import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from hard_lock import claudecode


def _write(path: Path, entries, age_seconds=0.0):
    """Write a transcript with the given entries, optionally aged."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    if age_seconds:
        old = time.time() - age_seconds
        os.utime(path, (old, old))


ASSISTANT_TEXT = {"type": "assistant", "message": {"content": [{"type": "text"}]}}
ASSISTANT_TOOL_USE = {"type": "assistant", "message": {"content": [{"type": "tool_use"}]}}
USER_TOOL_RESULT = {"type": "user", "message": {"content": [{"type": "tool_result"}]}}


class ClaudeCodeTestCase(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp()) / "projects"
        self.base.mkdir(parents=True)

    def active(self, window=300.0):
        return claudecode.is_claude_active(window, projects_dir=self.base)

    # ───────── recent-write window ─────────
    def test_recent_write_is_active(self):
        _write(self.base / "proj" / "s1.jsonl", [ASSISTANT_TEXT])
        self.assertTrue(self.active())

    def test_stale_finished_session_is_idle(self):
        # Ends on a completed tool result, untouched for an hour → done.
        _write(self.base / "proj" / "s1.jsonl", [ASSISTANT_TOOL_USE, USER_TOOL_RESULT],
               age_seconds=3600)
        self.assertFalse(self.active())

    def test_no_projects_dir_is_idle(self):
        self.assertFalse(claudecode.is_claude_active(projects_dir=self.base / "nope"))

    def test_empty_projects_dir_is_idle(self):
        self.assertFalse(self.active())

    # ───────── multiple sessions: any active holds ─────────
    def test_one_busy_session_among_idle_ones_holds(self):
        _write(self.base / "a" / "s1.jsonl", [USER_TOOL_RESULT], age_seconds=7200)
        _write(self.base / "b" / "s2.jsonl", [USER_TOOL_RESULT], age_seconds=3600)
        _write(self.base / "c" / "s3.jsonl", [ASSISTANT_TEXT])  # fresh
        self.assertTrue(self.active())

    def test_all_sessions_idle_releases(self):
        _write(self.base / "a" / "s1.jsonl", [USER_TOOL_RESULT], age_seconds=7200)
        _write(self.base / "b" / "s2.jsonl", [USER_TOOL_RESULT], age_seconds=3600)
        self.assertFalse(self.active())

    def test_subagent_transcript_counts(self):
        _write(self.base / "subagents" / "agent-abc.jsonl", [ASSISTANT_TEXT])
        self.assertTrue(self.active())

    # ───────── long-running tool still in flight ─────────
    def test_unfinished_tool_call_holds_past_the_window(self):
        # Quiet for 30 min, but the last entry is an unanswered tool_use → a
        # single long-running tool is still going.
        _write(self.base / "proj" / "s1.jsonl", [ASSISTANT_TEXT, ASSISTANT_TOOL_USE],
               age_seconds=1800)
        self.assertFalse(1800 <= 300)  # sanity: well outside the window
        self.assertTrue(self.active())

    def test_answered_tool_call_does_not_hold(self):
        _write(self.base / "proj" / "s1.jsonl",
               [ASSISTANT_TOOL_USE, USER_TOOL_RESULT], age_seconds=1800)
        self.assertFalse(self.active())

    def test_in_flight_tool_expires_after_max(self):
        # A crashed session (tool_use never answered) must not hold forever.
        _write(self.base / "proj" / "s1.jsonl", [ASSISTANT_TOOL_USE],
               age_seconds=claudecode.IN_FLIGHT_MAX_SECONDS + 3600)
        self.assertFalse(self.active())

    # ───────── resilience ─────────
    def test_corrupt_transcript_does_not_raise(self):
        p = self.base / "proj" / "bad.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{ not json at all\n", encoding="utf-8")
        old = time.time() - 3600
        os.utime(p, (old, old))
        self.assertFalse(self.active())  # unreadable → not active, no crash

    def test_window_is_configurable(self):
        _write(self.base / "proj" / "s1.jsonl", [USER_TOOL_RESULT], age_seconds=600)
        self.assertFalse(self.active(window=300))   # outside 5 min
        self.assertTrue(self.active(window=1200))   # inside 20 min


if __name__ == "__main__":
    unittest.main()
