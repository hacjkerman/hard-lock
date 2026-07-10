import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from hard_lock.config import Config


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "config.json"

    def _cfg(self, **overrides) -> Config:
        if overrides:
            self.path.write_text(json.dumps(overrides))
        return Config.load(self.path)

    # ───────── defaults / load ─────────
    def test_load_writes_defaults_when_missing(self):
        cfg = Config.load(self.path)
        self.assertTrue(self.path.exists())
        self.assertEqual(cfg.daily_cap_minutes, 480)
        self.assertEqual(cfg.late_night_hour, 23)

    def test_load_merges_partial_over_defaults(self):
        cfg = self._cfg(daily_cap_minutes=120)
        self.assertEqual(cfg.daily_cap_minutes, 120)
        # untouched key still comes from defaults
        self.assertEqual(cfg.grace_seconds, 60)

    # ───────── tightening is immediate ─────────
    def test_tightening_cap_is_immediate(self):
        cfg = self._cfg(daily_cap_minutes=480)
        applied, deferred = cfg.apply_settings({"daily_cap_minutes": 120})
        self.assertEqual(cfg.daily_cap_minutes, 120)
        self.assertTrue(applied)
        self.assertFalse(deferred)

    def test_tightening_cutoff_earlier_is_immediate(self):
        cfg = self._cfg(hard_cutoff_time="23:30")
        _, deferred = cfg.apply_settings({"hard_cutoff_time": "22:00"})
        self.assertEqual(cfg.hard_cutoff_time, "22:00")
        self.assertFalse(deferred)

    # ───────── weakening is deferred ─────────
    def test_weakening_cap_is_deferred(self):
        cfg = self._cfg(daily_cap_minutes=480, edit_cooldown_hours=24)
        applied, deferred = cfg.apply_settings({"daily_cap_minutes": 600})
        # value must NOT change yet
        self.assertEqual(cfg.daily_cap_minutes, 480)
        self.assertTrue(deferred)
        self.assertIn("daily_cap_minutes", cfg._data["pending_changes"])

    def test_weakening_cutoff_later_is_deferred(self):
        cfg = self._cfg(hard_cutoff_time="23:00")
        _, deferred = cfg.apply_settings({"hard_cutoff_time": "23:45"})
        self.assertEqual(cfg.hard_cutoff_time, "23:00")
        self.assertTrue(deferred)

    def test_enabling_dry_run_is_weakening(self):
        cfg = self._cfg(dry_run=False)
        _, deferred = cfg.apply_settings({"dry_run": True})
        self.assertFalse(cfg.dry_run)  # still armed until cooldown
        self.assertTrue(deferred)

    def test_disabling_dry_run_is_tightening(self):
        cfg = self._cfg(dry_run=True)
        applied, deferred = cfg.apply_settings({"dry_run": False})
        self.assertFalse(cfg.dry_run)
        self.assertTrue(applied)
        self.assertFalse(deferred)

    def test_lowering_cooldown_uses_current_cooldown_for_its_own_deferral(self):
        cfg = self._cfg(edit_cooldown_hours=24)
        before = dt.datetime.now()
        cfg.apply_settings({"edit_cooldown_hours": 1})
        entry = cfg._data["pending_changes"]["edit_cooldown_hours"]
        eff = dt.datetime.fromisoformat(entry["effective_at"])
        # deferred by the OLD 24h cooldown, not the new 1h
        self.assertGreater((eff - before).total_seconds(), 23 * 3600)

    # ───────── late_night_hour guard ─────────
    def test_raising_late_night_hour_is_weakening(self):
        cfg = self._cfg(late_night_hour=23)
        _, deferred = cfg.apply_settings({"late_night_hour": 24})
        self.assertEqual(cfg.late_night_hour, 23)
        self.assertTrue(deferred)

    def test_lowering_late_night_hour_is_tightening(self):
        cfg = self._cfg(late_night_hour=23)
        applied, _ = cfg.apply_settings({"late_night_hour": 21})
        self.assertEqual(cfg.late_night_hour, 21)
        self.assertTrue(applied)

    def test_is_late_night_wraps_past_midnight(self):
        # Window is late_night_hour (23) .. day_reset_hour (4), wrapping midnight.
        cfg = self._cfg(late_night_hour=23, day_reset_hour=4)
        self.assertTrue(cfg.is_late_night(dt.datetime(2026, 7, 2, 23, 0)))
        self.assertTrue(cfg.is_late_night(dt.datetime(2026, 7, 2, 23, 59)))
        self.assertTrue(cfg.is_late_night(dt.datetime(2026, 7, 2, 0, 30)))   # past midnight
        self.assertTrue(cfg.is_late_night(dt.datetime(2026, 7, 2, 3, 59)))
        self.assertFalse(cfg.is_late_night(dt.datetime(2026, 7, 2, 4, 0)))   # after reset
        self.assertFalse(cfg.is_late_night(dt.datetime(2026, 7, 2, 22, 59)))
        self.assertFalse(cfg.is_late_night(dt.datetime(2026, 7, 2, 12, 0)))

    def test_late_night_hour_24_is_off(self):
        cfg = self._cfg(late_night_hour=24)
        self.assertFalse(cfg.is_late_night(dt.datetime(2026, 7, 2, 23, 0)))
        self.assertFalse(cfg.is_late_night(dt.datetime(2026, 7, 2, 2, 0)))

    def test_is_late_night_non_wrapping(self):
        cfg = self._cfg(late_night_hour=1, day_reset_hour=4)  # 01:00..04:00
        self.assertTrue(cfg.is_late_night(dt.datetime(2026, 7, 2, 2, 0)))
        self.assertFalse(cfg.is_late_night(dt.datetime(2026, 7, 2, 0, 30)))
        self.assertFalse(cfg.is_late_night(dt.datetime(2026, 7, 2, 5, 0)))

    # ───────── removing warnings is weakening ─────────
    def test_removing_a_warning_is_weakening(self):
        cfg = self._cfg(warning_minutes_before=[30, 10, 5, 1])
        _, deferred = cfg.apply_settings({"warning_minutes_before": [10, 5, 1]})
        # dropping the 30-min heads-up reduces safety → must defer
        self.assertEqual(cfg.warning_minutes_before, [30, 10, 5, 1])
        self.assertTrue(deferred)

    def test_adding_a_warning_is_tightening(self):
        cfg = self._cfg(warning_minutes_before=[10, 5, 1])
        applied, deferred = cfg.apply_settings({"warning_minutes_before": [30, 10, 5, 1]})
        self.assertEqual(cfg.warning_minutes_before, [30, 10, 5, 1])
        self.assertTrue(applied)
        self.assertFalse(deferred)

    # ───────── pending activation ─────────
    def test_pending_activates_on_reload_after_effective_at(self):
        cfg = self._cfg(daily_cap_minutes=480, edit_cooldown_hours=24)
        cfg.apply_settings({"daily_cap_minutes": 600})
        # hand-rewrite the pending entry to be already due, then reload
        data = json.loads(self.path.read_text())
        past = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        data["pending_changes"]["daily_cap_minutes"]["effective_at"] = past
        self.path.write_text(json.dumps(data))

        cfg2 = Config.load(self.path)
        self.assertEqual(cfg2.daily_cap_minutes, 600)
        self.assertEqual(cfg2._data["pending_changes"], {})

    def test_due_pending_activates_without_reload(self):
        """A queued weakening must activate on a running instance once due,
        not only after a restart."""
        cfg = self._cfg(daily_cap_minutes=480, edit_cooldown_hours=24)
        cfg.apply_settings({"daily_cap_minutes": 600})
        # force it due in-memory
        past = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        cfg._data["pending_changes"]["daily_cap_minutes"]["effective_at"] = past

        cfg.refresh_pending()
        self.assertEqual(cfg.daily_cap_minutes, 600)
        self.assertEqual(cfg._data["pending_changes"], {})

    def test_cancel_pending(self):
        cfg = self._cfg(daily_cap_minutes=480)
        cfg.apply_settings({"daily_cap_minutes": 600})
        self.assertTrue(cfg.cancel_pending("daily_cap_minutes"))
        self.assertEqual(cfg._data["pending_changes"], {})
        self.assertFalse(cfg.cancel_pending("daily_cap_minutes"))

    # ───────── resilience: bad/BOM config must not crash ─────────
    def test_corrupt_config_falls_back_to_defaults(self):
        self.path.write_text("{ this is not valid json ", encoding="utf-8")
        cfg = Config.load(self.path)  # must not raise
        self.assertEqual(cfg.daily_cap_minutes, 480)
        # the bad file is preserved for debugging
        self.assertTrue(self.path.with_name(self.path.name + ".corrupt").exists())
        # and a fresh valid config is written
        self.assertEqual(json.loads(self.path.read_text())["daily_cap_minutes"], 480)

    def test_utf8_bom_config_is_tolerated(self):
        # a hand-edit on Windows can prepend a BOM
        self.path.write_text('﻿{"daily_cap_minutes": 90}', encoding="utf-8")
        cfg = Config.load(self.path)
        self.assertEqual(cfg.daily_cap_minutes, 90)

    def test_non_object_config_falls_back(self):
        self.path.write_text("[1, 2, 3]", encoding="utf-8")
        cfg = Config.load(self.path)
        self.assertEqual(cfg.daily_cap_minutes, 480)

    def test_malformed_pending_missing_effective_at_dropped(self):
        # valid JSON dict, but a pending entry is missing effective_at
        self.path.write_text(json.dumps({
            "daily_cap_minutes": 480,
            "pending_changes": {"daily_cap_minutes": {"value": 600}},
        }), encoding="utf-8")
        cfg = Config.load(self.path)  # must not raise
        self.assertEqual(cfg._data["pending_changes"], {})
        self.assertEqual(cfg.daily_cap_minutes, 480)

    def test_malformed_pending_bad_isoformat_dropped(self):
        self.path.write_text(json.dumps({
            "pending_changes": {"daily_cap_minutes": {"value": 600, "effective_at": "soon"}},
        }), encoding="utf-8")
        cfg = Config.load(self.path)  # must not raise
        self.assertEqual(cfg._data["pending_changes"], {})

    def test_concurrent_apply_and_refresh_keeps_file_valid(self):
        # Exercise the HUD-poll vs settings-thread race the lock + atomic save
        # must tame: many concurrent applies/refreshes must never crash and must
        # never leave config.json unparseable.
        import threading

        cfg = self._cfg(daily_cap_minutes=480, edit_cooldown_hours=0)
        errors: list = []

        def apply_worker():
            try:
                for i in range(60):
                    cfg.apply_settings({"daily_cap_minutes": 480 + (i % 7)})
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def refresh_worker():
            try:
                for _ in range(60):
                    cfg.refresh_pending()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=apply_worker) for _ in range(3)]
        threads += [threading.Thread(target=refresh_worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        # File must still be valid JSON (no torn write survived).
        json.loads(self.path.read_text(encoding="utf-8-sig"))

    # ───────── onboarding / setup ─────────
    def test_setup_completed_defaults_false(self):
        cfg = Config.load(self.path)
        self.assertFalse(cfg.setup_completed)

    def test_complete_setup_applies_directly_and_marks_done(self):
        cfg = self._cfg(daily_cap_minutes=480, dry_run=True)
        cfg.complete_setup({
            "daily_cap_minutes": 300, "hard_cutoff_time": "22:00",
            "dry_run": False, "not_a_setting": 1,
        })
        self.assertEqual(cfg.daily_cap_minutes, 300)
        self.assertEqual(cfg.hard_cutoff_time, "22:00")
        self.assertFalse(cfg.dry_run)  # set directly, no cooldown deferral
        self.assertTrue(cfg.setup_completed)
        self.assertNotIn("not_a_setting", cfg._data)  # unknown keys ignored
        self.assertTrue(json.loads(self.path.read_text())["setup_completed"])

    # ───────── traffic-light + cutoff math ─────────
    def test_state_for_thresholds(self):
        cfg = self._cfg()
        self.assertEqual(cfg.state_for(10 * 60), "red")
        self.assertEqual(cfg.state_for(30 * 60), "amber")
        self.assertEqual(cfg.state_for(2 * 3600), "green")


if __name__ == "__main__":
    unittest.main()
