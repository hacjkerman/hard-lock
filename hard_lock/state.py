import datetime as dt
import json
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
            data = json.loads(path.read_text())
            if data.get("date") == today:
                return cls(today, float(data.get("used_seconds", 0.0)), path)
        return cls(today, 0.0, path)

    def accumulate(self, delta_seconds: float) -> None:
        today = dt.date.today().isoformat()
        if today != self.date:
            self.date = today
            self.used_seconds = 0.0
        self.used_seconds += max(0.0, delta_seconds)

    def save(self) -> None:
        self._path.write_text(
            json.dumps({"date": self.date, "used_seconds": self.used_seconds}, indent=2)
        )
