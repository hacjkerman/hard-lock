import json
import os
from pathlib import Path


class State:
    """Active-time usage for the current logical day.

    The day-rollover decision (and archiving the finished day to history) lives
    in Api, which knows the configured reset hour and owns the loggers. State is
    just a container: `date` is the logical-day key it belongs to (or None if it
    has never been assigned one), `used_seconds` is active time so far, and
    `cap_minutes` snapshots the cap in force for this day so the archived history
    record reflects the cap that actually governed it (not a later change).
    """

    def __init__(self, date, used_seconds: float, path: Path, cap_minutes=None):
        self.date = date
        self.used_seconds = used_seconds
        self.cap_minutes = cap_minutes
        self._path = path

    @classmethod
    def load(cls, path: Path) -> "State":
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    date = data.get("date")
                    date = date if isinstance(date, str) and date else None
                    cap = data.get("cap_minutes")
                    cap = int(cap) if isinstance(cap, (int, float)) else None
                    return cls(date, float(data.get("used_seconds", 0.0)), path, cap)
            except (OSError, ValueError, TypeError, UnicodeError):
                # Corrupt usage data → start fresh rather than crash.
                pass
        return cls(None, 0.0, path)

    def accumulate(self, delta_seconds: float) -> None:
        self.used_seconds += max(0.0, delta_seconds)

    def roll_to(self, date: str, cap_minutes=None) -> None:
        """Begin a new logical day with a zeroed counter and the current cap."""
        self.date = date
        self.used_seconds = 0.0
        self.cap_minutes = cap_minutes
        self.save()

    def save(self) -> None:
        # Atomic write so a torn/partial state.json can't be left behind.
        data = {"date": self.date, "used_seconds": self.used_seconds}
        if self.cap_minutes is not None:
            data["cap_minutes"] = self.cap_minutes
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)
