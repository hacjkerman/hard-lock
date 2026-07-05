import tempfile
import unittest
from pathlib import Path

from hard_lock.history import DayHistory, EventLog


class EventLogTestCase(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "events.jsonl"

    def test_append_and_recent_newest_first(self):
        log = EventLog(self.path)
        log.append("warning", ts="2026-01-01T10:00:00", minutes=5)
        log.append("shutdown", ts="2026-01-01T10:05:00", reason="cap", dry_run=True)
        recent = log.recent(10)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0]["type"], "shutdown")  # newest first
        self.assertEqual(recent[1]["type"], "warning")
        self.assertEqual(recent[0]["reason"], "cap")

    def test_recent_limit(self):
        log = EventLog(self.path)
        for i in range(20):
            log.append("warning", ts=f"2026-01-01T10:{i:02d}:00", minutes=i)
        self.assertEqual(len(log.recent(5)), 5)

    def test_missing_file_is_empty(self):
        self.assertEqual(EventLog(self.path).recent(), [])

    def test_torn_line_is_skipped(self):
        self.path.write_text(
            '{"ts":"t","type":"a"}\n{ this is broken\n{"ts":"t2","type":"b"}\n',
            encoding="utf-8",
        )
        rows = EventLog(self.path).all()
        self.assertEqual([r["type"] for r in rows], ["a", "b"])


class DayHistoryTestCase(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "history.jsonl"

    def test_append_and_by_date_last_wins(self):
        h = DayHistory(self.path)
        h.append_day({"date": "2026-01-01", "active_seconds": 100, "cap_minutes": 480})
        h.append_day({"date": "2026-01-02", "active_seconds": 200, "cap_minutes": 480})
        h.append_day({"date": "2026-01-01", "active_seconds": 999, "cap_minutes": 480})
        by = h.by_date()
        self.assertEqual(by["2026-01-01"]["active_seconds"], 999)  # last wins
        self.assertEqual(by["2026-01-02"]["active_seconds"], 200)

    def test_empty_when_missing(self):
        self.assertEqual(DayHistory(self.path).all(), [])


if __name__ == "__main__":
    unittest.main()
