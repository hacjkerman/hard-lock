# Commitment periods + dev-closable build — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user commit Hard Lock to a fixed term during which it can't be disarmed or weakened, plus a separate compile-time "dev" build that is closable and isolated so it can't defeat a real commitment.

**Architecture:** A `commit_until` timestamp in config drives an `is_committed()` gate; the existing disarm and weakening paths consult that gate (guardian is unchanged because it already keys off `disarm_due()`, which becomes `False` while committed). A single compile-time constant `hard_lock/build.py::DEV_BUILD` (frozen into the binary) switches the app to a closable, guardian-free build with its own `%APPDATA%\HardLockDev` data dir; `is_committed()` short-circuits to `False` in that build.

**Tech Stack:** Python 3.12, stdlib `unittest`, pywebview UI, PyInstaller (onedir), Windows.

## Global Constraints

- Python: run everything with `py -3.12` (not `python`).
- Tests: stdlib `unittest`, no pytest. Full suite: `py -3.12 -m unittest discover -s tests`. Single: `py -3.12 -m unittest tests.test_config.ConfigTestCase.test_name`.
- Windows-only app; `sys.platform == "win32"` assumed.
- Config writes are atomic (temp file + `os.replace`) and a corrupt config must fall back to defaults — never crash at logon. Preserve this.
- `Config` mutations happen under `self._lock` (an `RLock`). Every read-modify-write of `self._data` + `self.save()` stays inside it.
- Commit is **extend-only**: a new commitment never shortens an existing one.
- Frequent commits: one per task minimum, end each task with `git commit`.
- Do not weaken existing behavior; the current 155-test suite must stay green.

---

### Task 1: Config — commitment state + `commit()`

**Files:**
- Modify: `hard_lock/config.py` (add `commit_until` to `DEFAULTS`; add methods near the disarm methods)
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: existing `Config._data`, `Config._lock`, `Config.save()`, `Config.cancel_disarm()`, `Config.edit_cooldown_hours`.
- Produces:
  - `Config.commit_until` (property) → `str | None`
  - `Config.is_committed(now: dt.datetime | None = None) -> bool`
  - `Config.commit_remaining_seconds(now=None) -> float | None`
  - `Config.commit(duration_seconds) -> str` (returns the new ISO `commit_until`; extend-only; clears `disarm_at`; cancels pending weakening changes)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py` (inside `ConfigTestCase`):

```python
    # ───────── commitment ("lock in") ─────────
    def test_not_committed_by_default(self):
        cfg = self._cfg()
        self.assertIsNone(cfg.commit_until)
        self.assertFalse(cfg.is_committed())
        self.assertIsNone(cfg.commit_remaining_seconds())

    def test_commit_sets_future_end_and_is_committed(self):
        cfg = self._cfg()
        cfg.commit(3600)  # 1 hour
        self.assertIsNotNone(cfg.commit_until)
        self.assertTrue(cfg.is_committed())
        self.assertGreater(cfg.commit_remaining_seconds(), 3500)

    def test_commit_is_extend_only(self):
        cfg = self._cfg()
        cfg.commit(3600)
        first = cfg.commit_until
        cfg.commit(60)  # shorter → must NOT shorten the existing commitment
        self.assertEqual(cfg.commit_until, first)
        cfg.commit(7200)  # longer → extends
        self.assertGreater(cfg.commit_until, first)

    def test_commit_clears_pending_disarm(self):
        cfg = self._cfg()
        cfg.request_disarm()
        self.assertIsNotNone(cfg.disarm_at)
        cfg.commit(3600)
        self.assertIsNone(cfg.disarm_at)

    def test_commit_cancels_pending_weakening(self):
        cfg = self._cfg(edit_cooldown_hours=24)
        cfg._data["cap_sat"] = 480
        cfg.apply_settings({"cap_sat": 600})  # weakening → queued
        self.assertIn("cap_sat", cfg._data["pending_changes"])
        cfg.commit(3600)
        self.assertEqual(cfg._data["pending_changes"], {})

    def test_expired_commitment_is_not_committed(self):
        cfg = self._cfg()
        cfg._data["commit_until"] = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        self.assertFalse(cfg.is_committed())
        self.assertEqual(cfg.commit_remaining_seconds(), 0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.12 -m unittest tests.test_config -v`
Expected: FAIL/ERROR — `commit`, `is_committed`, `commit_remaining_seconds`, `commit_until` don't exist.

- [ ] **Step 3: Add `commit_until` to DEFAULTS**

In `hard_lock/config.py`, in the `DEFAULTS` dict, next to `"disarm_at": None,` add:

```python
    # When set (ISO timestamp) and in the future, a fixed-term commitment is
    # active: the lock can't be disarmed or weakened until it passes.
    "commit_until": None,
```

- [ ] **Step 4: Implement the commitment methods**

In `hard_lock/config.py`, immediately after the `disarm_remaining_seconds` method (end of the disarm block), add:

```python
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
            self._data["disarm_at"] = None            # a pending disarm can't survive
            self._data["pending_changes"] = {}         # queued weakenings are moot now
            self.save()
        return self._data["commit_until"]
```

Note: `build` doesn't exist yet — Task 3 creates it. To keep this task green in isolation, also create the module now (Task 3 will formalize it). Add file `hard_lock/build.py` with exactly:

```python
"""Compile-time build flavor. The prod build ships DEV_BUILD = False; the dev
build (build-dev.bat) flips it to True and freezes it into the binary. It is NOT
read from env/argv, so a prod exe can't be switched into dev mode at runtime."""

DEV_BUILD = False
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -3.12 -m unittest tests.test_config -v`
Expected: PASS (all commitment tests green; existing tests still pass).

- [ ] **Step 6: Commit**

```bash
git add hard_lock/config.py hard_lock/build.py tests/test_config.py
git commit -m "Config: commitment (commit_until) — extend-only lock-in state"
```

---

### Task 2: Config — block disarm & weakening while committed

**Files:**
- Modify: `hard_lock/config.py` (`disarm_due`, `apply_settings`)
- Modify: `hard_lock/api.py` (unpack the new 3-tuple from `apply_settings`)
- Modify: `tests/test_config.py`, `tests/test_api.py` (unpack 3-tuple)
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `Config.is_committed()` (Task 1), existing `Config._weakens`, `Config.apply_settings`.
- Produces:
  - `Config.disarm_due()` returns `False` whenever `is_committed()`.
  - `Config.apply_settings(new) -> tuple[list[str], list[str], list[str]]` — now `(applied, deferred, rejected)`; weakening keys are put in `rejected` (not queued) while committed.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
    def test_disarm_blocked_while_committed(self):
        cfg = self._cfg()
        cfg.commit(3600)
        cfg._data["disarm_at"] = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()
        self.assertFalse(cfg.disarm_due())  # a stale disarm can't fire during a commitment

    def test_weakening_rejected_while_committed(self):
        cfg = self._cfg(edit_cooldown_hours=24)
        cfg._data["cap_sat"] = 480
        cfg.commit(3600)
        applied, deferred, rejected = cfg.apply_settings({"cap_sat": 600})  # raise = weaken
        self.assertEqual(applied, [])
        self.assertEqual(deferred, [])
        self.assertTrue(rejected)
        self.assertEqual(cfg._data["cap_sat"], 480)                 # unchanged
        self.assertNotIn("cap_sat", cfg._data["pending_changes"])   # not even queued

    def test_tightening_still_applies_while_committed(self):
        cfg = self._cfg()
        cfg._data["cap_sat"] = 480
        cfg.commit(3600)
        applied, deferred, rejected = cfg.apply_settings({"cap_sat": 300})  # lower = tighten
        self.assertTrue(applied)
        self.assertEqual(rejected, [])
        self.assertEqual(cfg._data["cap_sat"], 300)
```

Also update the two existing `apply_settings` unpackings that this task's return-type change breaks. Find them:

Run: `py -3.12 -c "import re,glob; [print(f, i+1, l.rstrip()) for f in glob.glob('tests/test_*.py') for i,l in enumerate(open(f, encoding='utf-8')) if 'apply_settings(' in l and '=' in l.split('apply_settings')[0]]"`

For every existing test line of the form `applied, deferred = <cfg>.apply_settings(...)`, change it to `applied, deferred, _ = <cfg>.apply_settings(...)`. (These are in `tests/test_config.py`; e.g. `test_tightening_cap_is_immediate`, `test_weakening_cap_is_deferred`, `test_enabling_dry_run_is_weakening`, `test_weakening_cutoff_later_is_deferred`, `test_earlier_night_cutoff_is_immediate`, `test_later_night_cutoff_is_deferred_even_past_midnight`, `test_reapplying_*`, `test_lowering_one_days_cap_is_immediate`, `test_raising_one_days_cap_is_deferred`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.12 -m unittest tests.test_config -v`
Expected: new tests FAIL (`apply_settings` returns 2 values, `disarm_due` still fires).

- [ ] **Step 3: Gate `disarm_due` on the commitment**

In `hard_lock/config.py`, change `disarm_due` to short-circuit while committed:

```python
    def disarm_due(self, now: "dt.datetime | None" = None) -> bool:
        if self.is_committed(now):
            return False
        at = self._data.get("disarm_at")
        if not at:
            return False
        try:
            return (now or dt.datetime.now()) >= dt.datetime.fromisoformat(at)
        except (TypeError, ValueError):
            return False
```

- [ ] **Step 4: Reject weakening in `apply_settings` while committed**

In `hard_lock/config.py`, in `apply_settings`, initialize a `rejected` list and update the loop + return. Replace the method body's list init and per-key loop and return:

Change the top:
```python
        applied: list[str] = []
        deferred: list[str] = []
        rejected: list[str] = []
        committed = self.is_committed()
```

In the loop, replace the weakening branch:
```python
                if self._weakens(key, old, value):
                    if committed:
                        rejected.append(f"{key}: {old} → {value}")
                        continue
                    pending[key] = {"value": value, "effective_at": effective_at}
                    deferred.append(f"{key}: {old} → {value}")
                else:
                    self._data[key] = value
                    pending.pop(key, None)
                    applied.append(f"{key}: {old} → {value}")
```

Change the return:
```python
            self._data["pending_changes"] = pending
            self.save()
        return applied, deferred, rejected
```

- [ ] **Step 5: Update the production caller in `api.py`**

In `hard_lock/api.py`, `apply_settings`:

```python
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
```

Also update the legacy tkinter caller so it doesn't crash if ever used — `hard_lock/ui.py`, `SettingsWindow._apply`: change `applied, deferred = self.config.apply_settings(new)` to `applied, deferred, _rejected = self.config.apply_settings(new)`.

- [ ] **Step 6: Run the full suite**

Run: `py -3.12 -m unittest discover -s tests`
Expected: OK (all green, including updated unpackings).

- [ ] **Step 7: Commit**

```bash
git add hard_lock/config.py hard_lock/api.py hard_lock/ui.py tests/
git commit -m "Config: block disarm + reject weakening while committed"
```

---

### Task 3: `DEV_BUILD` flag + `paths.data_dir` split

**Files:**
- Already created: `hard_lock/build.py` (Task 1) — confirm contents.
- Modify: `hard_lock/paths.py` (`data_dir`)
- Test: `tests/test_paths.py` (create)

**Interfaces:**
- Consumes: `hard_lock.build.DEV_BUILD`, existing `paths.is_frozen()`, `paths.APP_NAME`.
- Produces: `paths.data_dir()` → `%APPDATA%\HardLockDev` when frozen **and** `DEV_BUILD`, else `%APPDATA%\HardLock` (frozen) / repo root (source).

- [ ] **Step 1: Write the failing test**

Create `tests/test_paths.py`:

```python
import os
import unittest
from pathlib import Path
from unittest import mock

from hard_lock import paths


class DataDirTestCase(unittest.TestCase):
    def test_frozen_prod_uses_hardlock(self):
        with mock.patch.object(paths, "is_frozen", return_value=True), \
             mock.patch("hard_lock.build.DEV_BUILD", False), \
             mock.patch.dict(os.environ, {"APPDATA": str(Path.cwd())}):
            self.assertEqual(paths.data_dir().name, "HardLock")

    def test_frozen_dev_uses_hardlockdev(self):
        with mock.patch.object(paths, "is_frozen", return_value=True), \
             mock.patch("hard_lock.build.DEV_BUILD", True), \
             mock.patch.dict(os.environ, {"APPDATA": str(Path.cwd())}):
            self.assertEqual(paths.data_dir().name, "HardLockDev")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3.12 -m unittest tests.test_paths -v`
Expected: FAIL — dev case still returns `HardLock`.

- [ ] **Step 3: Split `data_dir`**

In `hard_lock/paths.py`, replace `data_dir`:

```python
def data_dir() -> Path:
    """Directory holding config.json / state.json. Created if missing. The dev
    build (build.DEV_BUILD) uses a separate HardLockDev dir so it can never read
    or clobber the committed prod install's config."""
    from . import build

    if is_frozen():
        name = "HardLockDev" if build.DEV_BUILD else APP_NAME
        base = Path(os.environ.get("APPDATA") or Path.home()) / name
    else:
        base = Path(__file__).resolve().parent.parent  # repo root
    base.mkdir(parents=True, exist_ok=True)
    return base
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3.12 -m unittest tests.test_paths -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hard_lock/paths.py hard_lock/build.py tests/test_paths.py
git commit -m "Add DEV_BUILD flag; dev build uses its own data dir"
```

---

### Task 4: Api — `commit`, status fields, disarm refusal

**Files:**
- Modify: `hard_lock/api.py` (`commit`, `get_status`, `request_disarm`, `_event_view`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Config.commit`, `Config.is_committed`, `Config.commit_remaining_seconds`, `Config.commit_until`, existing `_fmt_hm`, `_log`.
- Produces:
  - `Api.commit(duration_seconds) -> dict` (`{"ok": True, "commit_until": ...}`)
  - `Api.get_status()` gains `committed` (bool), `commit_until` (str|None), `commit_remaining_hm` (str|None).
  - `Api.request_disarm()` is a no-op returning `{"ok": False, "committed": True, ...}` while committed.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py` (near the disarm tests):

```python
    def test_commit_sets_committed_status(self):
        api, config, _ = make()
        api.commit(3600)
        s = api.get_status()
        self.assertTrue(s["committed"])
        self.assertIsNotNone(s["commit_until"])
        self.assertIsNotNone(s["commit_remaining_hm"])

    def test_request_disarm_refused_while_committed(self):
        api, config, _ = make()
        api.commit(3600)
        res = api.request_disarm()
        self.assertFalse(res["ok"])
        self.assertTrue(res.get("committed"))
        self.assertIsNone(config.disarm_at)  # no disarm scheduled
        self.assertFalse(api.get_status()["disarm_pending"])

    def test_request_disarm_works_when_not_committed(self):
        api, config, _ = make({"edit_cooldown_hours": 24})
        res = api.request_disarm()
        self.assertTrue(res["ok"])
        self.assertIsNotNone(config.disarm_at)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.12 -m unittest tests.test_api -v`
Expected: FAIL — `commit` missing; `request_disarm` still schedules while committed.

- [ ] **Step 3: Implement `commit` + guard `request_disarm`**

In `hard_lock/api.py`, replace `request_disarm` and add `commit` next to it:

```python
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
```

- [ ] **Step 4: Add status fields**

In `hard_lock/api.py`, `get_status`, in the returned dict next to the disarm fields, add:

```python
            "committed": self.config.is_committed(),
            "commit_until": self.config.commit_until,
            "commit_remaining_hm": (
                _fmt_hm(self.config.commit_remaining_seconds())
                if self.config.is_committed() else None
            ),
```

- [ ] **Step 5: Add a history label**

In `hard_lock/api.py`, `_event_view`, next to the `disarm`/`pending_activated` cases add:

```python
        elif t == "committed":
            label = f"Locked in · until {str(e.get('commit_until', ''))[:16].replace('T', ' ')}"
            tone = "amber"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `py -3.12 -m unittest tests.test_api -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add hard_lock/api.py tests/test_api.py
git commit -m "Api: commit(), committed status fields, disarm refused while committed"
```

---

### Task 5: `__main__` + tray — dev build is closable & guardian-free

**Files:**
- Modify: `hard_lock/__main__.py` (skip guardian when `DEV_BUILD`; wire a real quit for dev)
- Modify: `hard_lock/tray.py` (Quit item in dev build; keep Disarm otherwise)
- Test: `tests/test_tray.py`

**Interfaces:**
- Consumes: `hard_lock.build.DEV_BUILD`, existing `tray.build_icon` signature.
- Produces: `tray.build_icon(...)` shows "Quit Hard Lock" when `build.DEV_BUILD` else the cooldown "Disarm" item; `__main__` skips the watchdog/guardian loop and the singleton lock when `DEV_BUILD`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_tray.py`:

```python
    def test_dev_build_shows_quit_not_disarm(self):
        from hard_lock import tray
        with mock.patch("hard_lock.build.DEV_BUILD", True):
            icon = tray.build_icon(FakeApi(), lambda: None, lambda: None, lambda: None, lambda: None)
        labels = [str(i.text) for i in icon.menu if getattr(i, "text", None)]
        self.assertTrue(any("Quit" in x for x in labels))
        self.assertFalse(any("Disarm" in x for x in labels))
```

(`FakeApi` and `mock` are already imported at the top of `tests/test_tray.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3.12 -m unittest tests.test_tray -v`
Expected: FAIL — dev build still shows "Disarm".

- [ ] **Step 3: Branch the tray menu on the build**

In `hard_lock/tray.py`, `build_icon`, replace the final menu item (the disarm item) with a build-aware choice. After building `disarm_label`, change the `menu = pystray.Menu(...)` last item:

```python
    from . import build
    last_item = (
        pystray.MenuItem("Quit Hard Lock", wrap(on_disarm))
        if build.DEV_BUILD
        else pystray.MenuItem(disarm_label, wrap(on_disarm))
    )
    menu = pystray.Menu(
        pystray.MenuItem(status_text, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Show HUD", wrap(on_show_hud), default=True),
        pystray.MenuItem("Open settings", wrap(on_settings)),
        pystray.MenuItem("View history", wrap(on_history)),
        pystray.Menu.SEPARATOR,
        last_item,
    )
    return pystray.Icon("hardlock", make_image(), "Hard Lock", menu)
```

- [ ] **Step 4: Skip the guardian & make quit real in the dev build**

In `hard_lock/__main__.py`, `main()`, guard the guardian/singleton startup and give the dev build a real quit callback.

4a. Near the top of the armed-startup block, where the singleton is acquired and the guardian is spawned, wrap them:

Change
```python
    if not dormant and guardian.acquire_singleton(r"Local\HardLockMain") is None:
        return 0  # another armed instance already owns the lock
```
to
```python
    from . import build
    if not build.DEV_BUILD and not dormant and guardian.acquire_singleton(r"Local\HardLockMain") is None:
        return 0  # another armed instance already owns the lock
```

And change
```python
    if not dormant:
        guardian.write_heartbeat("main")
        threading.Thread(target=tick_loop, name="hardlock-ticker", daemon=True).start()
        guardian.spawn("watchdog")
        threading.Thread(target=guardian_loop, name="hardlock-guardian", daemon=True).start()
```
to
```python
    if not dormant:
        threading.Thread(target=tick_loop, name="hardlock-ticker", daemon=True).start()
        if not build.DEV_BUILD:
            guardian.write_heartbeat("main")
            guardian.spawn("watchdog")
            threading.Thread(target=guardian_loop, name="hardlock-guardian", daemon=True).start()
```

4b. Give the tray a real quit in dev, else the disarm request. Replace the `request_disarm_from_tray` definition + the `tray.start_tray(... on_disarm=request_disarm_from_tray)` call:

```python
    def _tray_stop_action() -> None:
        # Dev build: actually quit. Prod: request the cooldown-gated disarm.
        try:
            if build.DEV_BUILD:
                tick_stop.set()
                _teardown_windows()
            else:
                api.request_disarm()
        except Exception:
            pass

    tray_ref[0] = tray.start_tray(
        api,
        on_show_hud=open_hud,
        on_settings=open_settings,
        on_history=open_history,
        on_disarm=_tray_stop_action,
    )
```

- [ ] **Step 5: Run the tray test + full suite**

Run: `py -3.12 -m unittest tests.test_tray -v`
Expected: PASS.
Run: `py -3.12 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add hard_lock/__main__.py hard_lock/tray.py tests/test_tray.py
git commit -m "Dev build: closable (tray Quit) and no guardian"
```

---

### Task 6: Dev build artifacts (`HardLock-dev.spec`, `build-dev.bat`)

**Files:**
- Create: `HardLock-dev.spec` (copy of `HardLock.spec` renamed to `HardLockDev`)
- Create: `build-dev.bat`

No unit tests — verified by building. This task produces `dist/HardLockDev/HardLockDev.exe`.

- [ ] **Step 1: Create the dev spec**

Create `HardLock-dev.spec` identical to `HardLock.spec` except the two names. Copy `HardLock.spec` and change:
- `name="HardLock",` in `EXE(...)` → `name="HardLockDev",`
- `name="HardLock",` in `COLLECT(...)` → `name="HardLockDev",`

(Leave `datas`, `hiddenimports=["hard_lock.guardian"]`, icon, etc. unchanged.)

- [ ] **Step 2: Create the dev build script**

Create `build-dev.bat`:

```bat
@echo off
REM Build the closable DEV version: flip DEV_BUILD on, build HardLockDev.exe,
REM then restore DEV_BUILD=False so the repo stays prod (committed-capable).
setlocal
copy /y hard_lock\build.py hard_lock\build.py.bak >nul
py -3.12 -c "p='hard_lock/build.py'; s=open(p,encoding='utf-8').read().replace('DEV_BUILD = False','DEV_BUILD = True'); open(p,'w',encoding='utf-8').write(s)"
py -3.12 -m PyInstaller --noconfirm --clean HardLock-dev.spec
copy /y hard_lock\build.py.bak hard_lock\build.py >nul
del hard_lock\build.py.bak >nul 2>&1
echo Done: dist\HardLockDev\HardLockDev.exe  (DEV_BUILD restored to False)
endlocal
```

- [ ] **Step 3: Build and verify (manual)**

Run: `build-dev.bat`
Expected: `dist\HardLockDev\HardLockDev.exe` exists; afterward `hard_lock/build.py` reads `DEV_BUILD = False` again (confirm: `py -3.12 -c "import hard_lock.build as b; print(b.DEV_BUILD)"` prints `False`).

Sanity: launch `dist\HardLockDev\HardLockDev.exe`, confirm (a) only ONE process (no `--watchdog` child), (b) tray shows "Quit Hard Lock", (c) it created `%APPDATA%\HardLockDev`, not touching `%APPDATA%\HardLock`. Quit it from the tray.

- [ ] **Step 4: Commit**

```bash
git add HardLock-dev.spec build-dev.bat
git commit -m "Dev build artifacts: HardLock-dev.spec + build-dev.bat"
```

---

### Task 7: UI — commit status + lock-in controls

**Files:**
- Modify: `hard_lock/webui/hud.html`, `hard_lock/webui/hud.js` (committed banner + "Lock in" button)
- Modify: `hard_lock/webui/settings.html`, `hard_lock/webui/settings.js` (Lock-in / Extend section; show rejected on apply)
- Modify: `hard_lock/webui/onboarding.html`, `hard_lock/webui/onboarding.js` (optional initial commitment)

Browser-verified (no unit tests). Use the preview server (`preview_start name=webui`) and mock `window.pywebview.api` as in existing verifications.

- [ ] **Step 1: HUD — committed banner + Lock-in button**

In `hud.html`, after the `disarmed-note` block, add:

```html
      <div id="committed-note" class="held-note hidden">
        <span class="grow">🔒 Locked in — <span id="committed-until"></span></span>
      </div>
      <button id="lock-in" class="btn sm timer-btn">Lock in a commitment…</button>
```

In `hud.js`, in `render(status)` add:

```js
  const committed = !!status.committed;
  $("committed-note").classList.toggle("hidden", !committed);
  if (committed) $("committed-until").textContent = `${status.commit_remaining_hm} left`;
  $("lock-in").textContent = committed ? "Extend commitment…" : "Lock in a commitment…";
```

In `hud.js` `wire()` add a handler that prompts for a duration and calls `commit`. Use a minimal inline chooser (reuse Settings' control is cleaner, but a quick prompt is acceptable for the HUD):

```js
  $("lock-in").addEventListener("click", () => window.pywebview.api.open_settings());
```

(The actual duration picker lives in Settings — the HUD button just opens it. This keeps one picker.)

- [ ] **Step 2: Settings — Lock-in / Extend section**

In `settings.html`, add a new `<section>` before the footer (inside `.content-inner`):

```html
        <section class="section">
          <div class="section-head">
            <div class="section-title">Commitment (lock in)</div>
            <div class="section-sub">
              Commit the lock to a fixed term. Until it ends you cannot disarm it
              or weaken any limit — only tighten. Extend-only; you can never
              shorten or cancel a commitment early.
            </div>
          </div>
          <div id="commit-status" class="row"><div class="row-value muted">Not committed.</div></div>
          <div class="row">
            <div class="row-label">Lock in for</div>
            <div class="row-value">
              <select id="commit-duration" class="field" style="width: 140px;">
                <option value="2592000">1 month</option>
                <option value="7776000">3 months</option>
                <option value="15552000">6 months</option>
                <option value="31536000">1 year</option>
                <option value="63072000">2 years</option>
                <option value="157680000">5 years</option>
              </select>
              <button id="commit-btn" class="btn sm danger" style="margin-left:10px;">Lock in</button>
            </div>
          </div>
        </section>
```

In `settings.js`:
- In `reload()` after `applyFormValues`, set the commit status line from `get_status()`:

```js
  const st = await window.pywebview.api.get_status();
  const cs = document.getElementById("commit-status").querySelector(".row-value");
  cs.textContent = st.committed ? `🔒 Locked in — ${st.commit_remaining_hm} left (until ${String(st.commit_until).slice(0,10)})` : "Not committed.";
  document.getElementById("commit-btn").textContent = st.committed ? "Extend" : "Lock in";
```

- Wire the button with a two-step confirm (mirrors the "Activate now" pattern):

```js
  const commitBtn = document.getElementById("commit-btn");
  commitBtn.addEventListener("click", async () => {
    if (commitBtn.dataset.armed !== "1") {
      commitBtn.dataset.armed = "1";
      commitBtn.textContent = "Confirm — can't undo";
      setTimeout(() => { commitBtn.dataset.armed = "0"; reload(); }, 4000);
      return;
    }
    commitBtn.dataset.armed = "0";
    const secs = parseInt(document.getElementById("commit-duration").value, 10);
    await window.pywebview.api.commit(secs);
    await reload();
  });
```

- In the Apply handler, surface `rejected`:

```js
      if (res.rejected && res.rejected.length) {
        parts.push(`${res.rejected.length} locked (committed)`);
      }
```

- [ ] **Step 3: Onboarding — optional initial commitment**

In `onboarding.html`, add an optional commitment control to the final step (a checkbox + the same duration `<select id="onboarding-commit-duration">`; default unchecked). In `onboarding.js`, when finishing, if checked call `await window.pywebview.api.commit(parseInt(sel.value,10))` before `enter_app()`. (Follow the file's existing step/handler pattern; keep it skippable.)

- [ ] **Step 4: Browser-verify**

Start preview: `preview_start name=webui`; open `settings.html`; mock `get_status` returning `committed:false`, `commit` capturing its arg, and verify: two-click "Lock in" calls `commit(31536000)` for the "1 year" option; with a mock `get_status` returning `committed:true, commit_remaining_hm:"180d 0h", commit_until:"2027-07-20..."` the status line shows "Locked in". Open `hud.html`; mock `committed:true` → `#committed-note` visible, `#lock-in` reads "Extend commitment…". Check `read_console_messages` has no errors.

- [ ] **Step 5: Commit**

```bash
git add hard_lock/webui/
git commit -m "UI: commitment status + lock-in/extend controls (HUD, Settings, onboarding)"
```

---

## Final verification

- [ ] `py -3.12 -m unittest discover -s tests` → OK (all green).
- [ ] Prod build (`build.bat`), launch, Settings → Lock in 1 minute (temporarily edit the select or use a short custom value for the test), confirm: Disarm is refused/hidden, raising a cap is rejected ("locked"), tightening still works; after the minute passes, disarm + weakening work again.
- [ ] `build-dev.bat` → launch `HardLockDev.exe`: single process, tray Quit closes it, uses `%APPDATA%\HardLockDev`, and a commitment set there does NOT lock it (dev ignores commitments).
- [ ] `hard_lock/build.py` is back to `DEV_BUILD = False` in the repo; `git status` clean.

## Notes for the implementer

- `is_committed()` importing `hard_lock.build` inside the method (not at module top) avoids an import cycle and lets tests `mock.patch("hard_lock.build.DEV_BUILD", ...)`.
- The guardian needs no changes: it already refuses to resurrect / stops when `disarm_due()` is False→can't-stop vs due. While committed, `disarm_due()` is `False`, so the prod app stays alive and unstoppable via the sanctioned path — exactly the intent.
- Keep commits per task. If a task's tests don't fail first (Step 2), the test isn't exercising new behavior — fix the test before implementing.
