import datetime as dt
import json
import os
from pathlib import Path


class State:
    def __init__(self, date: str, used_seconds: float, path: Path):
        self.date = date
        self.used_seconds = used_seconds
        self._path = path

    @classmethod
    def load(cls, path: Path) -> "State":
        today = dt.date.today().isoformat()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                # Guard against valid-but-non-object JSON (e.g. `[1,2,3]`, `42`):
                # data.get would raise AttributeError and crash the app at logon.
                if isinstance(data, dict) and data.get("date") == today:
                    return cls(today, float(data.get("used_seconds", 0.0)), path)
            except (OSError, ValueError, TypeError, UnicodeError):
                # Corrupt usage data → start today from zero rather than crash.
                pass
        return cls(today, 0.0, path)

    def accumulate(self, delta_seconds: float) -> None:
        today = dt.date.today().isoformat()
        if today != self.date:
            self.date = today
            self.used_seconds = 0.0
        self.used_seconds += max(0.0, delta_seconds)

    def save(self) -> None:
        # Atomic write so a torn/partial state.json can't be left behind.
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(
            json.dumps({"date": self.date, "used_seconds": self.used_seconds}, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)
