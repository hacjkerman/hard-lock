"""Bridge object exposed to the pywebview JS side.

The JS code calls these methods via `window.pywebview.api.<name>()`.
The Python side owns the tick loop — every time JS polls `get_status()`
we tick the tracker, accumulate active seconds, save state, and compute
the snapshot the UI needs to render.
"""

from __future__ import annotations

import datetime as dt


def _fmt_hm(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h {m:02d}m"


def _fmt_clock(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}"


class Api:
    def __init__(self, config, state, tracker, request_grace, open_settings):
        self.config = config
        self.state = state
        self.tracker = tracker
        self._request_grace = request_grace
        self._open_settings = open_settings
        self._warnings_fired: set[int] = set()
        self._grace_requested = False

    # ───────── called from HUD / settings on every poll ─────────
    def get_status(self) -> dict:
        if not self._grace_requested:
            delta = self.tracker.tick()
            self.state.accumulate(delta)
            self.state.save()

        cap_remaining = self.config.remaining_seconds(self.state)
        cutoff_remaining = self.config.cutoff_remaining_seconds()
        effective = cap_remaining if cutoff_remaining is None else min(cap_remaining, cutoff_remaining)

        self._maybe_fire_warnings(effective)

        if not self._grace_requested and effective <= self.config.grace_seconds:
            self._grace_requested = True
            self._request_grace()

        cap_seconds = self.config.daily_cap_seconds
        used_pct = 0 if cap_seconds == 0 else min(100, 100 * self.state.used_seconds / cap_seconds)

        return {
            "remaining_seconds": effective,
            "remaining_clock": _fmt_clock(effective),
            "remaining_hm": _fmt_hm(effective),
            "cap_remaining_seconds": cap_remaining,
            "cutoff_remaining_seconds": cutoff_remaining,
            "cutoff_remaining_hm": _fmt_hm(cutoff_remaining) if cutoff_remaining is not None else None,
            "hard_cutoff_time": self.config.hard_cutoff_time,
            "used_seconds": self.state.used_seconds,
            "used_hm": _fmt_hm(self.state.used_seconds),
            "used_pct": used_pct,
            "cap_minutes": self.config.daily_cap_minutes,
            "cap_hm": _fmt_hm(cap_seconds),
            "state": self.config.state_for(effective),
            "dry_run": self.config.dry_run,
            "grace_seconds": self.config.grace_seconds,
            "idle_threshold_seconds": self.config.idle_threshold_seconds,
            "edit_cooldown_hours": self.config.edit_cooldown_hours,
            "warning_minutes_before": self.config.warning_minutes_before,
            "pending": self._pending_view(),
            "recent_warnings": sorted(self._warnings_fired, reverse=True),
        }

    def get_settings(self) -> dict:
        return {
            "daily_cap_minutes": self.config.daily_cap_minutes,
            "hard_cutoff_time": self.config.hard_cutoff_time,
            "warning_minutes_before": self.config.warning_minutes_before,
            "grace_seconds": self.config.grace_seconds,
            "idle_threshold_seconds": self.config.idle_threshold_seconds,
            "edit_cooldown_hours": self.config.edit_cooldown_hours,
            "dry_run": self.config.dry_run,
            "pending": self._pending_view(),
        }

    def apply_settings(self, new: dict) -> dict:
        applied, deferred = self.config.apply_settings(new)
        return {
            "applied": applied,
            "deferred": deferred,
            "pending": self._pending_view(),
        }

    def cancel_pending(self, key: str) -> dict:
        ok = self.config.cancel_pending(key)
        return {"ok": ok, "pending": self._pending_view()}

    def open_settings(self) -> None:
        self._open_settings()

    # ───────── internals ─────────
    def _maybe_fire_warnings(self, effective: float) -> None:
        for w in sorted(self.config.warning_minutes_before, reverse=True):
            if w not in self._warnings_fired and effective <= w * 60:
                self._warnings_fired.add(w)

    def _pending_view(self) -> list[dict]:
        pending = self.config._data.get("pending_changes") or {}
        out = []
        now = dt.datetime.now()
        for key, entry in pending.items():
            eff = dt.datetime.fromisoformat(entry["effective_at"])
            remaining = max(0.0, (eff - now).total_seconds())
            out.append({
                "key": key,
                "value": entry["value"],
                "effective_at": entry["effective_at"],
                "effective_at_human": eff.strftime("%a %b %d, %H:%M"),
                "remaining_seconds": remaining,
                "remaining_hm": _fmt_hm(remaining),
            })
        return out
