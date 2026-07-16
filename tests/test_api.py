import datetime as dt
import json
import tempfile
import time
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
        open_session_prompt=api_kwargs.get("open_session_prompt"),
        league_active=api_kwargs.get("league_active"),
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

    def test_manual_close_overrides_cutoff(self):
        # An on-demand manual close is authoritative — it overrides a nearer
        # cutoff (can even extend past it).
        api, config, _ = make({"daily_cap_minutes": 480, "hard_cutoff_time": "23:59"})
        config.cutoff_remaining_seconds = lambda now=None: 60.0  # cutoff in 1 min
        api.open_session_prompt()  # marks the prompt manual
        api.start_session_timer(30, override=True)  # 30-min manual close
        s = api.get_status()
        self.assertTrue(s["session_active"])
        self.assertGreater(s["remaining_seconds"], 29 * 60)  # ~30 min, not 1 min

    def test_bounded_timer_still_only_shortens(self):
        # The automatic (non-manual) timer must NOT override the cutoff.
        api, config, _ = make({"daily_cap_minutes": 480, "hard_cutoff_time": "23:59"})
        config.cutoff_remaining_seconds = lambda now=None: 60.0
        api.start_session_timer(30, override=False)  # bounded
        s = api.get_status()
        self.assertLessEqual(s["remaining_seconds"], 61)  # cutoff (1 min) still wins

    def test_on_demand_prompt_is_manual_with_full_range(self):
        api, _, _ = make({"daily_cap_minutes": 480, "hard_cutoff_time": "23:59"})
        api.open_session_prompt()
        info = api.get_session_prompt_info()
        self.assertTrue(info["manual"])
        self.assertEqual(info["max_minutes"], 480)

    def test_launch_prompt_is_bounded_not_manual(self):
        api, _, _ = make({"daily_cap_minutes": 480, "hard_cutoff_time": "23:59"})
        info = api.get_session_prompt_info()  # no on-demand open → late-night bounded
        self.assertFalse(info["manual"])
        self.assertLessEqual(info["max_minutes"], 480)

    def test_bar_tracks_cap_when_cap_is_binding(self):
        # No cutoff / timer → cap is the only limit; a fresh day ≈ full bar.
        api, _, _ = make({"daily_cap_minutes": 480, "hard_cutoff_time": None})
        s = api.get_status()
        self.assertEqual(s["binding"], "cap")
        self.assertAlmostEqual(s["remaining_pct"], 100.0, delta=0.5)
        self.assertIn("cap used", s["limit_label"])

    def test_bar_depletes_as_cap_is_used(self):
        api, _, _ = make({"daily_cap_minutes": 480, "hard_cutoff_time": None},
                         used_seconds=240 * 60)
        s = api.get_status()
        self.assertEqual(s["binding"], "cap")
        self.assertAlmostEqual(s["remaining_pct"], 50.0, delta=0.5)

    def test_bar_tracks_cutoff_when_cutoff_is_binding(self):
        # Huge cap so the wall-clock cutoff is always the nearest limit; the bar
        # is still expressed as a fraction of the daily cap.
        api, config, _ = make({"daily_cap_minutes": 1440, "hard_cutoff_time": "23:59"})
        s = api.get_status()
        self.assertEqual(s["binding"], "cutoff")
        self.assertGreaterEqual(s["remaining_pct"], 0.0)
        self.assertLessEqual(s["remaining_pct"], 100.0)
        self.assertIn("cutoff 23:59", s["limit_label"])
        expected = 100 * config.cutoff_remaining_seconds() / config.daily_cap_seconds
        self.assertAlmostEqual(s["remaining_pct"], round(expected, 1), delta=0.5)

    def test_get_settings_includes_per_day_schedule(self):
        api, config, _ = make({"daily_cap_minutes": 480, "hard_cutoff_time": "23:30"})
        s = api.get_settings()
        self.assertEqual(s["day_keys"], ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
        self.assertEqual(s["cap_by_day"], [480] * 7)
        self.assertEqual(s["cutoff_by_day"], ["23:30"] * 7)
        self.assertEqual(s["today_index"], config.logical_weekday())
        self.assertEqual(len(s["day_labels"]), 7)

    def test_bar_tracks_timer_relative_to_cap(self):
        # A 30-min timer against an 8h cap reads ~6.25% (30m / 480m).
        api, _, _ = make({"daily_cap_minutes": 480, "hard_cutoff_time": None})
        api.start_session_timer(30)
        s = api.get_status()
        self.assertEqual(s["binding"], "session")
        self.assertAlmostEqual(s["remaining_pct"], 6.25, delta=0.5)
        self.assertIn("work timer", s["limit_label"])

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

    def test_open_session_prompt_calls_callback(self):
        opened = []
        api, _, _ = make(open_session_prompt=lambda: opened.append(1))
        api.open_session_prompt()
        self.assertEqual(opened, [1])

    def test_session_prompt_info_reports_late_night(self):
        api, _, _ = make({"late_night_hour": 23})
        info = api.get_session_prompt_info()
        self.assertIn("is_late_night", info)

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
            {"daily_cap_minutes": 60, "hard_cutoff_time": None, "grace_seconds": 60,
             "dry_run": False},
            used_seconds=60 * 60,
            request_grace=lambda: graced.append(1),
        )
        api.tick()
        self.assertEqual(graced, [1])

    # ───────── don't-shut-down-during-a-game ─────────
    def test_shutdown_held_while_game_active(self):
        graced = []
        api, _, _ = make(
            {"daily_cap_minutes": 60, "hard_cutoff_time": None, "grace_seconds": 60},
            used_seconds=3600.0, request_grace=lambda: graced.append(1),
            league_active=lambda games: True,
        )
        api.tick()
        self.assertEqual(graced, [])  # NOT shut down — game in progress
        self.assertTrue(api.get_status()["shutdown_held"])

    def test_warnings_suppressed_while_game_active(self):
        # A held game must not fire (false, and intrusive) warnings.
        api, _, _ = make(
            {"daily_cap_minutes": 480, "hard_cutoff_time": None, "warning_minutes_before": [10]},
            used_seconds=(480 - 9) * 60,  # ~9 min left → inside the 10-min warning
            league_active=lambda games: True,
        )
        api.tick()
        self.assertEqual(api.get_status()["recent_warnings"], [])

    def test_warnings_fire_without_game(self):
        api, _, _ = make(
            {"daily_cap_minutes": 480, "hard_cutoff_time": None, "warning_minutes_before": [10]},
            used_seconds=(480 - 9) * 60,
            league_active=lambda games: False,
        )
        api.tick()
        self.assertIn(10, api.get_status()["recent_warnings"])

    def test_shutdown_held_within_buffer_after_game(self):
        graced = []
        api, _, _ = make(
            {"daily_cap_minutes": 60, "hard_cutoff_time": None, "grace_seconds": 60,
             "game_defer_grace_seconds": 180},
            used_seconds=3600.0, request_grace=lambda: graced.append(1),
            league_active=lambda games: False,
        )
        api._league_last_active = time.monotonic() - 60  # game ended 1 min ago
        api.tick()
        self.assertEqual(graced, [])  # still held (within the 3-min buffer)

    def test_shutdown_proceeds_after_buffer(self):
        graced = []
        api, _, _ = make(
            {"daily_cap_minutes": 60, "hard_cutoff_time": None, "grace_seconds": 60,
             "game_defer_grace_seconds": 180, "dry_run": False},
            used_seconds=3600.0, request_grace=lambda: graced.append(1),
            league_active=lambda games: False,
        )
        api._league_last_active = time.monotonic() - 240  # ended 4 min ago
        api.tick()
        self.assertEqual(graced, [1])  # buffer elapsed → shutdown fires

    def test_no_defer_when_game_never_ran(self):
        graced = []
        api, _, _ = make(
            {"daily_cap_minutes": 60, "hard_cutoff_time": None, "grace_seconds": 60,
             "dry_run": False},
            used_seconds=3600.0, request_grace=lambda: graced.append(1),
            league_active=lambda games: False,
        )
        api.tick()
        self.assertEqual(graced, [1])  # no game seen → normal shutdown

    def test_defer_disabled_when_no_games_configured(self):
        graced = []
        api, _, _ = make(
            {"daily_cap_minutes": 60, "hard_cutoff_time": None, "grace_seconds": 60,
             "defer_for_games": [], "dry_run": False},
            used_seconds=3600.0, request_grace=lambda: graced.append(1),
            league_active=lambda games: True,
        )
        api.tick()
        self.assertEqual(graced, [1])  # feature off → shutdown despite game

    def test_dry_run_does_not_tear_down_at_the_limit(self):
        # Dry-run must NOT trigger grace/teardown (which would exit the app and
        # lock you out of changing the setting). It registers the hit and runs on.
        graced = []
        api, _, _ = make(
            {"daily_cap_minutes": 60, "hard_cutoff_time": None, "grace_seconds": 60,
             "dry_run": True},
            used_seconds=3600.0, request_grace=lambda: graced.append(1),
        )
        api.tick()
        self.assertEqual(graced, [])  # no real grace/teardown in dry-run
        self.assertTrue(api.get_status()["dry_run_fired"])

    def test_dry_run_logs_shutdown_once(self):
        events = EventLog(Path(tempfile.mkdtemp()) / "e.jsonl")
        api, _, _ = make(
            {"daily_cap_minutes": 60, "hard_cutoff_time": None, "grace_seconds": 60,
             "dry_run": True},
            used_seconds=3600.0, event_log=events,
        )
        api.tick()
        api.tick()
        api.tick()
        shutdowns = [e for e in events.all() if e.get("type") == "shutdown"]
        self.assertEqual(len(shutdowns), 1)  # logged once, not every tick
        self.assertTrue(shutdowns[0]["dry_run"])

    def test_on_game_change_fires_on_transitions(self):
        calls = []
        api, _, _ = make(
            {"daily_cap_minutes": 480, "hard_cutoff_time": None},
            league_active=lambda games: True,
        )
        api._on_game_change = lambda active: calls.append(active)
        api.tick()  # game running → True
        api._league_active = lambda games: False
        api._league_last_active = time.monotonic() - 240  # ended, past buffer
        api.tick()  # released → False
        self.assertEqual(calls, [True, False])

    def test_request_disarm_is_pending_not_disarmed(self):
        api, _, _ = make({"edit_cooldown_hours": 24})
        api.request_disarm()
        s = api.get_status()
        self.assertTrue(s["disarm_pending"])
        self.assertFalse(s["disarmed"])
        self.assertIsNotNone(s["disarm_remaining_hm"])

    def test_matured_disarm_shows_disarmed(self):
        api, config, _ = make()
        config._data["disarm_at"] = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        s = api.get_status()
        self.assertTrue(s["disarmed"])
        self.assertFalse(s["disarm_pending"])

    def test_re_arm_clears_disarm_and_relaunches(self):
        called = []
        api, config, _ = make()
        api._re_arm = lambda: called.append(1)
        api.request_disarm()
        api.re_arm()
        self.assertIsNone(config.disarm_at)
        self.assertEqual(called, [1])

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

    # ───────── onboarding ─────────
    def test_get_onboarding_info(self):
        api, _, _ = make({"daily_cap_minutes": 480, "late_night_hour": 23})
        info = api.get_onboarding_info()
        self.assertEqual(info["daily_cap_minutes"], 480)
        self.assertIn("dry_run", info)

    def test_finish_onboarding_applies_and_completes(self):
        opened = []
        api, config, _ = make(open_hud=lambda: opened.append(1))
        res = api.finish_onboarding({
            "daily_cap_minutes": 300, "hard_cutoff_time": "22:00",
            "late_night_hour": 21, "dry_run": False,
        })
        self.assertTrue(res["ok"])
        self.assertIsNone(res["autostart"])
        self.assertEqual(config.daily_cap_minutes, 300)
        self.assertEqual(config.hard_cutoff_time, "22:00")
        self.assertEqual(config.late_night_hour, 21)
        self.assertFalse(config.dry_run)
        self.assertTrue(config.setup_completed)
        self.assertEqual(opened, [])  # finish does NOT open the HUD

    def test_finish_onboarding_coerces_bad_values(self):
        api, config, _ = make()
        api.finish_onboarding({"daily_cap_minutes": "nope", "late_night_hour": 99})
        self.assertGreaterEqual(config.daily_cap_minutes, 1)
        self.assertLessEqual(config.late_night_hour, 24)
        self.assertTrue(config.setup_completed)

    def test_finish_onboarding_autostart_failure_reported(self):
        from unittest import mock
        api, _, _ = make()
        with mock.patch("hard_lock.autostart.install", return_value=(False, "Access is denied")):
            res = api.finish_onboarding({"autostart": True})
        self.assertFalse(res["autostart"]["ok"])
        self.assertIn("denied", res["autostart"]["message"].lower())

    def test_enter_app_opens_hud(self):
        opened = []
        api, _, _ = make(open_hud=lambda: opened.append(1))
        api.enter_app()
        self.assertEqual(opened, [1])

    def test_get_settings_includes_late_night_hour(self):
        api, _, _ = make({"late_night_hour": 22})
        s = api.get_settings()
        self.assertEqual(s["late_night_hour"], 22)

    def test_get_autostart_status(self):
        from unittest import mock
        api, _, _ = make()
        with mock.patch("hard_lock.autostart.is_installed", return_value=True):
            self.assertTrue(api.get_autostart_status()["installed"])
        with mock.patch("hard_lock.autostart.is_installed", return_value=False):
            self.assertFalse(api.get_autostart_status()["installed"])

    def test_set_autostart_enable_triggers_elevated_install(self):
        from unittest import mock
        api, _, _ = make()
        with mock.patch("hard_lock.autostart.install_elevated", return_value=True) as inst, \
             mock.patch("hard_lock.autostart.uninstall_elevated") as uninst, \
             mock.patch("hard_lock.autostart.is_installed", return_value=True):
            res = api.set_autostart(True)
        inst.assert_called_once()
        uninst.assert_not_called()
        self.assertTrue(res["triggered"])
        self.assertTrue(res["installed"])

    def test_set_autostart_disable_triggers_elevated_uninstall(self):
        from unittest import mock
        api, _, _ = make()
        with mock.patch("hard_lock.autostart.uninstall_elevated", return_value=True) as uninst, \
             mock.patch("hard_lock.autostart.install_elevated") as inst, \
             mock.patch("hard_lock.autostart.is_installed", return_value=False):
            res = api.set_autostart(False)
        uninst.assert_called_once()
        inst.assert_not_called()
        self.assertFalse(res["installed"])

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
        from hard_lock.config import _DAYS
        api, config, _ = make({"daily_cap_minutes": 480, "edit_cooldown_hours": 24})
        today = _DAYS[config.logical_weekday()]
        config.apply_settings({f"cap_{today}": 600})  # weakening → deferred
        past = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        config._data["pending_changes"][f"cap_{today}"]["effective_at"] = past

        api.tick()
        self.assertEqual(config.daily_cap_minutes, 600)


if __name__ == "__main__":
    unittest.main()
