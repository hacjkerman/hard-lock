import datetime as dt
import json
import os
import threading
from pathlib import Path

# Per-day schedule keys are cap_<day> / cutoff_<day>, indexed by
# datetime.date.weekday() (Mon=0 … Sun=6).
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_DAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

DEFAULTS = {
    "daily_cap_minutes": 480,
    "hard_cutoff_time": "23:30",
    "warning_minutes_before": [30, 10, 5, 1],
    "grace_seconds": 60,
    "idle_threshold_seconds": 120,
    "edit_cooldown_hours": 24,
    "late_night_hour": 23,
    "day_reset_hour": 4,
    # Don't shut down while one of these games is running; wait until it ends
    # plus game_defer_grace_seconds. Empty list disables the feature.
    "defer_for_games": ["League of Legends.exe"],
    "game_defer_grace_seconds": 180,
    # Don't power off while a Claude Code session is actively working. The grace
    # warning still shows; the machine just waits for Claude to finish. "Working"
    # = some session transcript written within claude_active_window_seconds.
    "defer_for_claude": True,
    "claude_active_window_seconds": 300,
    "dry_run": True,
    "setup_completed": False,
    # When set (ISO timestamp), a disarm has been requested; once now passes it,
    # the app + watchdog stop and stop resurrecting. The only sanctioned way out.
    "disarm_at": None,
    # When set (ISO timestamp) and in the future, a fixed-term commitment is
    # active: the lock can't be disarmed or weakened until it passes.
    "commit_until": None,
    "pending_changes": {},
}

# For each configurable key, a function returning True when the proposed new
# value is a "weakening" (i.e. relaxes the lock) relative to the current value
# and therefore must be deferred by the edit cooldown. Tightening is immediate.
# Cutoff keys are NOT here — a "later" cutoff depends on day_reset_hour (a
# 01:30 cutoff is later at night than 23:30), so they weaken via a Config method.
def _hhmm_to_min(s: str) -> int:
    h, m = map(int, s.split(":"))
    return h * 60 + m


def _fewer_warnings(old, new) -> bool:
    # Weakening if any warning that used to fire is no longer scheduled —
    # dropping a heads-up (e.g. the 30-min notice) reduces safety. Adding
    # warnings is a tightening and applies immediately.
    old_set = {int(x) for x in (old or [])}
    new_set = {int(x) for x in (new or [])}
    return not old_set.issubset(new_set)


def _more_games(old, new) -> bool:
    # Adding a game to the defer list gives the lock more reasons to hold off,
    # so it's a weakening. Removing games is a tightening (immediate).
    old_set = {str(x).lower() for x in (old or [])}
    new_set = {str(x).lower() for x in (new or [])}
    return not new_set.issubset(old_set)


WEAKENING = {
    "daily_cap_minutes": lambda old, new: int(new) > int(old),
    "warning_minutes_before": _fewer_warnings,
    "grace_seconds": lambda old, new: int(new) > int(old),
    "idle_threshold_seconds": lambda old, new: int(new) < int(old),
    "edit_cooldown_hours": lambda old, new: int(new) < int(old),
    # Raising the late-night hour makes the timer prompt fire later (or never
    # at >=24), which relaxes the lock, so treat it as a weakening.
    "late_night_hour": lambda old, new: int(new) > int(old),
    # Deferring the shutdown for games (adding one / a longer buffer) relaxes it.
    "defer_for_games": _more_games,
    "game_defer_grace_seconds": lambda old, new: int(new) > int(old),
    # Turning the Claude-Code wait ON gives the lock another reason to hold off.
    "defer_for_claude": lambda old, new: bool(new) and not bool(old),
    "dry_run": lambda old, new: bool(new) and not bool(old),
}

# Each per-day cap weakens like the global one (raising it is deferred). Per-day
# cutoffs weaken via Config._cutoff_weakens (day_reset-aware), same as the global.
for _day in _DAYS:
    WEAKENING[f"cap_{_day}"] = lambda old, new: int(new) > int(old)


class Config:
    def __init__(self, data: dict, path: Path):
        self._data = data
        self._path = path
        # The HUD poll thread (refresh_pending) and the settings window
        # (apply_settings/cancel_pending) run on separate pywebview threads and
        # both mutate self._data + rewrite the file. Serialize every
        # read-modify-write behind one reentrant lock. RLock because save() is
        # called from within already-locked methods.
        self._lock = threading.RLock()

    @classmethod
    def load(cls, path: Path) -> "Config":
        write_defaults = not path.exists()
        data = dict(DEFAULTS)
        if path.exists():
            try:
                # utf-8-sig tolerates a stray BOM (e.g. from a hand-edit on
                # Windows). Explicit utf-8 keeps read/write symmetric regardless
                # of the machine's locale.
                loaded = json.loads(path.read_text(encoding="utf-8-sig"))
                if not isinstance(loaded, dict):
                    raise ValueError("config root is not a JSON object")
                data = {**DEFAULTS, **loaded}
            except (OSError, ValueError, UnicodeError):
                # A corrupt config must never crash the app at logon — that would
                # silently disable the lock. Preserve the bad file for debugging
                # and fall back to safe defaults.
                try:
                    path.replace(path.with_name(path.name + ".corrupt"))
                except OSError:
                    pass
                data = dict(DEFAULTS)
                write_defaults = True
        # Seed the per-day schedule from the scalar baseline for any day that
        # doesn't have its own value yet (older configs predate per-day limits).
        for _d in _DAYS:
            data.setdefault(f"cap_{_d}", data.get("daily_cap_minutes", DEFAULTS["daily_cap_minutes"]))
            data.setdefault(f"cutoff_{_d}", data.get("hard_cutoff_time", DEFAULTS["hard_cutoff_time"]))
        if write_defaults:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
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
        # Atomic write: a crash or a concurrent write mid-save must never leave
        # a truncated config.json (that would trip the corrupt-file fallback and
        # silently reset the lock to defaults). Write a temp file, then replace.
        with self._lock:
            tmp = self._path.with_name(self._path.name + ".tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            os.replace(tmp, self._path)

    def refresh_pending(self) -> None:
        """Activate any queued weakening changes whose cooldown has elapsed.
        Called at load AND on every status poll, so a queued change takes
        effect on the running instance the moment it comes due — not only
        after the next restart."""
        self._apply_pending()

    def _apply_pending(self) -> None:
        with self._lock:
            pending = self._data.get("pending_changes") or {}
            now = dt.datetime.now()
            remaining = {}
            changed = False
            for key, entry in pending.items():
                try:
                    eff = dt.datetime.fromisoformat(entry["effective_at"])
                    value = entry["value"]
                except (KeyError, TypeError, ValueError):
                    # Malformed entry (bad/missing effective_at, non-dict, etc.)
                    # from a hand-edit or torn write — drop it rather than crash
                    # at logon or on every poll.
                    changed = True
                    continue
                if eff <= now:
                    self._data[key] = value
                    changed = True
                else:
                    remaining[key] = entry
            if changed or remaining != pending:
                self._data["pending_changes"] = remaining
                self.save()

    def logical_weekday(self, now: dt.datetime | None = None) -> int:
        """Weekday (Mon=0 … Sun=6) of the current *logical* day. Because the day
        rolls at day_reset_hour, 02:00 Saturday still counts as Friday — so
        Friday's cap/cutoff governs Friday night into the small hours."""
        return dt.date.fromisoformat(self.logical_date(now)).weekday()

    @property
    def daily_cap_minutes(self) -> int:
        key = f"cap_{_DAYS[self.logical_weekday()]}"
        return int(self._data.get(key, self._data["daily_cap_minutes"]))

    @property
    def daily_cap_seconds(self) -> int:
        return self.daily_cap_minutes * 60

    @property
    def hard_cutoff_time(self):
        key = f"cutoff_{_DAYS[self.logical_weekday()]}"
        return self._data.get(key, self._data.get("hard_cutoff_time"))

    def cap_by_day(self) -> list:
        return [int(self._data.get(f"cap_{d}", self._data["daily_cap_minutes"])) for d in _DAYS]

    def cutoff_by_day(self) -> list:
        return [self._data.get(f"cutoff_{d}", self._data.get("hard_cutoff_time")) for d in _DAYS]

    @staticmethod
    def day_keys() -> list:
        return list(_DAYS)

    @staticmethod
    def day_labels() -> list:
        return list(_DAY_LABELS)

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
    def late_night_hour(self) -> int:
        return int(self._data.get("late_night_hour", 23))

    def is_late_night(self, now: dt.datetime | None = None) -> bool:
        """True when the session-timer prompt should fire at launch. The window
        runs from late_night_hour until the day resets (day_reset_hour), so it
        WRAPS past midnight — e.g. 23:00 → 04:00, not just 23:00–23:59."""
        start = self.late_night_hour
        if start >= 24:
            return False  # 24 = off
        start %= 24
        end = self.day_reset_hour % 24
        h = (now or dt.datetime.now()).hour
        if start == end:
            return False
        if start < end:
            return start <= h < end
        return h >= start or h < end

    @property
    def day_reset_hour(self) -> int:
        return int(self._data.get("day_reset_hour", 4))

    @property
    def defer_for_games(self) -> list:
        return list(self._data.get("defer_for_games") or [])

    @property
    def game_defer_grace_seconds(self) -> int:
        return int(self._data.get("game_defer_grace_seconds", 180))

    @property
    def defer_for_claude(self) -> bool:
        return bool(self._data.get("defer_for_claude", True))

    @property
    def claude_active_window_seconds(self) -> int:
        return int(self._data.get("claude_active_window_seconds", 300))

    def logical_date(self, now: dt.datetime | None = None) -> str:
        """The usage 'day' key. The day rolls over at day_reset_hour (04:00 by
        default), so time before then still counts toward the previous day."""
        now = now or dt.datetime.now()
        return (now - dt.timedelta(hours=self.day_reset_hour)).date().isoformat()

    @property
    def dry_run(self) -> bool:
        return bool(self._data.get("dry_run", True))

    @property
    def setup_completed(self) -> bool:
        return bool(self._data.get("setup_completed", False))

    # Keys the first-run wizard may set directly. Initial setup establishes the
    # baseline, so it bypasses the weakening cooldown (there's nothing to weaken
    # from yet).
    _SETUP_KEYS = frozenset({
        "daily_cap_minutes", "hard_cutoff_time", "warning_minutes_before",
        "grace_seconds", "idle_threshold_seconds", "edit_cooldown_hours",
        "late_night_hour", "day_reset_hour", "dry_run",
    })

    def complete_setup(self, values: dict) -> None:
        with self._lock:
            vals = values or {}
            for key, value in vals.items():
                if key in self._SETUP_KEYS:
                    self._data[key] = value
            # The wizard sets one baseline cap/cutoff; apply it to every day so
            # the per-day schedule starts uniform (users tune weekends later).
            if "daily_cap_minutes" in vals:
                for d in _DAYS:
                    self._data[f"cap_{d}"] = self._data["daily_cap_minutes"]
            if "hard_cutoff_time" in vals:
                for d in _DAYS:
                    self._data[f"cutoff_{d}"] = self._data["hard_cutoff_time"]
            self._data["setup_completed"] = True
            self.save()

    def remaining_seconds(self, state) -> float:
        return max(0.0, self.daily_cap_seconds - state.used_seconds)

    def cutoff_remaining_seconds(self, now: dt.datetime | None = None):
        now = now or dt.datetime.now()
        key = f"cutoff_{_DAYS[self.logical_weekday(now)]}"
        t = self._data.get(key, self._data.get("hard_cutoff_time"))
        if not t:
            return None
        h, m = map(int, t.split(":"))
        # The cutoff belongs to the current logical day. An after-midnight
        # cutoff (hour < day_reset_hour, e.g. 01:30) lands on the *next*
        # calendar date but still caps the same logical (Fri) night.
        d = dt.date.fromisoformat(self.logical_date(now))
        if h < self.day_reset_hour:
            d = d + dt.timedelta(days=1)
        cutoff = dt.datetime(d.year, d.month, d.day, h, m)
        return max(0.0, (cutoff - now).total_seconds())

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

    def _logical_cutoff_minute(self, hhmm: str) -> int:
        """Minutes from the day reset to this cutoff, wrapping past midnight, so
        a later night (01:30 with a 04:00 reset) sorts after an earlier one."""
        return (_hhmm_to_min(hhmm) - self.day_reset_hour * 60) % (24 * 60)

    def _cutoff_weakens(self, old, new) -> bool:
        if new is None and old is not None:
            return True  # removing the cutoff drops a limit → weakening
        if old is None or new is None:
            return False  # adding a cutoff is a tightening
        return self._logical_cutoff_minute(new) > self._logical_cutoff_minute(old)

    def _weakens(self, key: str, old, new) -> bool:
        if key == "hard_cutoff_time" or key.startswith("cutoff_"):
            return self._cutoff_weakens(old, new)
        fn = WEAKENING.get(key)
        return bool(fn and fn(old, new))

    def apply_settings(self, new: dict) -> tuple[list[str], list[str]]:
        """Apply a dict of settings. Tightening changes take effect immediately;
        weakening changes are deferred by edit_cooldown_hours. Returns
        (applied_descriptions, deferred_descriptions)."""
        applied: list[str] = []
        deferred: list[str] = []
        rejected: list[str] = []
        committed = self.is_committed()
        # A bare daily_cap_minutes / hard_cutoff_time means "set every day" — it
        # expands to the per-day keys (an explicit cap_<day> in the same call
        # wins). This keeps onboarding and legacy callers working now that the
        # per-day schedule is the source of truth.
        new = dict(new)
        if "daily_cap_minutes" in new:
            v = new.pop("daily_cap_minutes")
            for d in _DAYS:
                new.setdefault(f"cap_{d}", v)
        if "hard_cutoff_time" in new:
            v = new.pop("hard_cutoff_time")
            for d in _DAYS:
                new.setdefault(f"cutoff_{d}", v)
        with self._lock:
            pending = dict(self._data.get("pending_changes") or {})

            # Always use the CURRENT cooldown for deferrals so lowering the
            # cooldown (itself a weakening) can't shorten its own deferral.
            cooldown_hours = int(self._data["edit_cooldown_hours"])
            effective_at = (dt.datetime.now() + dt.timedelta(hours=cooldown_hours)).isoformat()

            for key, value in new.items():
                old = self._data.get(key)
                pend = pending.get(key)
                # Already the effective value with nothing queued → nothing to do.
                if value == old and pend is None:
                    continue
                # Already queued to exactly this value → leave the running timer
                # alone. Re-submitting the whole form (which shows queued values)
                # must be idempotent — not re-defer or, worse, cancel the change.
                if pend is not None and pend.get("value") == value:
                    continue
                if self._weakens(key, old, value):
                    if committed:
                        # Locked in: weakening is refused outright, not queued.
                        rejected.append(f"{key}: {old} → {value}")
                        continue
                    pending[key] = {"value": value, "effective_at": effective_at}
                    deferred.append(f"{key}: {old} → {value}")
                else:
                    self._data[key] = value
                    pending.pop(key, None)
                    applied.append(f"{key}: {old} → {value}")

            self._data["pending_changes"] = pending
            self.save()
        return applied, deferred, rejected

    # ───────── disarm: the one sanctioned stop (cooldown-gated) ─────────
    @property
    def disarm_at(self):
        return self._data.get("disarm_at")

    def request_disarm(self) -> str:
        """Schedule a disarm for edit_cooldown_hours from now. Until then the lock
        keeps running (and resurrecting); once due, everything stops."""
        with self._lock:
            at = (dt.datetime.now() + dt.timedelta(hours=self.edit_cooldown_hours)).isoformat()
            self._data["disarm_at"] = at
            self.save()
        return at

    def cancel_disarm(self) -> None:
        """Cancel a pending disarm, or re-arm after one matured."""
        with self._lock:
            self._data["disarm_at"] = None
            self.save()

    def disarm_due(self, now: "dt.datetime | None" = None) -> bool:
        if self.is_committed(now):
            return False  # a commitment can't be lifted early, even a stale disarm
        at = self._data.get("disarm_at")
        if not at:
            return False
        try:
            return (now or dt.datetime.now()) >= dt.datetime.fromisoformat(at)
        except (TypeError, ValueError):
            return False

    def disarm_remaining_seconds(self, now: "dt.datetime | None" = None):
        at = self._data.get("disarm_at")
        if not at:
            return None
        try:
            return max(0.0, (dt.datetime.fromisoformat(at) - (now or dt.datetime.now())).total_seconds())
        except (TypeError, ValueError):
            return None

    # ───────── commitment ("lock in"): a fixed term you can't lift early ─────────
    @property
    def commit_until(self):
        return self._data.get("commit_until")

    def is_committed(self, now: "dt.datetime | None" = None) -> bool:
        # The dev build never enforces commitments (see hard_lock/build.py).
        from . import build
        if build.DEV_BUILD:
            return False
        at = self._data.get("commit_until")
        if not at:
            return False
        try:
            return (now or dt.datetime.now()) < dt.datetime.fromisoformat(at)
        except (TypeError, ValueError):
            return False

    def commit_remaining_seconds(self, now: "dt.datetime | None" = None):
        at = self._data.get("commit_until")
        if not at:
            return None
        try:
            return max(0.0, (dt.datetime.fromisoformat(at) - (now or dt.datetime.now())).total_seconds())
        except (TypeError, ValueError):
            return None

    def commit(self, duration_seconds) -> str:
        """Lock in for a term. Extend-only: never shortens an existing
        commitment. Committing is a tightening, so it applies instantly; it also
        drops any pending disarm and any queued weakening changes (they can't
        benefit you during the term)."""
        try:
            secs = int(duration_seconds)
        except (TypeError, ValueError):
            secs = 0
        secs = max(60, min(secs, 10 * 365 * 24 * 3600))  # 1 min … ~10 years
        with self._lock:
            end = dt.datetime.now() + dt.timedelta(seconds=secs)
            current = self._data.get("commit_until")
            if current:
                try:
                    end = max(end, dt.datetime.fromisoformat(current))
                except (TypeError, ValueError):
                    pass
            self._data["commit_until"] = end.isoformat()
            self._data["disarm_at"] = None       # a pending disarm can't survive
            self._data["pending_changes"] = {}    # queued weakenings are moot now
            self.save()
        return self._data["commit_until"]

    def cancel_pending(self, key: str) -> bool:
        with self._lock:
            pending = dict(self._data.get("pending_changes") or {})
            if key not in pending:
                return False
            pending.pop(key)
            self._data["pending_changes"] = pending
            self.save()
        return True

    def activate_pending(self, key: str) -> bool:
        """Promote a queued change to effective immediately (manual override of
        the cooldown). Returns False if nothing is queued for that key."""
        with self._lock:
            pending = dict(self._data.get("pending_changes") or {})
            entry = pending.pop(key, None)
            if entry is None:
                return False
            self._data[key] = entry["value"]
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
