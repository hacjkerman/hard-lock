"""Detect an in-progress game so the shutdown can be deferred until it ends.

League of Legends runs a distinct game process ("League of Legends.exe") only
while you're in an actual match (from load screen through the end of the game) —
the launcher/client ("LeagueClient.exe") is separate. So a live match is simply
"is that process running?". Enumerated via the Toolhelp snapshot API (ctypes),
which spawns no console window.
"""

import ctypes
from ctypes import wintypes

TH32CS_SNAPPROCESS = 0x00000002
DEFAULT_GAMES = ["League of Legends.exe"]


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def running_process_names() -> "set[str]":
    """Lowercased names of all running processes. Empty set on any failure."""
    k = ctypes.windll.kernel32
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    invalid = ctypes.c_void_p(-1).value
    if not snap or snap == invalid:
        return set()
    names: set[str] = set()
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        if k.Process32FirstW(snap, ctypes.byref(entry)):
            while True:
                names.add(entry.szExeFile.lower())
                if not k.Process32NextW(snap, ctypes.byref(entry)):
                    break
    finally:
        k.CloseHandle(snap)
    return names


def is_game_active(process_names=None) -> bool:
    """True if any of the given game process names is currently running. An
    explicit empty list means "no games configured" → always False (the feature
    is off); only None falls back to DEFAULT_GAMES."""
    if process_names is None:
        process_names = DEFAULT_GAMES
    names = [n.lower() for n in process_names if n]
    if not names:
        return False
    try:
        running = running_process_names()
    except Exception:
        return False
    return any(n in running for n in names)
