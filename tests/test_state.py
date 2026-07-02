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
        self.assertEqual(st.used_seconds, 0.0)
        self.assertEqual(st.date, dt.date.today().isoformat())

    def test_load_same_day_restores_used(self):
        today = dt.date.today().isoformat()
        self.path.write_text(json.dumps({"date": today, "used_seconds": 123.0}))
        st = State.load(self.path)
        self.assertEqual(st.used_seconds, 123.0)

    def test_load_stale_day_resets(self):
        self.path.write_text(json.dumps({"date": "2000-01-01", "used_seconds": 999.0}))
        st = State.load(self.path)
        self.assertEqual(st.used_seconds, 0.0)

    def test_accumulate_adds(self):
        st = State(dt.date.today().isoformat(), 0.0, self.path)
        st.accumulate(10)
        st.accumulate(5)
        self.assertEqual(st.used_seconds, 15.0)

    def test_accumulate_clamps_negative(self):
        st = State(dt.date.today().isoformat(), 0.0, self.path)
        st.accumulate(-10)
        self.assertEqual(st.used_seconds, 0.0)

    def test_accumulate_resets_on_new_day(self):
        st = State("2000-01-01", 500.0, self.path)
        st.accumulate(5)  # today != stored date → reset then add
        self.assertEqual(st.used_seconds, 5.0)
        self.assertEqual(st.date, dt.date.today().isoformat())

    def test_corrupt_state_starts_fresh(self):
        self.path.write_text("not json", encoding="utf-8")
        st = State.load(self.path)  # must not raise
        self.assertEqual(st.used_seconds, 0.0)
        self.assertEqual(st.date, dt.date.today().isoformat())

    def test_non_object_state_starts_fresh(self):
        # valid JSON but not an object → data.get would raise AttributeError
        for payload in ("[1, 2, 3]", "42", '"foo"', "null"):
            self.path.write_text(payload, encoding="utf-8")
            st = State.load(self.path)  # must not raise
            self.assertEqual(st.used_seconds, 0.0)
            self.assertEqual(st.date, dt.date.today().isoformat())

    def test_save_roundtrip(self):
        st = State(dt.date.today().isoformat(), 42.0, self.path)
        st.save()
        data = json.loads(self.path.read_text())
        self.assertEqual(data["used_seconds"], 42.0)


if __name__ == "__main__":
    unittest.main()
