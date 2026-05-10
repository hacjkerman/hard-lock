import datetime as dt
import json
from pathlib import Path

DEFAULTS = {
    "daily_cap_minutes": 480,
    "hard_cutoff_time": "23:30",
    "warning_minutes_before": [30, 10, 5, 1],
    "grace_seconds": 60,
    "idle_threshold_seconds": 120,
    "edit_cooldown_hours": 24,
    "dry_run": True,
    "pending_changes": {},
}

# For each configurable key, a function returning True when the proposed new
# value is a "weakening" (i.e. relaxes the lock) relative to the current value
# and therefore must be deferred by the edit cooldown. Tightening is immediate.
def _later_cutoff(old, new) -> bool:
    if new is None and old is not None:
        return True
    if old is None or new is None:
        return False
    return _hhmm_to_min(new) > _hhmm_to_min(old)


def _hhmm_to_min(s: str) -> int:
    h, m = map(int, s.split(":"))
    return h * 60 + m


WEAKENING = {
    "daily_cap_minutes": lambda old, new: int(new) > int(old),
    "hard_cutoff_time": _later_cutoff,
    "grace_seconds": lambda old, new: int(new) > int(old),
    "idle_threshold_seconds": lambda old, new: int(new) < int(old),
    "edit_cooldown_hours": lambda old, new: int(new) < int(old),
    "dry_run": lambda old, new: bool(new) and not bool(old),
}


class Config:
    def __init__(self, data: dict, path: Path):
        self._data = data
        self._path = path

    @classmethod
    def load(cls, path: Path) -> "Config":
        if path.exists():
            data = {**DEFAULTS, **json.loads(path.read_text())}
        else:
            data = dict(DEFAULTS)
            path.write_text(json.dumps(data, indent=2))
        # Migrate legacy pending_raise → pending_changes["daily_cap_minutes"]
        legacy = data.pop("pending_raise", None)
        if legacy and not data.get("pending_changes"):
            data["pending_changes"] = {
                "daily_cap_minutes": {
                    "value": legacy["new_cap_minutes"],
                    "effective_at": legacy["effective_at"],
                }
            }
        data.setdefault("pending_changes", {})
        c = cls(data, path)
        c._apply_pending()
        return c

    def save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2))

    def _apply_pending(self) -> None:
        pending = self._data.get("pending_changes") or {}
        now = dt.datetime.now()
        remaining = {}
        changed = False
        for key, entry in pending.items():
            if dt.datetime.fromisoformat(entry["effective_at"]) <= now:
                self._data[key] = entry["value"]
                changed = True
            else:
                remaining[key] = entry
        if changed or remaining != pending:
            self._data["pending_changes"] = remaining
            self.save()

    @property
    def daily_cap_seconds(self) -> int:
        return int(self._data["daily_cap_minutes"]) * 60

    @property
    def daily_cap_minutes(self) -> int:
        return int(self._data["daily_cap_minutes"])

    @property
    def hard_cutoff_time(self):
        return self._data.get("hard_cutoff_time")

    @property
    def warning_minutes_before(self) -> list:
        return list(self._data["warning_minutes_before"])

    @property
    def grace_seconds(self) -> int:
        return int(self._data["grace_seconds"])

    @property
    def idle_threshold_seconds(self) -> int:
        return int(self._data["idle_threshold_seconds"])

    @property
    def edit_cooldown_hours(self) -> int:
        return int(self._data["edit_cooldown_hours"])

    @property
    def dry_run(self) -> bool:
        return bool(self._data.get("dry_run", True))

    def remaining_seconds(self, state) -> float:
        return max(0.0, self.daily_cap_seconds - state.used_seconds)

    def cutoff_remaining_seconds(self):
        t = self._data.get("hard_cutoff_time")
        if not t:
            return None
        h, m = map(int, t.split(":"))
        now = dt.datetime.now()
        cutoff = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if cutoff < now:
            return 0.0
        return (cutoff - now).total_seconds()

    def pending_summary(self) -> str:
        pending = self._data.get("pending_changes") or {}
        if not pending:
            return ""
        parts = []
        for key, entry in pending.items():
            eff = dt.datetime.fromisoformat(entry["effective_at"])
            parts.append(
                f"{key} → {entry['value']} @ {eff.strftime('%Y-%m-%d %H:%M')}"
            )
        return "Pending: " + "; ".join(parts)

    def apply_settings(self, new: dict) -> tuple[list[str], list[str]]:
        """Apply a dict of settings. Tightening changes take effect immediately;
        weakening changes are deferred by edit_cooldown_hours. Returns
        (applied_descriptions, deferred_descriptions)."""
        applied: list[str] = []
        deferred: list[str] = []
        pending = dict(self._data.get("pending_changes") or {})

        # Always use the CURRENT cooldown for deferrals so lowering the
        # cooldown (itself a weakening) can't shorten its own deferral.
        cooldown_hours = int(self._data["edit_cooldown_hours"])
        effective_at = (dt.datetime.now() + dt.timedelta(hours=cooldown_hours)).isoformat()

        for key, value in new.items():
            old = self._data.get(key)
            if value == old and key not in pending:
                continue
            weakens = WEAKENING.get(key, lambda o, n: False)
            if key in WEAKENING and weakens(old, value):
                pending[key] = {"value": value, "effective_at": effective_at}
                deferred.append(f"{key}: {old} → {value}")
            else:
                self._data[key] = value
                pending.pop(key, None)
                applied.append(f"{key}: {old} → {value}")

        self._data["pending_changes"] = pending
        self.save()
        return applied, deferred

    def cancel_pending(self, key: str) -> bool:
        pending = dict(self._data.get("pending_changes") or {})
        if key not in pending:
            return False
        pending.pop(key)
        self._data["pending_changes"] = pending
        self.save()
        return True

    # Traffic-light thresholds — single source of truth. Based on time
    # remaining (min of cap-remaining and cutoff-remaining) in seconds.
    STATE_RED_SECONDS = 15 * 60
    STATE_AMBER_SECONDS = 60 * 60

    def state_for(self, remaining_seconds: float) -> str:
        if remaining_seconds <= self.STATE_RED_SECONDS:
            return "red"
        if remaining_seconds <= self.STATE_AMBER_SECONDS:
            return "amber"
        return "green"

    # Kept for backward compatibility with any external callers.
    def request_cap_change(self, new_cap_minutes: int) -> None:
        self.apply_settings({"daily_cap_minutes": int(new_cap_minutes)})
