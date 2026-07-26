"""Detect an active Claude Code session so the shutdown can wait for it.

Claude Code (the Windows desktop app that hosts the Code session) runs as
``claude.exe``. So "is a session active?" is simply "is that process running?" —
enumerated via the same Toolhelp snapshot the game-defer uses (no console flash).

This is deliberately coarse: it holds while the Claude app is *open*, which is the
"all sessions completed" signal. It never *extends* anything and never suppresses
the shutdown warning — the grace countdown still shows; it just doesn't power off
while Claude is still there (see ui.GraceCountdown).
"""

from . import league

DEFAULT_CLAUDE_PROCESSES = ["claude.exe"]


def is_claude_active(process_names=None) -> bool:
    """True if a Claude Code process is running. Fails safe (False) on any error,
    so a detection glitch can never hold the shutdown forever."""
    names = [n.lower() for n in (process_names if process_names is not None
                                 else DEFAULT_CLAUDE_PROCESSES) if n]
    if not names:
        return False
    try:
        running = league.running_process_names()
    except Exception:
        return False
    return any(n in running for n in names)
