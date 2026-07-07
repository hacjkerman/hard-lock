import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from hard_lock.api import Api
from hard_lock.config import Config
from hard_lock.history import DayHistory, EventLog
from hard_lock.state import State


class FakeTracker:
    """Returns a fixed active delta per tick."""

    def __init__(self, delta=0.0):
        self.delta = delta

    def tick(self):
        return self.delta


def make(config_overrides=None, used_seconds=0.0, tracker_delta=0.0,
         event_log=None, day_history=None, state_date=None, state_cap_minutes=None,
         **api_kwargs):
    d = Path(tempfile.mkdtemp())
    cpath, spath = d / "config.json", d / "state.json"
    if config_overrides:
        cpath.write_text(json.dumps(config_overrides))
    config = Config.load(cpath)
    # Default to today's logical day so Api.__init__ doesn't roll over.
    state = State(state_date or config.logical_date(), used_seconds, spath, state_cap_minutes)
    api = Api(
        config=config,
        state=state,
        tracker=FakeTracker(tracker_delta),
        request_grace=api_kwargs.get("request_grace", lambda: None),
        open_settings=lambda: None,
        open_hud=api_kwargs.get("open_hud", lambda: None),
        hide_hud=api_kwargs.get("hide_hud"),
        event_log=event_log,
        day_history=day_history,
    )
    return api, config, state


class ApiStatusTestCase(unittest.TestCase):
    def test_effective_is_min_of_cap_and_cutoff(self):
        # cap far away, cutoff near → effective tracks cutoff
        api, _, _ = make({"daily_cap_minutes": 480, "hard_cutoff_time": "23:59"})
        s = api.get_status()
        self.assertLessEqual(s["remaining_seconds"], s["cap_remaining_seconds"])

    def test_session_timer_only_tightens(self):
        api, _, _ = make({"daily_cap_minutes": 480, "hard_cutoff_time": None})
        api.start_session_timer(30)
        s = api.get_status()
        self.assertTrue(s["session_active"])
        # 30-min session must dominate the 8h cap
        self.assertLessEqual(s["remaining_seconds"], 30 * 60 + 1)
        self.assertGreater(s["remaining_seconds"], 29 * 60)

    def test_no_session_by_default(self):
        api, _, _ = make()
        s = api.get_status()
        self.assertFalse(s["session_active"])
        self.assertIsNone(s["session_remaining_hm"])

    def test_start_session_opens_hud_and_sets_deadline(self):
        opened = []
        api, _, _ = make(open_hud=lambda: opened.append(1))
        res = api.start_session_timer(45)
        self.assertEqual(res, {"ok": True})
        self.assertEqual(opened, [1])
        self.assertIsNotNone(api._session_deadline)

    def test_hide_hud_calls_callback(self):
        hidden = []
        api, _, _ = make(hide_hud=lambda: hidden.append(1))
        api.hide_hud()
        self.assertEqual(hidden, [1])

    def test_hide_hud_without_callback_is_noop(self):
        api, _, _ = make()  # hide_hud is None
        api.hide_hud()  # must not raise

    def test_skip_session_opens_hud_without_deadline(self):
        opened = []
        api, _, _ = make(open_hud=lambda: opened.append(1))
        api.skip_session_timer()
        self.assertEqual(opened, [1])
        self.assertIsNone(api._session_deadline)

    def test_start_session_ignores_bad_input(self):
        api, _, _ = make()
        api.start_session_timer("not a number")
        self.assertIsNone(api._session_deadline)
        api.start_session_timer(0)
        self.assertIsNone(api._session_deadline)

    def test_session_prompt_info_floor_bounded_by_cutoff(self):
        # cutoff is what limits us late at night
        api, _, _ = make({"daily_cap_minutes": 480, "hard_cutoff_time": "23:59"})
        info = api.get_session_prompt_info()
        self.assertGreaterEqual(info["max_minutes"], 1)
        self.assertLessEqual(info["max_minutes"], 480)
        self.assertEqual(info["late_night_hour"], 23)

    def test_grace_requested_when_effective_hits_grace(self):
        graced = []
        # cap already spent, so effective ~0 → below grace_seconds
        api, _, _ = make(
            {"daily_cap_minutes": 60, "hard_cutoff_time": None, "grace_seconds": 60},
            used_seconds=60 * 60,
            request_grace=lambda: graced.append(1),
        )
        api.tick()
        self.assertEqual(graced, [1])

    def test_tracker_accumulates_into_state(self):
        api, _, state = make(tracker_delta=5.0)
        api.tick()
        self.assertEqual(state.used_seconds, 5.0)

    def test_get_status_is_read_only(self):
        # The read-only snapshot must not advance the clock; only tick() does.
        api, _, state = make(tracker_delta=5.0)
        api.get_status()
        api.get_status()
        self.assertEqual(state.used_seconds, 0.0)

    def test_get_settings_includes_late_night_hour(self):
        api, _, _ = make({"late_night_hour": 22})
        s = api.get_settings()
        self.assertEqual(s["late_night_hour"], 22)

    def test_apply_settings_late_night_hour_tightening(self):
        api, config, _ = make({"late_night_hour": 23})
        res = api.apply_settings({"late_night_hour": 21})  # earlier = tightening
        self.assertEqual(config.late_night_hour, 21)
        self.assertTrue(res["applied"])
        self.assertFalse(res["deferred"])

    # ───────── Phase 4: rollover, history, events ─────────
    def _loggers(self):
        d = Path(tempfile.mkdtemp())
        return EventLog(d / "events.jsonl"), DayHistory(d / "history.jsonl")

    def test_day_rollover_archives_and_resets(self):
        ev, dh = self._loggers()
        api, config, state = make(
            {"daily_cap_minutes": 480}, used_seconds=3600.0,
            state_date="2020-01-01", event_log=ev, day_history=dh,
        )
        # Api.__init__ should have rolled the stale day over.
        self.assertEqual(state.date, config.logical_date())
        self.assertEqual(state.used_seconds, 0.0)
        by = dh.by_date()
        self.assertIn("2020-01-01", by)
        self.assertEqual(by["2020-01-01"]["active_seconds"], 3600.0)
        self.assertFalse(by["2020-01-01"]["hit_cap"])
        self.assertIn("day_rollover", [e["type"] for e in ev.recent()])

    def test_rollover_marks_hit_cap(self):
        ev, dh = self._loggers()
        # 10h used against an 8h cap → hit_cap
        make({"daily_cap_minutes": 480}, used_seconds=36000.0,
             state_date="2020-01-01", event_log=ev, day_history=dh)
        self.assertTrue(dh.by_date()["2020-01-01"]["hit_cap"])

    def test_rollover_uses_the_days_own_cap_not_current(self):
        ev, dh = self._loggers()
        # Yesterday's cap was 480 and 300 min (18000s) was used (under cap).
        # The cap is now 120, but the archive must use the day's own cap.
        make({"daily_cap_minutes": 120}, used_seconds=18000.0,
             state_date="2020-01-01", state_cap_minutes=480,
             event_log=ev, day_history=dh)
        rec = dh.by_date()["2020-01-01"]
        self.assertEqual(rec["cap_minutes"], 480)
        self.assertFalse(rec["hit_cap"])  # 300 min < 480 min cap

    def test_get_history_rolls_a_stale_day(self):
        ev, dh = self._loggers()
        api, config, state = make({"daily_cap_minutes": 480}, used_seconds=7200.0,
                                  event_log=ev, day_history=dh)
        # Simulate crossing the reset boundary before any HUD poll rolled over.
        state.date = "2020-01-01"
        state.cap_minutes = 480
        api.get_history()  # must archive the stale day itself
        self.assertIn("2020-01-01", dh.by_date())
        self.assertEqual(state.date, config.logical_date())

    def test_streaks_ignore_never_used_days(self):
        # A fresh install (only today has data) must not show a 42-day streak.
        api, _, _ = make({"daily_cap_minutes": 480}, used_seconds=3600.0)
        stats = api.get_history()["stats"]
        self.assertEqual(stats["current_streak"], 1)
        self.assertEqual(stats["best_streak"], 1)

    def test_get_history_window_and_today_live(self):
        api, config, _ = make({"daily_cap_minutes": 480}, used_seconds=7200.0)
        hist = api.get_history()
        self.assertEqual(len(hist["days"]), 42)
        last = hist["days"][-1]
        self.assertEqual(last["date"], config.logical_date())
        self.assertAlmostEqual(last["active_hours"], 2.0, places=2)
        self.assertIn("current_streak", hist["stats"])
        self.assertIn("events", hist)

    def test_apply_settings_logs_event(self):
        ev, _ = self._loggers()
        api, _, _ = make({"daily_cap_minutes": 480}, event_log=ev)
        api.apply_settings({"daily_cap_minutes": 120})  # tightening
        self.assertIn("settings", [e["type"] for e in ev.recent()])

    def test_warning_and_shutdown_events_logged(self):
        ev, _ = self._loggers()
        api, _, _ = make(
            {"daily_cap_minutes": 60, "hard_cutoff_time": None,
             "grace_seconds": 60, "warning_minutes_before": [1]},
            used_seconds=3600.0, event_log=ev,
        )
        api.tick()
        types = [e["type"] for e in ev.recent()]
        self.assertIn("warning", types)
        self.assertIn("shutdown", types)
        shutdown = next(e for e in ev.recent() if e["type"] == "shutdown")
        self.assertEqual(shutdown["reason"], "cap")
        self.assertTrue(shutdown["dry_run"])

    def test_due_pending_applies_during_tick(self):
        """A queued cap-raise that has come due should activate while the app
        is running (on the next tick), not only after a restart."""
        api, config, _ = make({"daily_cap_minutes": 480, "edit_cooldown_hours": 24})
        config.apply_settings({"daily_cap_minutes": 600})
        past = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        config._data["pending_changes"]["daily_cap_minutes"]["effective_at"] = past

        api.tick()
        self.assertEqual(config.daily_cap_minutes, 600)


if __name__ == "__main__":
    unittest.main()
