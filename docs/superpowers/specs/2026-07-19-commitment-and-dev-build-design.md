# Hard Lock — Commitment periods + dev-closable build

Design spec. Date: 2026-07-19.

## Goal

Two linked features:

1. **Commitment ("Lock in").** Let the user commit the lock to a fixed term
   (1 month … 5 years). During the term the lock **cannot be disarmed and cannot
   be weakened** — only tightened. Like gambling self-exclusion: you can't lift
   it early. At term end it auto-releases to normal armed mode.
2. **Dev-closable build.** A separate developer build that *can* be closed and
   has no guardian, so the app can be developed/tested without locking the
   developer out — kept isolated from the committed prod install so it can't be
   used as a cheat hatch.

Non-goals / YAGNI: no cloud/accountability-partner, no per-app blocking, no
password-based unlock, no partial "reduce commitment" path (extend-only).

## Background

Current state (already built):
- Config-driven limits (`daily_cap_minutes`, per-day caps/cutoffs, etc.).
- `disarm_at` — the only sanctioned stop, a 24h-cooldown-gated disarm; when due
  the app + guardian stop. `Config.request_disarm/cancel_disarm/disarm_due`.
- Weakening edits are deferred by the edit cooldown (`_weakens`, `pending_changes`).
- Guardian: mutual watchdog + minute heartbeat task + logon task; resurrects
  unless `disarm_due()`.
- `paths.data_dir()` → `%APPDATA%\HardLock` (frozen) / repo root (source).

The commitment builds on `disarm_at`/weakening; the dev build keys off a new
compile-time flag and `paths.data_dir()`.

---

## Part 1 — Commitment ("Lock in")

### Data model

One new config field:

- `commit_until`: ISO-8601 timestamp string, or `null`. Not committed when
  `null` or in the past. Added to `DEFAULTS` as `null`.

### Config API (`hard_lock/config.py`)

- `commit_until` (property) → the raw value or `None`.
- `is_committed(now=None) -> bool` → `commit_until` set and `now < commit_until`.
- `commit_remaining_seconds(now=None) -> float | None`.
- `commit(duration_seconds) -> str`: set
  `commit_until = max(now + duration, existing commit_until)` — **extend-only,
  never shortens**. Committing is a tightening → applies instantly. Also clears
  any in-flight `disarm_at` (a pending disarm must not survive a new commitment).
- Duration is validated/clamped to a sane range (min 1 minute, max ~10 years).

### Interaction with disarm

- `request_disarm()`: if `is_committed()` → **no-op / refuse** (return a result
  flagging `committed_until`). Disarm is unavailable during a commitment.
- `disarm_due(now=None)`: returns `False` whenever `is_committed()` — so the
  guardian never treats the app as stoppable during the term, and a stale
  `disarm_at` can't fire.

### Interaction with weakening (`apply_settings`)

- While `is_committed()`, any key whose change `_weakens(...)` is **rejected
  outright** — not applied and **not queued**. Returned in a new `rejected` list
  so the UI can explain "locked in until \<date\>". Tightening still applies
  instantly. (Decision: reject, not defer-to-term-end — simpler and matches
  "tighten-only".)
- Starting a commitment does not retroactively change existing limits; any
  already-`pending` weakening changes are cancelled when `commit()` is called
  (they can't benefit the user during the term).

### Guardian interaction

No guardian changes needed: it already gates resurrection on `disarm_due()`,
which is now `False` during a commitment. The dev build (Part 2) skips the
guardian entirely.

### Entry points / UI

- **Onboarding:** an optional "Lock in for…" step (duration picker; skippable).
- **Settings + HUD:** a "Lock in" / "Extend" control available anytime.
- **HUD status:** when committed, show `🔒 Locked in — until <date> (<remaining>)`
  and replace the Disarm affordance with the committed state.
- `Api` methods: `commit(duration)`, and `get_status()` exposes `committed`,
  `commit_until`, `commit_remaining_hm`. Tray "Disarm" item reflects the
  committed state (disabled + relabeled).

### Term end

`commit_until` passing needs no action — `is_committed()` becomes `False`, so:
lock stays **armed** (limits still enforced), disarm becomes available again
under the normal 24h cooldown, weakening resumes (deferred). User may re-commit.

---

## Part 2 — Dev-closable build

### Compile-time flag

- New module `hard_lock/build.py` with a single constant: `DEV_BUILD = False`
  (repo default = prod). Frozen into the binary by PyInstaller — **not** read
  from env/argv at runtime, so it can't be flipped on a prod exe.
- `build-dev.bat`: set `DEV_BUILD = True` in `build.py`, run PyInstaller with a
  dev spec producing `HardLockDev.exe`, then restore `build.py` to `False`.
  (Prod `build.bat` unchanged.)

### Behavior when `DEV_BUILD is True`

- **No guardian:** don't spawn the watchdog, don't run the guardian loop, don't
  install/expect the heartbeat or logon tasks.
- **Closable:** tray shows **Quit** (immediate) again.
- **Commitments not enforced:** `is_committed()` treated as `False` in the dev
  build (so a developer is never locked out mid-work).
- **Separate data dir:** `paths.data_dir()` → `%APPDATA%\HardLockDev` when
  `DEV_BUILD`. Its own config/state/history/heartbeats.

### Why this resolves the cheat-hatch tension

Because the dev build uses a *different* data dir, running `HardLockDev.exe`
touches only the dev config — it can't read or clear the committed prod install's
`commit_until`, `disarm_at`, or processes. So possessing the dev exe grants no
power over a real commitment. Defeating a commitment would require editing the
source and rebuilding the prod exe with `DEV_BUILD = True` — well beyond a moment
of weakness.

Trade-off (accepted): the dev build can't exercise the *real* prod config, only
its own. Acceptable — development/testing uses dev data; the prod config is
validated by unit tests + deliberate armed tests.

---

## Honest limitations

The commitment removes the in-app disarm and the dev-exe bypass and keeps the
guardian resurrecting. It cannot stop a determined user with admin rights from
force-killing both processes **and** elevated-deleting the scheduled tasks
(exactly the manual teardown used to remove it before). That is the true ceiling
of any self-imposed lock on a machine you control; the design makes every *easy*
escape impossible, not every escape.

## Testing

Unit tests (stdlib `unittest`):
- `commit()` sets/extends and never shortens; clears `disarm_at`; cancels pending
  weakening.
- `is_committed()` / `commit_remaining_seconds()` boundaries (future/past/None).
- `disarm_due()` is `False` while committed; `request_disarm()` refuses while
  committed; both behave normally after the term.
- `apply_settings` rejects weakening while committed (reports `rejected`), still
  applies tightening.
- Term-end auto-release: after `commit_until` passes, disarm + weakening resume.
- `DEV_BUILD` branches (mock the flag): guardian skipped, `data_dir` →
  `HardLockDev`, `is_committed` forced False, tray exposes Quit.

## Rollout

1. Config model + methods + tests.
2. `apply_settings`/disarm gating on `is_committed` + tests.
3. `build.py` flag, `paths.data_dir` split, `__main__`/tray gating on
   `DEV_BUILD` + tests; `build-dev.bat`.
4. Api `commit` + `get_status` fields; HUD/Settings/onboarding UI.
5. Verify: prod build enforces a short test commitment (can't disarm/weaken);
   dev build is closable and isolated.
