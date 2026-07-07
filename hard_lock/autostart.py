"""Run Hard Lock at logon via a Windows Task Scheduler task.

Chosen over the Startup folder / HKCU Run key because a scheduled task is not
listed in Task Manager's Startup tab, so a moment of weakness can't toggle it
off there. This is convenience, not tamper-proofing — the task is still
removable by someone determined (that's an honest limitation of a
self-discipline tool).
"""

import subprocess
import sys
from pathlib import Path

TASK_NAME = "HardLock"


def launch_command() -> str:
    """The command Task Scheduler runs at logon.

    Frozen build → the packaged exe. From source → the windowed interpreter
    running the repo's launcher script; running a *script by full path* puts
    its directory on sys.path, so the import works regardless of the task's
    working directory.
    """
    from . import paths

    if paths.is_frozen():
        return f'"{sys.executable}"'

    interp = Path(sys.executable)
    pyw = interp.with_name("pythonw.exe")
    launcher = pyw if pyw.exists() else interp
    entry = paths.data_dir() / "launch.py"
    return f'"{launcher}" "{entry}"'


def _schtasks(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["schtasks", *args],
        capture_output=True,
        text=True,
    )


def install() -> tuple[bool, str]:
    """Create/replace the logon task. Returns (ok, message)."""
    res = _schtasks(
        "/create",
        "/tn", TASK_NAME,
        "/sc", "ONLOGON",
        "/tr", launch_command(),
        "/f",
    )
    if res.returncode == 0:
        return True, f'Installed logon task "{TASK_NAME}".'
    err = (res.stderr or res.stdout).strip()
    hint = ""
    if "denied" in err.lower() or "access" in err.lower():
        hint = " (try running this once from an elevated/admin console)"
    return False, f"Could not install task: {err}{hint}"


def uninstall() -> tuple[bool, str]:
    res = _schtasks("/delete", "/tn", TASK_NAME, "/f")
    if res.returncode == 0:
        return True, f'Removed logon task "{TASK_NAME}".'
    err = (res.stderr or res.stdout).strip()
    if "cannot find" in err.lower() or "does not exist" in err.lower():
        return True, "No logon task was installed."
    return False, f"Could not remove task: {err}"


def is_installed() -> bool:
    return _schtasks("/query", "/tn", TASK_NAME).returncode == 0


def status() -> str:
    return (
        f'Autostart: installed (task "{TASK_NAME}", runs at logon).'
        if is_installed()
        else "Autostart: not installed."
    )
