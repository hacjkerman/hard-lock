"""Detect an *actively working* Codex thread so the shutdown can wait.

The Codex Desktop app and ``codex exec`` both record each thread as a rollout
(.jsonl under ~/.codex/sessions/YYYY/MM/DD, or $CODEX_HOME/sessions). A thread
stays in the folder of the day it started and keeps being appended to after
that. Every turn opens with an ``event_msg`` of type ``task_started`` and closes
with ``task_complete``, or ``turn_aborted`` when interrupted. So a thread is
still going if either

  1. some rollout was written within a recent window (normal back-and-forth
     work, the same rule as Claude Code), or
  2. a rollout's latest turn has started and not closed. Nothing is appended
     while a long tool call runs, so this is what keeps a quiet build, a
     delegated Claude run or a remote job from being powered off under Codex.

This is the other half of claudecode.py: whichever agent drives, and whichever
is delegated work, the shutdown waits while either is mid-turn. Reads
modification times and entry types only — never message text. Fails safe
(returns False) on any error, so a glitch can never hold the shutdown forever.
"""

import os
import time
from pathlib import Path

from . import league
from .claudecode import DEFAULT_WINDOW_SECONDS, IN_FLIGHT_MAX_SECONDS, _TAIL_BYTES, _tail_entries

# The Desktop app's bundled CLI and ``codex exec`` both run as codex.exe. The
# app keeps it open, so on its own it only means Codex is available.
DEFAULT_PROCESS_NAMES = ["codex.exe"]
_TURN_OPENED = ("task_started",)
_TURN_CLOSED = ("task_complete", "turn_aborted")


def _sessions_dir() -> Path:
    home = os.environ.get("CODEX_HOME")
    return (Path(home) if home else Path.home() / ".codex") / "sessions"


def is_codex_running(process_names=None) -> bool:
    """True if a Codex process exists at all. Fails safe (False) on error."""
    names = [n.lower() for n in (process_names if process_names is not None
                                 else DEFAULT_PROCESS_NAMES) if n]
    if not names:
        return False
    try:
        running = league.running_process_names()
    except Exception:
        return False
    return any(n in running for n in names)


def _has_open_turn(path: Path) -> bool:
    """True while the rollout's latest turn has started and not closed.

    Walks back from the end to the nearest turn marker. With none in view, a
    turn long enough to push its own start out of the tail is still open (a
    closed turn leaves its completion near the end), while a file read whole
    never started one.
    """
    for entry in reversed(_tail_entries(path)):
        if entry.get("type") != "event_msg":
            continue
        payload = entry.get("payload")
        kind = payload.get("type") if isinstance(payload, dict) else None
        if kind in _TURN_CLOSED:
            return False
        if kind in _TURN_OPENED:
            return True
    try:
        return path.stat().st_size > _TAIL_BYTES
    except OSError:
        return False


def is_codex_active(window_seconds: float = DEFAULT_WINDOW_SECONDS,
                    sessions_dir=None, process_names=None,
                    require_process: bool = True) -> bool:
    """True while any Codex thread is actively working.

    Codex must be running at all, and some thread must be mid-work (a recent
    rollout append, or a turn that has not closed). Quitting Codex therefore
    releases the shutdown immediately.
    """
    try:
        if require_process and not is_codex_running(process_names):
            return False
        base = Path(sessions_dir) if sessions_dir is not None else _sessions_dir()
        if not base.exists():
            return False
        now = time.time()
        cutoff = now - float(window_seconds)
        in_flight_cutoff = now - IN_FLIGHT_MAX_SECONDS
        for p in base.glob("**/rollout-*.jsonl"):
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if mtime >= cutoff:
                return True
            if mtime >= in_flight_cutoff and _has_open_turn(p):
                return True
        return False
    except Exception:
        return False
