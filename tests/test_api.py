import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from hard_lock.api import Api
from hard_lock.config import Config
from hard_lock.state import State


class FakeTracker:
    """Returns a fixed active delta per tick."""

    def __init__(self, delta=0.0):
        self.delta = delta

    def tick(self):
        return self.delta


def make(config_overrides=None, used_seconds=0.0, tracker_delta=0.0, **api_kwargs):
    d = Path(tempfile.mkdtemp())
    cpath, spath = d / "config.json", d / "state.json"
    if config_overrides:
        cpath.write_text(json.dumps(config_overrides))
    config = Config.load(cpath)
    state = State(dt.date.today().isoformat(), used_seconds, spath)
    api = Api(
        config=config,
        state=state,
        tracker=FakeTracker(tracker_delta),
        request_grace=api_kwargs.get("request_grace", lambda: None),
        open_settings=lambda: None,
        open_hud=api_kwargs.get("open_hud", lambda: None),
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
        api.get_status()
        self.assertEqual(graced, [1])

    def test_tracker_accumulates_into_state(self):
        api, _, state = make(tracker_delta=5.0)
        api.get_status()
        self.assertEqual(state.used_seconds, 5.0)

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

    def test_due_pending_applies_during_status_poll(self):
        """A queued cap-raise that has come due should activate while the app
        is running (on the next status poll), not only after a restart."""
        api, config, _ = make({"daily_cap_minutes": 480, "edit_cooldown_hours": 24})
        config.apply_settings({"daily_cap_minutes": 600})
        past = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        config._data["pending_changes"]["daily_cap_minutes"]["effective_at"] = past

        api.get_status()
        self.assertEqual(config.daily_cap_minutes, 600)


if __name__ == "__main__":
    unittest.main()
