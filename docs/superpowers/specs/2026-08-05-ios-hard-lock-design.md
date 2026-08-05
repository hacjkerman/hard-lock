# Hard Lock for iOS — design

Design spec. Date: 2026-08-05.

## Goal

Bring Hard Lock's nightly cutoff to the iPhone: after a per-day cutoff time, the
phone shields every app until the day resets. Loosening a rule waits out a
cooldown, and a fixed-term commitment blocks loosening entirely — the same
"tighten now, weaken later" model as the Windows app.

## The constraint that shapes everything

**iOS cannot lock or power off the device from a third-party app.** There is no
API; `lockNow()` is Android's Device Admin. The only sanctioned enforcement is
Apple's **Family Controls / ManagedSettings**, which *shields* apps: a shielded
app shows a block screen instead of opening.

So the desktop's "shut down the machine" becomes **"shield every app"** — the
strongest lockout iOS permits. Emergency calling from the lock screen is never
affected.

## Scope

**In scope (v1)**
- Per-day nightly hard cutoff (different times per weekday), including
  after-midnight cutoffs (a Friday `01:30` belongs to Friday night).
- Shield-everything enforcement during the lockout window.
- Tighten-now / weaken-later cooldown on rule changes.
- Fixed-term commitments ("lock in"), during which nothing can be weakened.
- Local-only: no accounts, no network, no telemetry.

**Explicit non-goals**
- *Daily screen-time cap.* Dropped deliberately: `DeviceActivity` reports usage
  in coarse intervals, so a cap would be imprecise and much more complex. Cutoff
  + cooldown + commitments need no usage tracking at all.
- *Sync with the Windows app.* A separate follow-up project (see below).
- *Android.* Different enforcement model entirely.

## Relationship to the desktop app

This is a **separate codebase** (Swift), not a port of the Python. What carries
over is the *rules model*, reimplemented in Swift as `LockRules`.

Sync is deferred to its own project, but v1 prepares for it: the config is a
flat JSON document whose keys mirror the desktop's `config.json`
(`cutoff_mon`…`cutoff_sun`, `day_reset_hour`, `edit_cooldown_hours`,
`pending_changes`, `commit_until`). A later sync project transports that
document; it does not have to reshape it.

## Architecture

Six units, each independently understandable and testable. Only the first two
are pure logic/storage; the rest are thin wrappers over Apple frameworks, which
keeps the testable surface large and the untestable surface small.

### 1. `LockRules` (pure Swift, no Apple frameworks)

The rules engine, and the only place decisions are made. Ports the semantics of
the desktop's `config.py`:

- `cutoff(for: weekday) -> DateComponents?` — that day's cutoff, or none.
- `logicalDate(now:)` / `logicalWeekday(now:)` — the day rolls at
  `day_reset_hour` (04:00), so 02:00 Saturday still counts as Friday.
- `isLockedOut(now:) -> Bool` — inside the cutoff→reset window for the logical day.
- `apply(changes:) -> (applied, deferred, rejected)` — tightening applies
  immediately; weakening is queued for `edit_cooldown_hours`; while committed,
  weakening is **rejected outright**, not queued.
- `isCommitted(now:)`, `commit(duration:)` — extend-only; a new commitment never
  shortens an existing one.
- Weakening classification: a later cutoff is weakening, an earlier one is
  tightening — compared as minutes since the day reset, so `23:30 → 01:30`
  correctly counts as *later* (this bug was found and fixed on the desktop).

No UI, no I/O, no frameworks — so it is exhaustively unit-testable.

### 2. `ConfigStore`

Reads/writes the config JSON in a shared **App Group** container so both the app
and the monitor extension see the same rules. Atomic writes; a corrupt file
falls back to defaults rather than crashing (matching desktop behaviour).

### 3. `ShieldController`

Wraps `ManagedSettingsStore`. Two operations:

```swift
store.shield.applicationCategories = .all()   // lock out
store.shield.webDomainCategories  = .all()
// and clearing both to release
```

### 4. `ScheduleManager`

Registers the lockout windows with `DeviceActivityCenter`. Each window is a
`DeviceActivitySchedule` from that day's cutoff to `day_reset_hour` — so the
lockout window *is* the schedule interval.

Because a `DeviceActivitySchedule` repeats daily rather than weekly, per-weekday
cutoffs are handled by registering one repeating activity per **distinct** cutoff
time (at most seven), each with its own `DeviceActivityName`. The monitor then
confirms the current logical weekday actually uses that activity's time before
shielding. Schedules are re-registered whenever settings change.

### 5. `MonitorExtension` (`DeviceActivityMonitor`)

The piece that makes this work when the app isn't running — iOS will not keep
the app alive, but it *will* wake this extension on schedule.

- `intervalDidStart` → load config, confirm today's cutoff matches this activity,
  then shield everything.
- `intervalDidEnd` → clear the shields (day reset).

### 6. SwiftUI screens

Status (locked out or time until cutoff), per-day cutoff editor, commitment
("lock in") with a confirm step, and a pending-changes list with time remaining.

## Data flow

```
UI edit → LockRules.apply() → ConfigStore (App Group JSON) → ScheduleManager
                                        ↓
                          MonitorExtension wakes at cutoff
                                        ↓
                    reads same config → ShieldController.shieldAll()
                                        ↓
                       intervalDidEnd at day reset → clear
```

The extension reads the same config the app writes, so enforcement stays correct
even if the app is never opened.

## Failure handling

- **Corrupt config** → fall back to defaults; never crash the extension.
- **Authorization revoked** → shields stop applying; the app detects this on
  launch and surfaces it prominently rather than silently doing nothing (the
  desktop's "alive but inert" failure taught this).
- **Schedule registration fails** → surface the error in the UI; do not fail
  silently.
- **Shields must fail open, not closed** — if the extension cannot read config,
  it clears shields rather than stranding the phone in a permanent lockout.

## Honest limitations

State these in the app and README rather than implying a hard lock:

- **Deleting the app removes its shields.** That is the escape hatch. The
  mitigation is a Screen Time passcode plus Settings → Screen Time → Content &
  Privacy → "Don't Allow" removing apps — set by the user, and documented.
- **Revoking Family Controls** in Settings ends enforcement; a Screen Time
  passcode gates that.
- **Emergency calls always work** from the lock screen.

Like the desktop app: strong friction, not security.

## Prerequisites

- macOS with Xcode (available).
- The **`com.apple.developer.family-controls`** entitlement. Free for local
  development on your own device; distribution beyond that requires Apple's
  approval.
- Screen Time authorization from the user at first launch
  (`AuthorizationCenter.requestAuthorization(for: .individual)`).

## Testing

- **XCTest over `LockRules`**, mirroring the Python suite: tightening applies
  instantly, weakening defers, cooldown expiry activates, commitment rejects
  weakening, commitment is extend-only, per-day cutoff resolution, after-midnight
  cutoff belongs to the right night, logical-day rollover at 04:00.
- **Fake clock** — every rules API takes an explicit `now`, so time-dependent
  behaviour is tested without waiting.
- **On-device verification** — shields actually apply at the cutoff and clear at
  the reset, with the app force-quit (proving the extension path works).

## Rollout

1. `LockRules` + tests (no Apple frameworks — pure logic, fastest to get right).
2. `ConfigStore` + App Group.
3. Xcode project skeleton, entitlement, Family Controls authorization flow.
4. `ShieldController` + manual shield/unshield behind a debug button.
5. `ScheduleManager` + `MonitorExtension`; verify with the app force-quit.
6. SwiftUI screens (status, per-day cutoffs, commitment, pending).
7. On-device soak: leave it running through a real cutoff.
