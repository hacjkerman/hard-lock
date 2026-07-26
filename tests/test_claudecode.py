import unittest
from unittest import mock

from hard_lock import claudecode


class ClaudeCodeTestCase(unittest.TestCase):
    def test_detects_claude_process(self):
        with mock.patch("hard_lock.league.running_process_names",
                        return_value={"claude.exe", "explorer.exe"}):
            self.assertTrue(claudecode.is_claude_active())

    def test_absent_when_not_running(self):
        with mock.patch("hard_lock.league.running_process_names",
                        return_value={"explorer.exe", "node.exe"}):
            self.assertFalse(claudecode.is_claude_active())

    def test_explicit_empty_list_is_false(self):
        self.assertFalse(claudecode.is_claude_active([]))

    def test_fails_safe_on_error(self):
        with mock.patch("hard_lock.league.running_process_names", side_effect=OSError):
            self.assertFalse(claudecode.is_claude_active())


if __name__ == "__main__":
    unittest.main()
