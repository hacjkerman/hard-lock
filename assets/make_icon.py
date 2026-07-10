"""Generate assets/hardlock.ico (+ .png) from hard_lock.tray.make_image, so the
tray icon and the Windows exe icon are the exact same mark.

Run from the repo root:  py -3.12 assets/make_icon.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hard_lock.tray import make_image  # noqa: E402

ASSETS = ROOT / "assets"
master = make_image(256)
master.save(ASSETS / "hardlock.png")
master.save(
    ASSETS / "hardlock.ico",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("wrote", ASSETS / "hardlock.ico", "and hardlock.png")
