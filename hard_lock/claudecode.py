"""Detect an *actively working* Claude Code session so the shutdown can wait.

A running claude.exe only means the app is open — not that a session is working.
The real signal is Claude's session transcripts (.jsonl under ~/.claude/projects):
it appends a line for every message and every tool call/result. So a session is
still going if either

  1. some transcript was written within a recent window (normal back-and-forth
     work — many small appends), or
  2. a transcript's last entry is an unfinished tool call (``tool_use`` with no
     matching ``tool_result`` yet). Nothing is appended *during* a long-running
     tool, so this is what distinguishes "one slow operation in progress" from
     "the session actually finished".

Both checks cover ALL sessions and subagents: active while *any* transcript is
active, idle only once every session has finished. Reads modification times and
the last line's *structure* (entry/block types) — never message text. Fails safe
(returns False) on any error, so a glitch can never hold the shutdown forever.
"""

import json
import time
from pathlib import Path

from . import league

# How far back a transcript write still counts as "working".
DEFAULT_WINDOW_SECONDS = 300.0
# An unfinished tool call holds the shutdown for at most this long, so a crashed
# session (tool_use never answered) can't defer forever.
IN_FLIGHT_MAX_SECONDS = 6 * 3600.0
# Claude Code must actually be running for any of it to count. Without this a
# stale transcript (or a session you closed) kept holding the shutdown long
# after Claude was gone.
DEFAULT_PROCESS_NAMES = ["claude.exe"]
_TAIL_BYTES = 65536


def _projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


def is_claude_running(process_names=None) -> bool:
    """True if a Claude Code process exists at all. Fails safe (False) on error,
    so a detection glitch releases the shutdown rather than holding it."""
    names = [n.lower() for n in (process_names if process_names is not None
                                 else DEFAULT_PROCESS_NAMES) if n]
    if not names:
        return False
    try:
        running = league.running_process_names()
    except Exception:
        return False
    return any(n in running for n in names)


def _last_entry(path: Path):
    """The last JSON entry of a transcript, or None. Reads only the file's tail."""
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > _TAIL_BYTES:
                f.seek(size - _TAIL_BYTES)
                f.readline()  # discard a partial line
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
        if not lines:
            return None
        return json.loads(lines[-1].decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None


def _block_types(entry) -> list:
    msg = entry.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        return [b.get("type") for b in content if isinstance(b, dict)]
    return []


def _has_unfinished_tool_call(path: Path) -> bool:
    """True if the transcript ends on an assistant tool_use — i.e. a tool is
    still running (its tool_result hasn't been appended yet)."""
    entry = _last_entry(path)
    if not isinstance(entry, dict):
        return False
    if entry.get("type") != "assistant":
        return False
    return "tool_use" in _block_types(entry)


def is_claude_active(window_seconds: float = DEFAULT_WINDOW_SECONDS,
                     projects_dir=None, process_names=None,
                     require_process: bool = True) -> bool:
    """True while any Claude Code session is actively working.

    Two conditions must BOTH hold: Claude is running at all, and some session is
    mid-work (a recent transcript append, or an unanswered tool call). Closing
    Claude therefore releases the shutdown immediately, instead of waiting out
    the window or a stale in-flight tool call.
    """
    try:
        if require_process and not is_claude_running(process_names):
            return False  # nothing running -> nothing to wait for
        base = Path(projects_dir) if projects_dir is not None else _projects_dir()
        if not base.exists():
            return False
        now = time.time()
        cutoff = now - float(window_seconds)
        in_flight_cutoff = now - IN_FLIGHT_MAX_SECONDS
        for p in base.glob("**/*.jsonl"):
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if mtime >= cutoff:
                return True  # recent append → actively working
            # Quiet for a while, but a long-running tool may still be in flight.
            if mtime >= in_flight_cutoff and _has_unfinished_tool_call(p):
                return True
        return False
    except Exception:
        return False
