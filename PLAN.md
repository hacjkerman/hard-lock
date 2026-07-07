# Hard Lock — build plan

Phased rollout from current tkinter MVP to the full Windows 11 Fluent design
(`design/Hard Lock.html` + `design/components/*.jsx`). UI moves to pywebview;
tkinter stays as fallback for safety-critical screens until verified.

## Phase 1 — pywebview scaffold + HUD + settings

- Add `pywebview` to `requirements.txt`.
- Scaffold `hard_lock/webui/` with `index.html`, `style.css`, `app.js`.
- Port `StatusWindow` to a pywebview window rendering the HUD pill/widget
  from `design/components/hud.jsx`.
- Build the settings app (sidebar variant) with the **pending-changes queue**
  including per-item **Cancel** button.
- Python `Api` object exposes: `get_status()`, `apply_settings()`,
  `cancel_pending(key)`, `get_pending()`.
- Backend additions:
  - `Config.cancel_pending(key)` — pop from `pending_changes`, save.
  - Traffic-light state helper (green/amber/red) driven by % of cap
    remaining. Centralize thresholds.
- `GraceCountdown` (tkinter) unchanged — safety-critical path.

## Phase 2 — warnings + shutdown takeover

- Port warning popups (30/10/5/1 min) to pywebview toasts
  (`design/components/surfaces.jsx` → `WarningPopup`).
- **Sound effects on warning fires** — escalating intensity (soft chime at
  30 → sharper at 10 → urgent alarm at 5/1). HTML5 Audio from the toast,
  or `winsound` from Python. Need to source/generate assets.
- Implement the **classic** shutdown takeover variant in pywebview.
- Keep tkinter `GraceCountdown` as a verified fallback until the pywebview
  takeover is confirmed reliable (topmost over fullscreen apps, no close).

## Phase 3 — package + auto-start (done)

- ✅ Bundle with PyInstaller into `HardLock.exe` — `HardLock.spec` (onedir,
  windowed), built via `build.bat`; webui assets bundled as datas; verified the
  frozen exe launches and bootstraps `%APPDATA%\HardLock\config.json`.
- ✅ Data path resolution split (`paths.py`): repo root in dev, `%APPDATA%\HardLock`
  when frozen (previously wrote next to `__file__`, which breaks when packaged).
- ✅ **Task Scheduler** logon task via `autostart.py` + CLI (`--install` /
  `--uninstall` / `--status`), with self-elevating `packaging/*.bat` helpers.
  (Chosen over Startup folder / Run key because it's not togglable from Task
  Manager Startup tab; over a service because services lack a desktop session.)
  Note: creating an ONLOGON task requires admin — handled with a clear message
  + the self-elevating helper; confirmed on Win11 that non-elevated create fails
  with Access Denied.
- ✅ `launch.py` entry (runs by full path → repo root on `sys.path`, so the
  logon task works regardless of working directory).
- ✅ Optional Authenticode signing wired into `build.bat` (guarded on
  `HARDLOCK_PFX`); documented in README. Still needs a real CA cert to clear
  SmartScreen on other machines.
- Follow-ups: obtain an OV/EV code-signing cert; optional MSI/installer; app icon.

## Late-night session timer (shipped)

- At launch (each logon/reopen), if `now.hour >= late_night_hour` (config,
  default 23) a **pywebview prompt window** (`webui/session.{html,css,js}`)
  opens first instead of the HUD, built to the Fluent design system
  (`CooldownConfirm` / Onboarding "set your limits" surface). It asks for a
  work window in minutes (preset chips + stepper), clamped to the floor already
  left before cap/cutoff. On commit/skip it hands off to the HUD in the same
  `webview.start()` loop via `Api.start_session_timer` / `skip_session_timer`
  → `open_hud()` (HUD created first, then the prompt is destroyed).
- The chosen minutes set a wall-clock deadline on `Api`. It folds into
  `effective = min(cap, cutoff, session)`, so it can only ever *tighten* time
  and reuses the existing warnings → grace → shutdown path.
- Skip ⇒ no extra limit. Not persisted — fresh prompt every reopen (the
  intended friction; honest that it's not tamper-proof).
- Surfaced in the HUD as a "Late-night timer" card (`session_active`).
- ✅ `late_night_hour` editable in the settings UI (0–24, 24 = off), validated,
  round-trip verified; exposed via `get_settings`.
- Follow-ups: escalating warning sounds (Phase 2) apply here too; optional
  persistence-across-restart to close the kill-and-relaunch cheat; per-restart
  minimum window.

## Hardening review (done)

Adversarial multi-agent review of the release-hardening diff found + fixed 6
real issues (0 false positives):
- Config `config.json` had an unsynchronized read-modify-write between the HUD
  poll thread (`refresh_pending`) and the settings thread (`apply_settings`/
  `cancel_pending`) → lost updates / torn file → reset to defaults. Fixed with a
  reentrant `threading.Lock` around all mutation+save paths and **atomic writes**
  (temp + `os.replace`) in both `Config.save` and `State.save`.
- `State.load` crashed at logon on valid-but-non-object JSON (`AttributeError`).
  Fixed with an `isinstance(dict)` guard.
- `_apply_pending` ran outside the corrupt-file guard → a malformed
  `pending_changes` entry crashed at logon and every poll. Now drops bad entries.
- Clearing a settings number field sent `NaN`→`null` → `int(None)` crash that
  dropped the whole edit batch. Added client-side validation for grace/idle/cooldown.
- `get_status` had no re-entrancy guard → overlapping polls could double-count
  active time. Serialized the poll critical section with a `Lock`.
- Late-night prompt hardcoded "60-second grace"; now renders the real
  `grace_seconds`.
All covered by new tests (57 total, all passing).

## Phase 4 — event log + history (done)

- ✅ Append-only `events.jsonl` + per-day `history.jsonl` (`hard_lock/history.py`:
  `EventLog`, `DayHistory` — tolerant JSONL, torn lines skipped). Events logged
  from `apply_settings`, `cancel_pending`, warning fires, shutdown (with reason +
  dry-run), session-timer set, and day rollover.
- ✅ Daily reset moved midnight → **04:00 local** via `day_reset_hour` (config)
  and `Config.logical_date()`. `State` refactored into a dumb container; rollover
  + archiving moved to `Api._roll_day` (runs at launch and each poll under the
  poll lock). State snapshots the day's `cap_minutes` so the archive reflects the
  cap that governed that day.
- ✅ `HistoryView` (`webui/history.{html,css,js}`): 42-day bar chart with cap
  line + shutdown markers, stat cards (streaks/avg/shutdowns), recent-events
  list. Opened from a new HUD **History** button (`Api.get_history` / `open_history`).
- **Hardening review** of the Phase 4 diff found + fixed 5 issues (0 false pos):
  archive using the day's own cap (not current); dead History/Settings button
  after close (subscribe to `events.closed`; was a pre-existing Settings bug too);
  streaks no longer count never-used days; `get_history` rolls the day itself;
  single `events.jsonl` read per call. Covered by tests (74 total, all passing).
- Follow-ups: rotate/cap `events.jsonl` for very long-lived installs;
  `day_reset_hour` in the settings UI; `hit_cutoff` in the day summary.

## Phase 5 — tray + onboarding

### Background process model + tray (done)

- ✅ **Tick loop moved to a Python background thread** (`__main__.tick_loop` →
  `Api.tick()`); `get_status` is now a read-only snapshot. Active-time tracking
  and the grace/shutdown trigger no longer depend on the HUD's JS poll, so the
  lock keeps enforcing when the HUD is hidden. Live-verified: the ticker drives
  the full cutoff → warning → grace → dry-run shutdown chain.
- ✅ **System tray** (`hard_lock/tray.py`, `pystray`) on a daemon thread —
  Show HUD / Settings / History / Quit + a live status line. Defensive: if
  pystray/Pillow are missing or the icon fails, the app runs without it (the
  lock never depends on the tray).
- ✅ **Hide-to-tray**: the frameless HUD gains a ✕ button (`Api.hide_hud`); a
  `closing` handler hides the HUD (and the late-night prompt) instead of exiting
  unless `force_close` (grace/Quit) is set. The app persists via the hidden
  window so `webview.start()` keeps running.
- **Review of the diff** found + fixed 1 HIGH (a dismissed false-positive too):
  the late-night prompt had no `closing` guard, so Alt+F4 on it (the only window
  at that point) called `Application.Exit()` and silently killed the lock —
  fixed with the same hide-to-tray guard (verified live: WM_CLOSE hides, process
  stays alive). 80 tests, all passing.
- Notes: Quit is **enabled** (beta safety). The design shows "Quit disabled" as
  the armed behavior — gate on an armed/`dry_run` flag later.

### Onboarding wizard (done)

- ✅ 5-step first-run wizard (`webui/onboarding.{html,css,js}`) gated by a
  `setup_completed` config flag; shown before the HUD on first launch (takes
  precedence over the late-night prompt), reusing the hide-to-tray guard.
  Steps: welcome → how-it-works → set limits (cap slider + cutoff + late-night
  hour) → arm (dry-run + autostart toggle) → recap.
- ✅ `Config.complete_setup` sets the chosen values **directly** (initial setup
  bypasses the weakening cooldown — nothing to weaken from yet) and marks setup
  done. `Api.get_onboarding_info` / `finish_onboarding` (coerce + persist +
  optional Task-Scheduler install, reporting admin failures) / `enter_app`.
- Verified: 87 tests; wizard flow + autostart-failure path checked in-browser;
  packaged exe shows "Hard Lock — Setup" on first run.
- Follow-up: `day_reset_hour` and warnings aren't in the wizard (sensible
  defaults); expose in Settings later.

## Deferred / open questions

- **Idle pause** button appears in HUD widget + tray (disabled). It's a
  cheat vector — lets you step away, pause, resume without cap consuming.
  Decision pending: drop it, or route it through the cooldown queue as a
  weakening action.
- HUD has 5 variants in the design (pill, pill-progress, pill-minimal,
  widget, widget-detailed) — ship 1 pill + 1 widget; drop the rest.
- Settings "unified" variant hides the pending queue — drop; ship sidebar.
- Shutdown "terminal" variant feels off-tone — drop; ship classic.
- "Lock armed · running as service" copy in settings sidebar implies a
  service model we're not building. Reword to match actual runtime (task
  scheduler launched, running in user session).

## Design → backend gap summary (for reference)

| Design element                | Backend status         | Action                               |
|-------------------------------|------------------------|--------------------------------------|
| Cancel pending change         | missing                | add `Config.cancel_pending`          |
| Reset at 04:00 local          | midnight               | add `day_reset_hour`, update `State` |
| History bar chart / streaks   | nothing recorded       | `history.jsonl` summaries            |
| Recent events list            | nothing recorded       | `events.jsonl` append-only           |
| Tray menu                     | foreground window only | `pystray` + background process model |
| Idle pause                    | auto only              | decision pending (see open questions)|
| Onboarding wizard             | silent defaults        | `setup_completed` flag + first-run   |
| Traffic-light state           | not computed           | central helper, documented thresholds|
| Per-hour activity sparkline   | not bucketed           | hourly buckets in `State` or drop    |
