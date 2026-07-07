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

## Phase 4 — event log + history

- Append-only `events.jsonl`: writes from `apply_settings`,
  `cancel_pending`, `initiate_shutdown`, warning fires, dry-run toggles.
- Per-day summary archive (on reset, append `{date, active_seconds,
  cap_minutes, hit_cap, hit_cutoff}` somewhere — `history.jsonl`).
- Implement `HistoryView` from `design/components/surfaces.jsx`: 42-day bar
  chart, streaks (derived at render time), recent events list.
- Change daily reset from midnight → **04:00 local** to match the design.
  Likely a new config field (e.g. `day_reset_hour: 4`).

## Phase 5 — tray + onboarding

- System tray icon + menu (`pystray`) from
  `design/components/surfaces.jsx` → `TrayMenu`. Implies a background
  process model: closing the HUD does not exit the app.
- Onboarding wizard (`design/components/surfaces.jsx` → `Onboarding`).
  Design only specifies step 3 (limits). **Need to decide steps 1, 2, 4, 5
  before building this phase.** Gated by a `setup_completed` flag in config.

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
