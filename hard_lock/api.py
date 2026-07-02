"""Bridge object exposed to the pywebview JS side.

The JS code calls these methods via `window.pywebview.api.<name>()`.
The Python side owns the tick loop — every time JS polls `get_status()`
we tick the tracker, accumulate active seconds, save state, and compute
the snapshot the UI needs to render.
"""

from __future__ import annotations

import datetime as dt
import threading


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
    def __init__(self, config, state, tracker, request_grace, open_settings,
                 open_hud=None, session_deadline: "dt.datetime | None" = None):
        self.config = config
        self.state = state
        self.tracker = tracker
        self._request_grace = request_grace
        self._open_settings = open_settings
        self._open_hud = open_hud
        # Wall-clock deadline for the late-night session timer, or None.
        self._session_deadline = session_deadline
        self._warnings_fired: set[int] = set()
        self._grace_requested = False
        # Serializes the poll critical section. pywebview runs each JS→Python
        # call on its own thread, so a slow poll can overlap the next 1s tick;
        # without this, tracker.tick()/accumulate() double-count active time.
        self._poll_lock = threading.Lock()

    def session_remaining_seconds(self) -> "float | None":
        if self._session_deadline is None:
            return None
        return max(0.0, (self._session_deadline - dt.datetime.now()).total_seconds())

    # ───────── late-night session prompt (shown at launch after the hour) ─────────
    def get_session_prompt_info(self) -> dict:
        """Data for the late-night prompt window. The chosen timer can never
        exceed what's already left before the cap/cutoff, so surface that floor.
        Read-only — does not tick the tracker."""
        cap_remaining = self.config.remaining_seconds(self.state)
        cutoff_remaining = self.config.cutoff_remaining_seconds()
        floor = cap_remaining
        if cutoff_remaining is not None:
            floor = min(floor, cutoff_remaining)
        return {
            "max_minutes": max(1, int(floor // 60)),
            "hard_cutoff_time": self.config.hard_cutoff_time,
            "cutoff_remaining_hm": _fmt_hm(cutoff_remaining) if cutoff_remaining is not None else None,
            "late_night_hour": self.config.late_night_hour,
            "grace_seconds": self.config.grace_seconds,
        }

    def start_session_timer(self, minutes) -> dict:
        """Commit to a work window (minutes) and hand off to the HUD."""
        try:
            m = int(minutes)
        except (TypeError, ValueError):
            m = 0
        if m > 0:
            self._session_deadline = dt.datetime.now() + dt.timedelta(minutes=m)
        if self._open_hud:
            self._open_hud()
        return {"ok": True}

    def skip_session_timer(self) -> dict:
        """Dismiss the prompt with no extra limit; normal cap/cutoff still apply."""
        if self._open_hud:
            self._open_hud()
        return {"ok": True}

    # ───────── called from HUD / settings on every poll ─────────
    def get_status(self) -> dict:
        # The mutating critical section (tick/accumulate/save + warning/grace
        # state) is serialized so overlapping polls can't double-count time or
        # double-fire. The read-only snapshot is built afterwards from locals.
        with self._poll_lock:
            # Activate any queued weakening changes that have come due, so they
            # apply to this running instance rather than waiting for a restart.
            self.config.refresh_pending()

            if not self._grace_requested:
                delta = self.tracker.tick()
                self.state.accumulate(delta)
                self.state.save()

            cap_remaining = self.config.remaining_seconds(self.state)
            cutoff_remaining = self.config.cutoff_remaining_seconds()
            session_remaining = self.session_remaining_seconds()

            # Effective time is the tightest of every active limit. The session
            # timer only ever shortens this — never extends past cap/cutoff.
            effective = cap_remaining
            for limit in (cutoff_remaining, session_remaining):
                if limit is not None:
                    effective = min(effective, limit)

            self._maybe_fire_warnings(effective)

            if not self._grace_requested and effective <= self.config.grace_seconds:
                self._grace_requested = True
                self._request_grace()

            used_seconds = self.state.used_seconds

        cap_seconds = self.config.daily_cap_seconds
        used_pct = 0 if cap_seconds == 0 else min(100, 100 * used_seconds / cap_seconds)

        return {
            "remaining_seconds": effective,
            "remaining_clock": _fmt_clock(effective),
            "remaining_hm": _fmt_hm(effective),
            "cap_remaining_seconds": cap_remaining,
            "cutoff_remaining_seconds": cutoff_remaining,
            "cutoff_remaining_hm": _fmt_hm(cutoff_remaining) if cutoff_remaining is not None else None,
            "hard_cutoff_time": self.config.hard_cutoff_time,
            "session_remaining_seconds": session_remaining,
            "session_remaining_hm": _fmt_hm(session_remaining) if session_remaining is not None else None,
            "session_active": session_remaining is not None,
            "used_seconds": used_seconds,
            "used_hm": _fmt_hm(used_seconds),
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
            "late_night_hour": self.config.late_night_hour,
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
