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
        # a bare cap change fans out to the per-day keys
        self.assertIn("cap_mon", cfg._data["pending_changes"])

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

    def test_adding_a_defer_game_is_weakening(self):
        cfg = self._cfg(defer_for_games=["League of Legends.exe"])
        _, deferred = cfg.apply_settings({"defer_for_games": ["League of Legends.exe", "dota2.exe"]})
        self.assertEqual(cfg.defer_for_games, ["League of Legends.exe"])  # not yet
        self.assertTrue(deferred)

    def test_removing_a_defer_game_is_tightening(self):
        cfg = self._cfg(defer_for_games=["League of Legends.exe", "dota2.exe"])
        applied, _ = cfg.apply_settings({"defer_for_games": ["League of Legends.exe"]})
        self.assertEqual(cfg.defer_for_games, ["League of Legends.exe"])
        self.assertTrue(applied)

    def test_raising_game_defer_buffer_is_weakening(self):
        cfg = self._cfg(game_defer_grace_seconds=180)
        _, deferred = cfg.apply_settings({"game_defer_grace_seconds": 600})
        self.assertEqual(cfg.game_defer_grace_seconds, 180)
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
        cfg = self._cfg(edit_cooldown_hours=24)
        cfg._data["cap_sat"] = 480
        cfg.apply_settings({"cap_sat": 600})  # weakening → deferred
        # hand-rewrite the pending entry to be already due, then reload
        data = json.loads(self.path.read_text())
        past = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        data["pending_changes"]["cap_sat"]["effective_at"] = past
        self.path.write_text(json.dumps(data))

        cfg2 = Config.load(self.path)
        self.assertEqual(cfg2._data["cap_sat"], 600)
        self.assertEqual(cfg2._data["pending_changes"], {})

    def test_due_pending_activates_without_reload(self):
        """A queued weakening must activate on a running instance once due,
        not only after a restart."""
        cfg = self._cfg(edit_cooldown_hours=24)
        cfg._data["cap_sat"] = 480
        cfg.apply_settings({"cap_sat": 600})
        # force it due in-memory
        past = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        cfg._data["pending_changes"]["cap_sat"]["effective_at"] = past

        cfg.refresh_pending()
        self.assertEqual(cfg._data["cap_sat"], 600)
        self.assertEqual(cfg._data["pending_changes"], {})

    def test_cancel_pending(self):
        cfg = self._cfg(edit_cooldown_hours=24)
        cfg._data["cap_sat"] = 480
        cfg.apply_settings({"cap_sat": 600})
        self.assertTrue(cfg.cancel_pending("cap_sat"))
        self.assertEqual(cfg._data["pending_changes"], {})
        self.assertFalse(cfg.cancel_pending("cap_sat"))

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

    # ───────── disarm (cooldown-gated stop) ─────────
    def test_request_disarm_is_cooldown_gated(self):
        cfg = self._cfg(edit_cooldown_hours=24)
        self.assertIsNone(cfg.disarm_at)
        self.assertFalse(cfg.disarm_due())
        cfg.request_disarm()
        self.assertIsNotNone(cfg.disarm_at)
        self.assertFalse(cfg.disarm_due())  # 24h out — still armed
        self.assertGreater(cfg.disarm_remaining_seconds(), 23 * 3600)

    def test_cancel_disarm(self):
        cfg = self._cfg()
        cfg.request_disarm()
        cfg.cancel_disarm()
        self.assertIsNone(cfg.disarm_at)
        self.assertFalse(cfg.disarm_due())
        self.assertIsNone(cfg.disarm_remaining_seconds())

    def test_disarm_due_when_matured(self):
        cfg = self._cfg()
        cfg._data["disarm_at"] = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        self.assertTrue(cfg.disarm_due())

    # ───────── traffic-light + cutoff math ─────────
    def test_state_for_thresholds(self):
        cfg = self._cfg()
        self.assertEqual(cfg.state_for(10 * 60), "red")
        self.assertEqual(cfg.state_for(30 * 60), "amber")
        self.assertEqual(cfg.state_for(2 * 3600), "green")

    # ───────── per-day (weekend) limits ─────────
    def test_missing_days_seeded_from_scalar_baseline(self):
        cfg = self._cfg(daily_cap_minutes=500, hard_cutoff_time="22:15")
        self.assertEqual(cfg.cap_by_day(), [500] * 7)
        self.assertEqual(cfg.cutoff_by_day(), ["22:15"] * 7)

    def test_daily_cap_resolves_to_todays_weekday(self):
        from hard_lock.config import _DAYS
        cfg = self._cfg(daily_cap_minutes=480)
        today = _DAYS[cfg.logical_weekday()]
        cfg._data[f"cap_{today}"] = 333
        self.assertEqual(cfg.daily_cap_minutes, 333)
        self.assertEqual(cfg.daily_cap_seconds, 333 * 60)

    def test_cutoff_resolves_to_todays_weekday(self):
        from hard_lock.config import _DAYS
        cfg = self._cfg(hard_cutoff_time="23:30")
        today = _DAYS[cfg.logical_weekday()]
        cfg._data[f"cutoff_{today}"] = "21:00"
        self.assertEqual(cfg.hard_cutoff_time, "21:00")

    def test_after_midnight_cutoff_spans_the_same_logical_night(self):
        # Fri 23:00 with a Fri cutoff of 01:30 → 2h30m left (lands on Sat 01:30),
        # not "already passed". day_reset_hour defaults to 4.
        from hard_lock.config import _DAYS
        cfg = self._cfg()
        friday_2300 = dt.datetime(2026, 1, 9, 23, 0)  # a Friday
        self.assertEqual(friday_2300.weekday(), 4)
        cfg._data[f"cutoff_{_DAYS[cfg.logical_weekday(friday_2300)]}"] = "01:30"
        self.assertAlmostEqual(cfg.cutoff_remaining_seconds(friday_2300), 2.5 * 3600, delta=1)

    def test_evening_cutoff_before_midnight_still_works(self):
        from hard_lock.config import _DAYS
        cfg = self._cfg()
        friday_2200 = dt.datetime(2026, 1, 9, 22, 0)
        cfg._data[f"cutoff_{_DAYS[cfg.logical_weekday(friday_2200)]}"] = "23:30"
        self.assertAlmostEqual(cfg.cutoff_remaining_seconds(friday_2200), 1.5 * 3600, delta=1)

    def test_past_evening_cutoff_reads_zero_after_midnight(self):
        # Sat 02:00 is still logically Friday; a Fri 23:30 cutoff already passed.
        from hard_lock.config import _DAYS
        cfg = self._cfg()
        sat_0200 = dt.datetime(2026, 1, 10, 2, 0)
        cfg._data[f"cutoff_{_DAYS[cfg.logical_weekday(sat_0200)]}"] = "23:30"
        self.assertEqual(cfg.cutoff_remaining_seconds(sat_0200), 0.0)

    def test_raising_one_days_cap_is_deferred(self):
        cfg = self._cfg(edit_cooldown_hours=24)
        cfg._data["cap_sat"] = 480
        applied, deferred = cfg.apply_settings({"cap_sat": 720})
        self.assertFalse(applied)
        self.assertTrue(deferred)
        self.assertIn("cap_sat", cfg._data["pending_changes"])
        self.assertEqual(cfg._data["cap_sat"], 480)  # not yet in force

    def test_lowering_one_days_cap_is_immediate(self):
        cfg = self._cfg()
        cfg._data["cap_sat"] = 480
        applied, deferred = cfg.apply_settings({"cap_sat": 300})
        self.assertTrue(applied)
        self.assertFalse(deferred)
        self.assertEqual(cfg._data["cap_sat"], 300)

    def test_later_night_cutoff_is_deferred_even_past_midnight(self):
        # 23:30 → 01:30 lets you stay up 2h later, so it must be deferred despite
        # 01:30 < 23:30 on the raw clock. (day_reset_hour defaults to 4.)
        cfg = self._cfg(edit_cooldown_hours=24)
        cfg._data["cutoff_sat"] = "23:30"
        applied, deferred = cfg.apply_settings({"cutoff_sat": "01:30"})
        self.assertFalse(applied)
        self.assertTrue(deferred)
        self.assertEqual(cfg._data["cutoff_sat"], "23:30")  # not yet in force

    def test_earlier_night_cutoff_is_immediate(self):
        cfg = self._cfg()
        cfg._data["cutoff_sat"] = "23:30"
        applied, deferred = cfg.apply_settings({"cutoff_sat": "22:00"})
        self.assertTrue(applied)
        self.assertFalse(deferred)
        self.assertEqual(cfg._data["cutoff_sat"], "22:00")

    def test_reapplying_a_queued_value_is_idempotent(self):
        # Re-submitting the form (which shows queued values) must not cancel the
        # pending change or reset its timer — the bug that wiped a weekend cutoff.
        cfg = self._cfg(edit_cooldown_hours=24)
        cfg._data["cutoff_sat"] = "23:30"
        _, deferred = cfg.apply_settings({"cutoff_sat": "01:30"})
        self.assertTrue(deferred)
        eff_at = cfg._data["pending_changes"]["cutoff_sat"]["effective_at"]
        # Apply the same queued value again → no-op, timer untouched.
        applied2, deferred2 = cfg.apply_settings({"cutoff_sat": "01:30"})
        self.assertEqual(applied2, [])
        self.assertEqual(deferred2, [])
        self.assertIn("cutoff_sat", cfg._data["pending_changes"])
        self.assertEqual(cfg._data["pending_changes"]["cutoff_sat"]["effective_at"], eff_at)

    def test_reapplying_current_value_still_cancels_a_pending_change(self):
        # Deliberately setting the field back to the in-force value cancels the
        # queued change (an explicit revert).
        cfg = self._cfg(edit_cooldown_hours=24)
        cfg._data["cutoff_sat"] = "23:30"
        cfg.apply_settings({"cutoff_sat": "01:30"})
        cfg.apply_settings({"cutoff_sat": "23:30"})
        self.assertNotIn("cutoff_sat", cfg._data["pending_changes"])
        self.assertEqual(cfg._data["cutoff_sat"], "23:30")

    def test_activate_pending_applies_now_and_clears_queue(self):
        cfg = self._cfg(edit_cooldown_hours=24)
        cfg._data["cutoff_sat"] = "23:30"
        cfg.apply_settings({"cutoff_sat": "01:30"})  # queued
        self.assertIn("cutoff_sat", cfg._data["pending_changes"])
        self.assertTrue(cfg.activate_pending("cutoff_sat"))
        self.assertEqual(cfg._data["cutoff_sat"], "01:30")  # now in force
        self.assertNotIn("cutoff_sat", cfg._data["pending_changes"])
        self.assertFalse(cfg.activate_pending("cutoff_sat"))  # nothing queued now

    def test_setup_fans_baseline_out_to_all_days(self):
        cfg = Config.load(self.path)
        cfg.complete_setup({"daily_cap_minutes": 360, "hard_cutoff_time": "22:00"})
        self.assertEqual(cfg.cap_by_day(), [360] * 7)
        self.assertEqual(cfg.cutoff_by_day(), ["22:00"] * 7)


if __name__ == "__main__":
    unittest.main()
