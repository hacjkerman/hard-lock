"""Bridge object exposed to the pywebview JS side.

The JS code calls these methods via `window.pywebview.api.<name>()`.
The Python side owns the tick loop — every time JS polls `get_status()`
we tick the tracker, accumulate active seconds, save state, and compute
the snapshot the UI needs to render.
"""

from __future__ import annotations

import datetime as dt
import threading
import time


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
                 open_hud=None, session_deadline: "dt.datetime | None" = None,
                 event_log=None, day_history=None, open_history=None, hide_hud=None,
                 open_session_prompt=None, league_active=None, on_game_change=None,
                 re_arm=None):
        self.config = config
        self.state = state
        self.tracker = tracker
        self._request_grace = request_grace
        self._open_settings = open_settings
        self._open_hud = open_hud
        self._open_history = open_history
        self._hide_hud = hide_hud
        self._open_session_prompt = open_session_prompt
        # Called with True when a defer-for game starts holding, False when it
        # releases — the app uses it to auto-hide the HUD during a game.
        self._on_game_change = on_game_change
        # Re-arm from the dormant (disarmed) state: relaunch enforcing.
        self._re_arm = re_arm
        self._event_log = event_log
        self._day_history = day_history
        # Wall-clock deadline for the session timer, or None. A manual (on-demand)
        # close overrides cap/cutoff; the automatic late-night prompt stays
        # bounded (can only shorten). _manual_prompt marks that the NEXT prompt
        # was opened on demand; _session_override marks the active timer as
        # authoritative (it decides the shutdown time on its own).
        self._session_deadline = session_deadline
        self._manual_prompt = False
        self._session_override = False
        # Detects whether a "don't shut down mid-game" process is running.
        self._league_active = league_active
        self._league_last_active: "float | None" = None
        self._league_checked_at: "float | None" = None
        self._shutdown_held = False
        self._game_defer_prev = False
        # Dry-run reached the limit at least once (so we don't re-log every tick).
        self._dry_run_fired = False
        self._warnings_fired: set[int] = set()
        self._grace_requested = False
        # Serializes the poll critical section. pywebview runs each JS→Python
        # call on its own thread, so a slow poll can overlap the next 1s tick;
        # without this, tracker.tick()/accumulate() double-count active time.
        self._poll_lock = threading.Lock()
        # Archive a finished day (and reset the counter) if we launched into a
        # new logical day since the last run.
        self._roll_day()

    def session_remaining_seconds(self) -> "float | None":
        if self._session_deadline is None:
            return None
        return max(0.0, (self._session_deadline - dt.datetime.now()).total_seconds())

    # ───────── day rollover + history ─────────
    def _roll_day(self) -> None:
        """If the logical day changed, archive the day that ended and reset the
        counter. Called from __init__ and (under the poll lock) each poll."""
        today = self.config.logical_date()
        if self.state.date == today:
            return
        if self.state.date is not None:
            # Use the cap that governed the ended day, not whatever it is now.
            cap_minutes = self.state.cap_minutes
            if cap_minutes is None:
                cap_minutes = self.config.daily_cap_minutes
            summary = {
                "date": self.state.date,
                "active_seconds": round(self.state.used_seconds, 1),
                "cap_minutes": cap_minutes,
                "hit_cap": self.state.used_seconds >= cap_minutes * 60,
            }
            if self._day_history is not None:
                self._day_history.append_day(summary)
            if self._event_log is not None:
                self._event_log.append("day_rollover", **summary)
        self.state.roll_to(today, self.config.daily_cap_minutes)
        self._warnings_fired.clear()

    def _log(self, event_type: str, **detail) -> None:
        if self._event_log is not None:
            self._event_log.append(event_type, **detail)

    def _log_shutdown(self, cap_r, cutoff_r, session_r) -> None:
        reason, tightest = "cap", cap_r
        if cutoff_r is not None and cutoff_r <= tightest:
            reason, tightest = "cutoff", cutoff_r
        if session_r is not None and session_r <= tightest:
            reason, tightest = "session", session_r
        self._log("shutdown", reason=reason, dry_run=self.config.dry_run,
                  used_seconds=round(self.state.used_seconds, 1))

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
        # A manual close overrides cap/cutoff, so it isn't bounded by the floor —
        # offer a full range. The bounded late-night prompt caps at the floor.
        manual = self._manual_prompt
        max_minutes = 480 if manual else max(1, int(floor // 60))
        return {
            "manual": manual,
            "max_minutes": max_minutes,
            "hard_cutoff_time": self.config.hard_cutoff_time,
            "cutoff_remaining_hm": _fmt_hm(cutoff_remaining) if cutoff_remaining is not None else None,
            "late_night_hour": self.config.late_night_hour,
            "grace_seconds": self.config.grace_seconds,
            "is_late_night": self.config.is_late_night(),
        }

    def start_session_timer(self, minutes, override=False) -> dict:
        """Commit to a work window (minutes) and hand off to the HUD. override=True
        (a manual close) makes the timer authoritative — it decides the shutdown
        time even past the cap/cutoff."""
        try:
            m = int(minutes)
        except (TypeError, ValueError):
            m = 0
        if m > 0:
            self._session_deadline = dt.datetime.now() + dt.timedelta(minutes=m)
            self._session_override = bool(override)
            self._log("session_timer", minutes=m, override=bool(override))
        self._manual_prompt = False
        if self._open_hud:
            self._open_hud()
        return {"ok": True}

    def skip_session_timer(self) -> dict:
        """Dismiss the prompt with no extra limit; normal cap/cutoff still apply."""
        self._manual_prompt = False
        if self._open_hud:
            self._open_hud()
        return {"ok": True}

    # ───────── the clock: owned by a single background thread ─────────
    def _limits(self):
        return (
            self.config.remaining_seconds(self.state),
            self.config.cutoff_remaining_seconds(),
            self.session_remaining_seconds(),
        )

    @staticmethod
    def _effective_from(cap_remaining, cutoff_remaining, session_remaining) -> float:
        # Tightest of every active limit. A bounded session timer only ever
        # shortens this — it never extends past cap/cutoff.
        effective = cap_remaining
        for limit in (cutoff_remaining, session_remaining):
            if limit is not None:
                effective = min(effective, limit)
        return effective

    def _effective(self, cap_remaining, cutoff_remaining, session_remaining) -> float:
        # A manual close timer is authoritative: the user deliberately chose when
        # the machine shuts down, so it overrides cap/cutoff (even to extend).
        if self._session_override and session_remaining is not None:
            return session_remaining
        return self._effective_from(cap_remaining, cutoff_remaining, session_remaining)

    def _track_league(self) -> None:
        """Note when a defer-for game was last seen running (throttled). Keeps
        _league_last_active current so a game that ends just before the cutoff
        still holds the shutdown for the full buffer."""
        games = self.config.defer_for_games
        if not games or self._league_active is None:
            return
        now = time.monotonic()
        if self._league_checked_at is not None and now - self._league_checked_at < 5.0:
            return  # check at most every ~5s; the buffer (minutes) tolerates this
        self._league_checked_at = now
        try:
            if self._league_active(games):
                self._league_last_active = now
        except Exception:
            pass

    def _deferred_for_game(self) -> bool:
        """True while a defer-for game is running or ended within the buffer."""
        if not self.config.defer_for_games or self._league_last_active is None:
            return False
        return (time.monotonic() - self._league_last_active) < self.config.game_defer_grace_seconds

    def tick(self) -> None:
        """Advance the clock once: accumulate active time, fire warnings, and
        trigger the grace/shutdown when time runs out. Driven by a single
        background thread (see __main__) so tracking continues even when the HUD
        is hidden to the tray. Serialized with settings writes via the lock."""
        with self._poll_lock:
            if self._grace_requested:
                return
            # Roll to a new logical day (archiving the finished one) first.
            self._roll_day()
            # Activate any queued weakening changes that have come due.
            self.config.refresh_pending()
            # Keep today's cap snapshot current so the archive reflects the cap
            # actually in force (it may have been tightened mid-day).
            self.state.cap_minutes = self.config.daily_cap_minutes

            delta = self.tracker.tick()
            self.state.accumulate(delta)
            self.state.save()
            self._track_league()

            cap_remaining, cutoff_remaining, session_remaining = self._limits()
            effective = self._effective(cap_remaining, cutoff_remaining, session_remaining)
            deferred = self._deferred_for_game()
            # Tell the app when a game starts/stops holding (→ auto-hide the HUD).
            if deferred != self._game_defer_prev:
                self._game_defer_prev = deferred
                if self._on_game_change:
                    try:
                        self._on_game_change(deferred)
                    except Exception:
                        pass
            # While a game holds the shutdown, a "N minutes left" warning would be
            # a lie (nothing is going to shut down) AND could pop over the game —
            # so fire warnings only when the shutdown is actually imminent.
            if not deferred:
                self._maybe_fire_warnings(effective)
            if effective <= self.config.grace_seconds:
                # Don't cut off a game in progress — hold until it ends + buffer.
                if deferred:
                    if not self._shutdown_held:
                        self._shutdown_held = True
                        self._log("shutdown_held", reason="game")
                    return
                self._shutdown_held = False
                if self.config.dry_run:
                    # Dry-run must NOT tear down the app / exit — otherwise once
                    # you're past the limit you can never reach Settings to turn
                    # dry-run off. Register the (simulated) shutdown once and keep
                    # running so the app stays fully usable.
                    if not self._dry_run_fired:
                        self._dry_run_fired = True
                        self._log_shutdown(cap_remaining, cutoff_remaining, session_remaining)
                    return
                self._grace_requested = True
                self._log_shutdown(cap_remaining, cutoff_remaining, session_remaining)
                self._request_grace()
            else:
                self._shutdown_held = False
                self._dry_run_fired = False

    def _bar_metrics(self, cap_remaining, cutoff_remaining, session_remaining,
                     used_seconds, cap_seconds) -> dict:
        """The HUD bar shows time-until-shutdown as a fraction of the daily cap
        (the '8h full day' reference), so it depletes in step with the big
        countdown. The label names whichever limit is currently nearest."""
        limits = [("cap", cap_remaining)]
        if cutoff_remaining is not None:
            limits.append(("cutoff", cutoff_remaining))
        if session_remaining is not None:
            limits.append(("session", session_remaining))
        name, remaining = min(limits, key=lambda pair: pair[1])
        pct = 100.0 if cap_seconds <= 0 else max(0.0, min(100.0, 100.0 * remaining / cap_seconds))
        if name == "cutoff":
            label = f"{_fmt_hm(used_seconds)} used · cutoff {self.config.hard_cutoff_time}"
        elif name == "session":
            label = f"{_fmt_hm(used_seconds)} used · work timer"
        else:
            label = f"{_fmt_hm(used_seconds)} of {_fmt_hm(cap_seconds)} cap used"
        return {"remaining_pct": round(pct, 1), "binding": name, "limit_label": label}

    # ───────── read-only snapshot for the HUD / settings / tray ─────────
    def get_status(self) -> dict:
        cap_remaining, cutoff_remaining, session_remaining = self._limits()
        effective = self._effective(cap_remaining, cutoff_remaining, session_remaining)
        used_seconds = self.state.used_seconds
        cap_seconds = self.config.daily_cap_seconds
        used_pct = 0 if cap_seconds == 0 else min(100, 100 * used_seconds / cap_seconds)
        bar = self._bar_metrics(cap_remaining, cutoff_remaining, session_remaining,
                                used_seconds, cap_seconds)

        return {
            "remaining_seconds": effective,
            "remaining_clock": _fmt_clock(effective),
            "remaining_hm": _fmt_hm(effective),
            "remaining_pct": bar["remaining_pct"],
            "binding": bar["binding"],
            "limit_label": bar["limit_label"],
            "cap_remaining_seconds": cap_remaining,
            "cutoff_remaining_seconds": cutoff_remaining,
            "cutoff_remaining_hm": _fmt_hm(cutoff_remaining) if cutoff_remaining is not None else None,
            "hard_cutoff_time": self.config.hard_cutoff_time,
            "session_remaining_seconds": session_remaining,
            "session_remaining_hm": _fmt_hm(session_remaining) if session_remaining is not None else None,
            "session_active": session_remaining is not None,
            "shutdown_held": self._shutdown_held,
            "dry_run_fired": self._dry_run_fired,
            "disarmed": self.config.disarm_due(),
            "disarm_pending": self.config.disarm_at is not None and not self.config.disarm_due(),
            "disarm_remaining_hm": (
                _fmt_hm(self.config.disarm_remaining_seconds())
                if self.config.disarm_at is not None and not self.config.disarm_due() else None
            ),
            "committed": self.config.is_committed(),
            "commit_until": self.config.commit_until,
            "commit_remaining_hm": (
                _fmt_hm(self.config.commit_remaining_seconds())
                if self.config.is_committed() else None
            ),
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
            "cap_by_day": self.config.cap_by_day(),
            "cutoff_by_day": self.config.cutoff_by_day(),
            "day_keys": self.config.day_keys(),
            "day_labels": self.config.day_labels(),
            "today_index": self.config.logical_weekday(),
            "warning_minutes_before": self.config.warning_minutes_before,
            "grace_seconds": self.config.grace_seconds,
            "idle_threshold_seconds": self.config.idle_threshold_seconds,
            "edit_cooldown_hours": self.config.edit_cooldown_hours,
            "late_night_hour": self.config.late_night_hour,
            "day_reset_hour": self.config.day_reset_hour,
            "dry_run": self.config.dry_run,
            "pending": self._pending_view(),
        }

    @staticmethod
    def _autostart_installed() -> bool:
        try:
            from . import autostart

            return autostart.is_installed()
        except Exception:
            return False

    def set_autostart(self, enabled) -> dict:
        """Turn 'start at logon' on/off. Installing/removing the Task Scheduler
        task needs admin, so this triggers a UAC prompt; the caller re-queries
        get_autostart_status() afterwards to reflect the real state."""
        from . import autostart

        try:
            triggered = autostart.install_elevated() if enabled else autostart.uninstall_elevated()
        except Exception:
            triggered = False
        self._log("autostart", enabled=bool(enabled), triggered=triggered)
        return {"triggered": triggered, "installed": self._autostart_installed()}

    def get_autostart_status(self) -> dict:
        return {"installed": self._autostart_installed()}

    def apply_settings(self, new: dict) -> dict:
        applied, deferred, rejected = self.config.apply_settings(new)
        if applied or deferred or rejected:
            self._log("settings", applied=applied, deferred=deferred, rejected=rejected)
        return {
            "applied": applied,
            "deferred": deferred,
            "rejected": rejected,
            "pending": self._pending_view(),
        }

    def cancel_pending(self, key: str) -> dict:
        ok = self.config.cancel_pending(key)
        if ok:
            self._log("pending_cancelled", key=key)
        return {"ok": ok, "pending": self._pending_view()}

    def activate_pending(self, key: str) -> dict:
        """Manual override: apply a queued change now instead of after cooldown."""
        ok = self.config.activate_pending(key)
        if ok:
            self._log("pending_activated", key=key)
        return {"ok": ok, "pending": self._pending_view()}

    # ───────── disarm (the sanctioned, cooldown-gated stop) ─────────
    def request_disarm(self) -> dict:
        if self.config.is_committed():
            return {"ok": False, "committed": True,
                    "commit_remaining_hm": _fmt_hm(self.config.commit_remaining_seconds() or 0)}
        at = self.config.request_disarm()
        self._log("disarm_requested", effective_at=at)
        return {"ok": True, "disarm_at": at,
                "disarm_remaining_hm": _fmt_hm(self.config.disarm_remaining_seconds() or 0)}

    def commit(self, duration_seconds) -> dict:
        """Lock in for a fixed term (extend-only). Can't be undone before it ends."""
        at = self.config.commit(duration_seconds)
        self._log("committed", commit_until=at)
        return {"ok": True, "commit_until": at,
                "commit_remaining_hm": _fmt_hm(self.config.commit_remaining_seconds() or 0)}

    def cancel_disarm(self) -> dict:
        self.config.cancel_disarm()
        self._log("disarm_cancelled")
        return {"ok": True}

    def re_arm(self) -> dict:
        """Leave the dormant state and start enforcing again."""
        self.config.cancel_disarm()
        self._log("re_armed")
        if self._re_arm:
            self._re_arm()
        return {"ok": True}

    def open_settings(self) -> None:
        self._open_settings()

    def open_history(self) -> None:
        if self._open_history:
            self._open_history()

    def open_session_prompt(self) -> None:
        """Open the 'set a work timer' prompt on demand (any time, not just at
        the late-night launch). On-demand = a manual close that overrides the
        cap/cutoff; the automatic late-night prompt (opened at launch, not via
        this method) stays bounded."""
        self._manual_prompt = True
        if self._open_session_prompt:
            self._open_session_prompt()

    def hide_hud(self) -> None:
        """Hide the HUD to the tray (the app keeps running in the background)."""
        if self._hide_hud:
            self._hide_hud()

    # ───────── first-run onboarding ─────────
    def get_onboarding_info(self) -> dict:
        return {
            "daily_cap_minutes": self.config.daily_cap_minutes,
            "hard_cutoff_time": self.config.hard_cutoff_time,
            "late_night_hour": self.config.late_night_hour,
            "dry_run": self.config.dry_run,
        }

    def finish_onboarding(self, payload: dict) -> dict:
        """Persist the wizard's choices, mark setup complete, optionally install
        the logon task, and hand off to the HUD."""
        values = payload or {}

        def _int(v, default):
            try:
                return int(v)
            except (TypeError, ValueError):
                return default

        settings: dict = {}
        if "daily_cap_minutes" in values:
            settings["daily_cap_minutes"] = max(1, _int(values["daily_cap_minutes"], self.config.daily_cap_minutes))
        if "hard_cutoff_time" in values:
            t = values["hard_cutoff_time"]
            settings["hard_cutoff_time"] = t or None
        if "late_night_hour" in values:
            settings["late_night_hour"] = min(24, max(0, _int(values["late_night_hour"], self.config.late_night_hour)))
        if "dry_run" in values:
            settings["dry_run"] = bool(values["dry_run"])

        self.config.complete_setup(settings)
        self._log("onboarding_completed", **settings)

        autostart_result = None
        if values.get("autostart"):
            try:
                from . import autostart

                ok, msg = autostart.install()
                autostart_result = {"ok": ok, "message": msg}
            except Exception as exc:  # noqa: BLE001
                autostart_result = {"ok": False, "message": str(exc)}

        # The wizard shows any autostart failure before entering the app; it
        # calls enter_app() to hand off to the HUD.
        return {"ok": True, "autostart": autostart_result}

    def enter_app(self) -> None:
        """Leave the onboarding / prompt and open the HUD."""
        if self._open_hud:
            self._open_hud()

    # ───────── internals ─────────
    def _maybe_fire_warnings(self, effective: float) -> None:
        for w in sorted(self.config.warning_minutes_before, reverse=True):
            if w not in self._warnings_fired and effective <= w * 60:
                self._warnings_fired.add(w)
                self._log("warning", minutes=w, remaining_seconds=round(effective, 1))

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

    # ───────── history view ─────────
    def get_history(self, days: int = 42) -> dict:
        # Archive a just-finished day before rendering (the history window polls
        # on its own timer, independent of the HUD). Serialize with the poll
        # loop so the two can't roll concurrently; do the heavy file reads after.
        with self._poll_lock:
            self._roll_day()
            today = self.config.logical_date()
            today_active = self.state.used_seconds if self.state.date == today else 0.0

        cap_minutes = self.config.daily_cap_minutes
        by_date = self._day_history.by_date() if self._day_history is not None else {}
        # Today is in progress — its live counter overrides any stale archive.
        by_date[today] = {"date": today, "active_seconds": today_active, "cap_minutes": cap_minutes}

        # Read the event log once; derive both shutdown days and the recent feed.
        events = self._event_log.all() if self._event_log is not None else []
        shutdown_dates = set()
        for ev in events:
            if ev.get("type") == "shutdown":
                ld = self._logical_date_of(ev.get("ts"))
                if ld:
                    shutdown_dates.add(ld)

        base = dt.date.fromisoformat(today)
        window = []
        for i in range(days - 1, -1, -1):
            d = (base - dt.timedelta(days=i)).isoformat()
            s = by_date.get(d)
            active = float(s["active_seconds"]) if s else 0.0
            cap_sec = (int(s["cap_minutes"]) if s and "cap_minutes" in s else cap_minutes) * 60
            window.append({
                "date": d,
                "active_seconds": active,
                "active_hm": _fmt_hm(active),
                "active_hours": round(active / 3600, 3),
                "cap_hours": round(cap_sec / 3600, 3),
                "has_data": s is not None,
                "hit_cap": bool(s) and cap_sec > 0 and active >= cap_sec,
                "shutdown": d in shutdown_dates,
            })

        # Streaks only span days that actually have data — a never-used day is
        # neither a success nor counted, so a 2-day-old install can't show "42".
        current = 0
        for day in reversed(window):
            if not day["has_data"] or day["hit_cap"]:
                break
            current += 1
        best = run = 0
        for day in window:
            run = run + 1 if (day["has_data"] and not day["hit_cap"]) else 0
            best = max(best, run)
        data_days = [d for d in window if d["has_data"]]
        avg = sum(d["active_seconds"] for d in data_days) / len(data_days) if data_days else 0.0

        recent = [self._event_view(e) for e in reversed(events[-10:])]
        return {
            "days": window,
            "stats": {
                "current_streak": current,
                "best_streak": best,
                "avg_active_hm": _fmt_hm(avg),
                "shutdowns": sum(1 for d in window if d["shutdown"]),
                "cap_hours": round(cap_minutes * 60 / 3600, 3),
            },
            "events": recent,
        }

    def _logical_date_of(self, ts) -> "str | None":
        if not isinstance(ts, str):
            return None
        try:
            return self.config.logical_date(dt.datetime.fromisoformat(ts))
        except (TypeError, ValueError):
            return None

    def _event_view(self, e: dict) -> dict:
        t = e.get("type")
        ts = e.get("ts", "")
        when = ts.replace("T", " ")[:16] if isinstance(ts, str) else ""
        if t == "shutdown":
            kind = "Dry-run shutdown" if e.get("dry_run") else "Shutdown"
            label = f"{kind} · {e.get('reason', '')} reached"
            tone = "red"
        elif t == "warning":
            label = f"Warning · {e.get('minutes')} min left"
            tone = "amber"
        elif t == "settings":
            applied = e.get("applied") or []
            deferred = e.get("deferred") or []
            parts = []
            if applied:
                parts.append(f"{len(applied)} applied")
            if deferred:
                parts.append(f"{len(deferred)} deferred")
            label = "Settings · " + (", ".join(parts) if parts else "changed")
            tone = "amber" if deferred else "green"
        elif t == "pending_cancelled":
            label = f"Cancelled queued {e.get('key', '')}"
            tone = "neutral"
        elif t == "pending_activated":
            label = f"Activated queued {e.get('key', '')} (skipped cooldown)"
            tone = "amber"
        elif t == "committed":
            label = f"Locked in · until {str(e.get('commit_until', ''))[:16].replace('T', ' ')}"
            tone = "amber"
        elif t == "session_timer":
            label = f"Late-night timer · {e.get('minutes')} min"
            tone = "neutral"
        elif t == "shutdown_test":
            if e.get("held"):
                label = "Shutdown test · held (game running)"
                tone = "neutral"
            else:
                kind = "simulated" if e.get("dry_run") else "REAL"
                label = f"Shutdown test · {kind} ({e.get('grace_seconds')}s grace)"
                tone = "amber"
        elif t == "day_rollover":
            label = f"Day archived · {_fmt_hm(e.get('active_seconds', 0))} active"
            tone = "red" if e.get("hit_cap") else "green"
        else:
            label = str(t or "event")
            tone = "neutral"
        return {"when": when, "label": label, "tone": tone}
