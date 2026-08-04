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

> ⚠️ **This app can force your PC to shut down.** The final shutdown runs
> `shutdown /s /f` — it force-closes applications, so **unsaved work in other
> programs is lost**. You get warnings (30/10/5/1 min) and a 60-second grace
> countdown first. It ships with **dry-run ON**, meaning it simulates the
> shutdown and never actually powers off until you deliberately arm it. Try it
> in dry-run for a day before arming it. Removal instructions are at the bottom.

## Download

Grab the latest `HardLock-vX.Y.Z-win64.zip` from the
[Releases page](https://github.com/hacjkerman/hard-lock/releases), unzip it
anywhere, and run `HardLock.exe`. Windows 10/11 64-bit. No installer, no admin
needed to run (only to install the optional start-at-logon task).

### "Windows protected your PC" / antivirus warnings

The builds are **not code-signed**, so SmartScreen shows *"Windows protected
your PC"* on first run — click **More info → Run anyway**. Some antivirus
engines may also flag it. That's expected for what this app legitimately does:
it calls `shutdown.exe`, restarts itself when killed, and creates scheduled
tasks — the same behaviours malware uses. The source is all here if you'd rather
[build it yourself](#building).

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

## Uninstalling / turning it off

Hard Lock deliberately resists being closed — a watchdog process restarts it and
a scheduled task relaunches it every minute. That's the point, but it means
"just close it" doesn't work. Here's how to actually stop it.

**The sanctioned way — Disarm.** Tray icon → **Disarm**. It keeps running until
your edit cooldown elapses (24h by default), then both processes exit and stay
gone. This is intentional: it's what stops a 2 a.m. you from switching it off.
A commitment ("lock in") blocks even this until the term ends.

**The manual way — remove it now.** In an **administrator** terminal:

```
schtasks /delete /tn HardLock /f
schtasks /delete /tn HardLockHeartbeat /f
taskkill /f /im HardLock.exe
```

Delete the tasks *first* — otherwise the heartbeat task relaunches it within a
minute. Then delete the folder you unzipped, and (optionally) your settings and
history at `%APPDATA%\HardLock`.

**Nothing else is touched.** Hard Lock writes only to `%APPDATA%\HardLock`, the
two scheduled tasks above, and (if you enabled it) a Startup shortcut. No
installer, no registry keys, no services, no network access — it never phones
home or sends any data anywhere.

**Want a version you can just close?** Build the dev flavour with
`build-dev.bat`. It has a working tray **Quit**, no watchdog, no scheduled
tasks, and its own separate settings in `%APPDATA%\HardLockDev`.
