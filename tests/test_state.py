import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from hard_lock.state import State


class StateTestCase(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "state.json"

    def test_fresh_state_when_missing(self):
        st = State.load(self.path)
        self.assertIsNone(st.date)  # Api assigns the logical day on first poll
        self.assertEqual(st.used_seconds, 0.0)

    def test_load_preserves_saved_day_and_used(self):
        self.path.write_text(json.dumps({"date": "2026-01-02", "used_seconds": 123.0}))
        st = State.load(self.path)
        self.assertEqual(st.date, "2026-01-02")
        self.assertEqual(st.used_seconds, 123.0)

    def test_load_null_or_empty_date_is_none(self):
        for date in (None, ""):
            self.path.write_text(json.dumps({"date": date, "used_seconds": 5.0}))
            st = State.load(self.path)
            self.assertIsNone(st.date)

    def test_accumulate_is_pure_add(self):
        st = State("2026-01-02", 0.0, self.path)
        st.accumulate(10)
        st.accumulate(5)
        self.assertEqual(st.used_seconds, 15.0)
        self.assertEqual(st.date, "2026-01-02")  # no auto-reset

    def test_accumulate_clamps_negative(self):
        st = State("2026-01-02", 0.0, self.path)
        st.accumulate(-10)
        self.assertEqual(st.used_seconds, 0.0)

    def test_roll_to_zeroes_and_saves(self):
        st = State("2026-01-02", 500.0, self.path)
        st.roll_to("2026-01-03")
        self.assertEqual(st.date, "2026-01-03")
        self.assertEqual(st.used_seconds, 0.0)
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["date"], "2026-01-03")
        self.assertEqual(saved["used_seconds"], 0.0)

    def test_corrupt_state_starts_fresh(self):
        self.path.write_text("not json", encoding="utf-8")
        st = State.load(self.path)  # must not raise
        self.assertIsNone(st.date)
        self.assertEqual(st.used_seconds, 0.0)

    def test_non_object_state_starts_fresh(self):
        for payload in ("[1, 2, 3]", "42", '"foo"', "null"):
            self.path.write_text(payload, encoding="utf-8")
            st = State.load(self.path)  # must not raise
            self.assertIsNone(st.date)
            self.assertEqual(st.used_seconds, 0.0)

    def test_save_roundtrip(self):
        st = State(dt.date.today().isoformat(), 42.0, self.path)
        st.save()
        data = json.loads(self.path.read_text())
        self.assertEqual(data["used_seconds"], 42.0)

    def test_cap_minutes_roundtrip(self):
        st = State("2026-01-02", 100.0, self.path, cap_minutes=480)
        st.save()
        self.assertEqual(json.loads(self.path.read_text())["cap_minutes"], 480)
        self.assertEqual(State.load(self.path).cap_minutes, 480)

    def test_cap_minutes_absent_is_none(self):
        self.path.write_text(json.dumps({"date": "2026-01-02", "used_seconds": 5.0}))
        self.assertIsNone(State.load(self.path).cap_minutes)

    def test_roll_to_sets_cap(self):
        st = State("2026-01-02", 500.0, self.path, cap_minutes=480)
        st.roll_to("2026-01-03", cap_minutes=120)
        self.assertEqual(st.cap_minutes, 120)
        self.assertEqual(st.used_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
