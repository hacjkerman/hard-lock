"""Keep Hard Lock alive so closing the app can't defeat the lock.

Two processes guard each other: the main app and a lightweight ``--watchdog``.
Each writes a heartbeat file every ~1.5s; each relaunches the other the moment
that heartbeat goes stale. Kill one and it's back in a few seconds. The only
sanctioned stop is a cooldown-gated *disarm* (Config.disarm_*): while a disarm is
due, both processes exit and neither resurrects.

Nothing here is load-bearing for the shutdown itself — if the guardian fails to
start, the app still enforces; it just becomes closable again.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import time

from . import paths

HEARTBEAT_INTERVAL = 1.5   # seconds between heartbeat writes
HEARTBEAT_STALE = 4.0      # older than this ⇒ the other process is considered dead
_CREATE_NO_WINDOW = 0x08000000
_DETACHED_PROCESS = 0x00000008


def _hb_path(name: str):
    return paths.data_dir() / f"{name}.heartbeat"


def write_heartbeat(name: str) -> None:
    try:
        _hb_path(name).write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def clear_heartbeat(name: str) -> None:
    try:
        _hb_path(name).unlink()
    except OSError:
        pass


def heartbeat_age(name: str):
    """Seconds since the named process last checked in, or None if missing/bad."""
    try:
        ts = float(_hb_path(name).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return time.time() - ts


def is_alive(name: str, stale: float = HEARTBEAT_STALE) -> bool:
    age = heartbeat_age(name)
    return age is not None and age < stale


def _target_cmd(mode: str):
    """Command to (re)launch the given mode. Frozen build → the exe itself;
    dev → ``python -m hard_lock``."""
    if paths.is_frozen():
        return [sys.executable] if mode == "main" else [sys.executable, "--watchdog"]
    base = [sys.executable, "-m", "hard_lock"]
    return base if mode == "main" else base + ["--watchdog"]


def spawn(mode: str) -> None:
    try:
        subprocess.Popen(
            _target_cmd(mode),
            creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS,
            close_fds=True,
        )
    except Exception:
        pass


def acquire_singleton(name: str):
    """Named-mutex single-instance lock. Returns a handle to hold for the process
    lifetime, or None if another instance already holds it. Never raises."""
    try:
        import ctypes
        from ctypes import wintypes

        k = ctypes.windll.kernel32
        k.CreateMutexW.restype = wintypes.HANDLE
        k.CreateMutexW.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR]
        handle = k.CreateMutexW(None, False, name)
        ERROR_ALREADY_EXISTS = 183
        if not handle or k.GetLastError() == ERROR_ALREADY_EXISTS:
            return None
        return handle
    except Exception:
        # If we can't create the mutex, don't block startup — just skip the guard.
        return True


def disarm_due(now: "dt.datetime | None" = None) -> bool:
    """Read-only check of the shared config for a matured disarm. Deliberately
    does NOT go through Config.load (which can rewrite the file) so the watchdog
    can poll it without fighting the main process over config.json."""
    try:
        data = json.loads(paths.config_path().read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    at = data.get("disarm_at")
    if not at:
        return False
    try:
        return (now or dt.datetime.now()) >= dt.datetime.fromisoformat(at)
    except (TypeError, ValueError):
        return False


def run_watchdog() -> int:
    """The ``--watchdog`` process: heartbeat, and resurrect the main app while no
    disarm is due. Exits (without resurrecting) once a disarm matures."""
    if acquire_singleton(r"Local\HardLockWatchdog") is None:
        return 0  # another watchdog already running
    while True:
        write_heartbeat("watchdog")
        if disarm_due():
            clear_heartbeat("watchdog")
            return 0
        if not is_alive("main"):
            spawn("main")
            time.sleep(3.0)  # let it come up before re-checking
        time.sleep(HEARTBEAT_INTERVAL)
