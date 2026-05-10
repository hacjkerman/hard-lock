import subprocess
import sys


def initiate_shutdown(dry_run: bool = False) -> None:
    if dry_run:
        print("[DRY RUN] Would execute: shutdown.exe /s /f /t 0", file=sys.stderr)
        return
    subprocess.run(["shutdown.exe", "/s", "/f", "/t", "0"], check=False)
