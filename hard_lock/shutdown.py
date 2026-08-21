import subprocess
import sys

# Windowed builds have no console, so spawning shutdown.exe without this flashes
# a console window on screen. The other subprocess callers (autostart, guardian)
# already suppress it; this keeps the shutdown path consistent.
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def initiate_shutdown(dry_run: bool = False) -> None:
    if dry_run:
        print("[DRY RUN] Would execute: shutdown.exe /s /f /t 0", file=sys.stderr)
        return
    subprocess.run(
        ["shutdown.exe", "/s", "/f", "/t", "0"],
        check=False,
        creationflags=CREATE_NO_WINDOW,
    )
