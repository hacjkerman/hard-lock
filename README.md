# Hard Lock

A self-imposed shutdown lock for Windows. You commit — while rested — to a
daily limit on active computer time and a nightly hard cutoff. When you hit
either, the machine shuts down after a short grace countdown. Loosening the
rules (raising the cap, pushing the cutoff later) doesn't take effect until a
cooldown passes, so a tired 1 a.m. version of you can't undo a decision the
rested version made.

> **Honest limitation:** this is a discipline aid, not security. Anyone
> determined can end the process or remove the scheduled task. It's built to
> add friction, not to be tamper-proof.

## How it works

- **Daily active cap** — counts time you're actually at the keyboard (idle time,
  past a threshold, doesn't count). Default 8h.
- **Hard cutoff** — a wall-clock time after which the machine won't stay on.
  Default 23:30. A cutoff after midnight (e.g. `01:30`) belongs to that night —
  a Friday `01:30` keeps you up until 1:30 Saturday morning.
- **Per-day limits** — the daily cap and hard cutoff can differ by day of week
  (e.g. a bigger cap and later cutoff on weekends). Set them in Settings → Per-day
  limits. Lowering a cap / earlier cutoff applies now; raising / later is deferred.
- **Late-night timer** — if you sign in *after* a configured hour (default 23:00),
  a prompt asks how long you intend to work; that timer only ever *shortens* the
  time you have, never extends it.
- **Warnings** fire at 30 / 10 / 5 / 1 minutes before shutdown.
- **Don't-kill-my-game** — if a configured game (League of Legends by default) is
  in progress when a limit is hit, the shutdown is held until the game ends plus
  a buffer (3 min by default). See `defer_for_games` / `game_defer_grace_seconds`.
- **Wait for Claude Code** — the grace countdown still shows, but the machine
  won't actually power off while a Claude Code session is still working. Detected
  from session-transcript activity across *all* sessions and subagents (recent
  appends, plus an unanswered `tool_use` so a single long-running tool still
  counts). No way to extend it manually. See `defer_for_claude` /
  `claude_active_window_seconds`.
- **Grace countdown** — a final, uncancelable 60s window to save your work.
- **Tighten now, weaken later** — stricter changes apply immediately; looser
  changes are queued and only activate after the edit cooldown (default 24h).
  Queued changes can be cancelled before they activate.

## Install & run

### Packaged (recommended)

1. Get the `HardLock` release folder (build it with `build.bat`, see below).
2. Double-click `HardLock.exe` to run it, or `install-autostart.bat` to have it
   launch automatically at every sign-in (this needs admin and will prompt to
   elevate).
3. Config and usage data live in `%APPDATA%\HardLock\`.

Command line (`HardLock.exe`):

| Command                 | Effect                                    |
|-------------------------|-------------------------------------------|
| `HardLock.exe`          | Launch the app.                           |
| `HardLock.exe --install`   | Install the logon task (needs admin).  |
| `HardLock.exe --uninstall` | Remove the logon task.                 |
| `HardLock.exe --status`    | Show whether autostart is installed.   |

### From source

```
py -3.12 -m pip install -r requirements.txt
run.bat                     # or:  pyw -3.12 -m hard_lock
```

In dev mode `config.json` / `state.json` are written to the repo root.

## Arming (important)

Hard Lock ships in **dry-run mode** (`"dry_run": true`) — it simulates the
shutdown instead of performing it, so you can try it safely. To actually arm it,
turn dry-run **off** in Settings (or set `"dry_run": false` in config). Disabling
dry-run is a *tightening* change and takes effect immediately; re-enabling it is
a *weakening* change and waits out the cooldown.

## Configuration

`config.json` (defaults shown):

| Key                       | Default   | Meaning                                    |
|---------------------------|-----------|--------------------------------------------|
| `daily_cap_minutes`       | `480`     | Active-time cap per day.                    |
| `hard_cutoff_time`        | `"23:30"` | Wall-clock cutoff (`null` to disable).      |
| `warning_minutes_before`  | `[30,10,5,1]` | When to warn before shutdown.           |
| `grace_seconds`           | `60`      | Final countdown length.                     |
| `idle_threshold_seconds`  | `120`     | Idle past this doesn't count as active.     |
| `edit_cooldown_hours`     | `24`      | Delay before weakening changes apply.       |
| `late_night_hour`         | `23`      | Sign-ins at/after this hour get the prompt. |
| `dry_run`                 | `true`    | Simulate shutdown instead of performing it. |

## Building

```
py -3.12 -m pip install -r requirements-dev.txt
build.bat
```

Produces a self-contained `dist\HardLock\` (exe + autostart helpers) via
PyInstaller (`HardLock.spec`).

### Code signing

The exe is unsigned by default, so Windows SmartScreen shows an "unknown
publisher" warning on first run (click **More info → Run anyway**, or sign it).
To sign automatically during `build.bat`, point it at a code-signing cert:

```
set HARDLOCK_PFX=C:\path\to\cert.pfx
set HARDLOCK_PFX_PASS=your-password
build.bat
```

Needs `signtool.exe` (Windows SDK) on `PATH`. Distributing to other machines
without SmartScreen friction requires a cert from a trusted CA (an OV/EV
code-signing certificate); a self-signed cert only clears the warning on
machines that trust it.

## Development

```
py -3.12 -m unittest discover -s tests
```

The safety-critical logic (weakening/cooldown model, effective-time folding,
dry-run guard, autostart command construction) is covered by the test suite.
See [PLAN.md](PLAN.md) for the roadmap and remaining phases.
