"""Where Hard Lock keeps its data and bundled assets.

In dev (running from source) data lives in the repo root, so the existing
workflow and `config.example.json` reference are unchanged. When frozen by
PyInstaller, `__file__` points inside a temp extraction dir, so data instead
lives in a stable per-user location (`%APPDATA%\\HardLock`).
"""

import os
import sys
from pathlib import Path

APP_NAME = "HardLock"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def data_dir() -> Path:
    """Directory holding config.json / state.json. Created if missing."""
    if is_frozen():
        base = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
    else:
        base = Path(__file__).resolve().parent.parent  # repo root
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_path() -> Path:
    return data_dir() / "config.json"


def state_path() -> Path:
    return data_dir() / "state.json"


def webui_dir() -> Path:
    """Bundled web assets — always alongside the package (PyInstaller keeps the
    package layout, so this resolves in both source and frozen builds)."""
    return Path(__file__).resolve().parent / "webui"
