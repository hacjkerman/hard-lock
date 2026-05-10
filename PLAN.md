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

## Phase 3 — package + auto-start

- Bundle with PyInstaller into `HardLock.exe`.
- Install a **Task Scheduler** task that runs `HardLock.exe` at logon.
  (Chosen over Startup folder / Run key because it's not togglable from
  Task Manager Startup tab; chosen over a Windows service because services
  don't have a desktop session and the added IPC complexity isn't worth it
  for a self-discipline tool that's honest about not being tamper-proof.)

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
