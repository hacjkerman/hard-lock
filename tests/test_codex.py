import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from hard_lock import codex


def _write(path: Path, entries, age_seconds=0.0):
    """Write a rollout with the given entries, optionally aged."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    if age_seconds:
        old = time.time() - age_seconds
        os.utime(path, (old, old))


def ev(kind):
    return {"timestamp": "2026-09-27T14:52:00.000Z", "type": "event_msg", "payload": {"type": kind}}


def item(kind):
    return {"timestamp": "2026-09-27T14:52:00.000Z", "type": "response_item", "payload": {"type": kind}}


META = {"type": "session_meta", "payload": {"originator": "Codex Desktop", "source": "vscode"}}
QUIET = 1800  # well outside the 300 s window, well inside the in-flight max


class CodexTestCase(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp()) / "sessions"
        self.base.mkdir(parents=True)

    def rollout(self, entries, age_seconds=0.0, day="2026/09/26", name="rollout-2026-09-26T12-57-39-a.jsonl"):
        _write(self.base / day / name, entries, age_seconds)

    def active(self, window=300.0):
        # require_process=False isolates the rollout logic; the process gate
        # has its own tests below.
        return codex.is_codex_active(window, sessions_dir=self.base, require_process=False)

    # ───────── turn markers ─────────
    def test_open_turn_holds_past_the_window(self):
        # Quiet for 30 min mid-turn: one long tool call is still running.
        self.rollout([META, ev("task_started"), item("custom_tool_call")], QUIET)
        self.assertTrue(self.active())

    def test_completed_turn_does_not_hold(self):
        self.rollout([META, ev("task_started"), item("message"), ev("task_complete"),
                      ev("token_count")], QUIET)
        self.assertFalse(self.active())

    def test_aborted_turn_does_not_hold(self):
        self.rollout([META, ev("task_started"), item("reasoning"), ev("turn_aborted")], QUIET)
        self.assertFalse(self.active())

    def test_a_new_turn_after_a_finished_one_holds(self):
        self.rollout([META, ev("task_started"), ev("task_complete"),
                      ev("task_started"), item("reasoning")], QUIET)
        self.assertTrue(self.active())

    def test_the_night_it_powered_off(self):
        # The tail of a Codex Desktop thread the shutdown killed on 2026-09-28:
        # mid-turn, last line a tool call, no task_complete.
        self.rollout([META, ev("task_started"), ev("item_completed"), item("message"),
                      item("reasoning"), item("custom_tool_call"), {"type": "token_usage_record"},
                      item("custom_tool_call_output"), ev("token_count"), item("reasoning")], QUIET)
        self.assertTrue(self.active())

    def test_a_long_turn_whose_start_left_the_tail_holds(self):
        # An unfinished turn can outgrow the tail; only a completion ends it.
        filler = [dict(item("function_call_output"), pad="x" * 200) for _ in range(600)]
        self.rollout([META, ev("task_started")] + filler, QUIET)
        self.assertTrue(self.active())

    def test_a_thread_with_no_turn_does_not_hold(self):
        self.rollout([META, {"type": "turn_context"}, {"type": "world_state"}], QUIET)
        self.assertFalse(self.active())

    def test_open_turn_expires_after_max(self):
        # A crashed thread (turn never completed) must not hold forever.
        self.rollout([META, ev("task_started"), item("custom_tool_call")],
                     codex.IN_FLIGHT_MAX_SECONDS + 3600)
        self.assertFalse(self.active())

    # ───────── recent-write window ─────────
    def test_recent_write_is_active(self):
        self.rollout([META, ev("task_started"), ev("task_complete")])
        self.assertTrue(self.active())

    def test_window_is_configurable(self):
        self.rollout([META, ev("task_started"), ev("task_complete")], 600)
        self.assertFalse(self.active(window=300))
        self.assertTrue(self.active(window=1200))

    # ───────── many threads ─────────
    def test_one_busy_thread_among_idle_ones_holds(self):
        self.rollout([META, ev("task_started"), ev("task_complete")], 7200, name="rollout-a.jsonl")
        self.rollout([META, ev("task_started"), item("custom_tool_call")], QUIET,
                     day="2026/09/28", name="rollout-b.jsonl")
        self.assertTrue(self.active())

    def test_all_threads_finished_releases(self):
        self.rollout([META, ev("task_started"), ev("task_complete")], 7200, name="rollout-a.jsonl")
        self.rollout([META, ev("task_started"), ev("turn_aborted")], QUIET, name="rollout-b.jsonl")
        self.assertFalse(self.active())

    def test_only_rollouts_count(self):
        _write(self.base / "2026" / "09" / "28" / "notes.jsonl",
               [ev("task_started")], QUIET)
        self.assertFalse(self.active())

    # ───────── resilience ─────────
    def test_no_sessions_dir_is_idle(self):
        self.assertFalse(codex.is_codex_active(sessions_dir=self.base / "nope",
                                               require_process=False))

    def test_empty_sessions_dir_is_idle(self):
        self.assertFalse(self.active())

    def test_corrupt_rollout_does_not_raise(self):
        p = self.base / "2026" / "09" / "28" / "rollout-bad.jsonl"
        p.parent.mkdir(parents=True)
        p.write_text("{ not json at all\n", encoding="utf-8")
        old = time.time() - QUIET
        os.utime(p, (old, old))
        self.assertFalse(self.active())

    def test_empty_rollout_does_not_hold(self):
        _write(self.base / "2026" / "09" / "28" / "rollout-empty.jsonl", [], QUIET)
        self.assertFalse(self.active())

    def test_codex_home_sets_the_sessions_dir(self):
        home = self.base.parent
        self.rollout([META, ev("task_started")], QUIET)
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(home)}):
            self.assertTrue(codex.is_codex_active(require_process=False))

    # ───────── the process gate ─────────
    def test_no_codex_process_means_idle_even_mid_turn(self):
        self.rollout([META, ev("task_started")])
        with mock.patch("hard_lock.league.running_process_names", return_value={"explorer.exe"}):
            self.assertFalse(codex.is_codex_active(sessions_dir=self.base))

    def test_running_codex_mid_turn_holds(self):
        self.rollout([META, ev("task_started"), item("custom_tool_call")], QUIET)
        with mock.patch("hard_lock.league.running_process_names",
                        return_value={"codex.exe", "explorer.exe"}):
            self.assertTrue(codex.is_codex_active(sessions_dir=self.base))

    def test_process_detection_failure_fails_safe(self):
        self.rollout([META, ev("task_started")])
        with mock.patch("hard_lock.league.running_process_names", side_effect=OSError):
            self.assertFalse(codex.is_codex_active(sessions_dir=self.base))


class ShutdownWaitsForAgentsTestCase(unittest.TestCase):
    """Either agent working holds the power-off, whichever one is driving."""

    def cfg(self, on=True):
        return mock.Mock(grace_seconds=1, dry_run=True, defer_for_games=[],
                         defer_for_claude=on, claude_active_window_seconds=300)

    def holding(self, claude, codex_):
        from hard_lock import __main__ as m
        with mock.patch("hard_lock.claudecode.is_claude_active", return_value=claude), \
             mock.patch("hard_lock.codex.is_codex_active", return_value=codex_):
            return m._agent_active(self.cfg())()

    def test_codex_working_holds_while_claude_is_idle(self):
        self.assertTrue(self.holding(claude=False, codex_=True))

    def test_claude_working_holds_while_codex_is_idle(self):
        self.assertTrue(self.holding(claude=True, codex_=False))

    def test_both_idle_releases(self):
        self.assertFalse(self.holding(claude=False, codex_=False))

    def test_switched_off_waits_for_neither(self):
        from hard_lock import __main__ as m
        self.assertIsNone(m._agent_active(self.cfg(on=False)))

    def test_test_shutdown_countdown_waits_for_agents(self):
        from hard_lock import __main__ as m
        with mock.patch("hard_lock.config.Config.load", return_value=self.cfg()), \
             mock.patch("hard_lock.history.EventLog"), \
             mock.patch("hard_lock.ui.GraceCountdown") as grace, \
             mock.patch("hard_lock.claudecode.is_claude_active", return_value=False), \
             mock.patch("hard_lock.codex.is_codex_active", return_value=True):
            m._run_test_shutdown([])
            self.assertTrue(grace.call_args.kwargs["agent_active"]())


if __name__ == "__main__":
    unittest.main()
