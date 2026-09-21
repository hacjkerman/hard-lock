Hard Lock for iOS is implemented and ready for Claude’s branch review. All 41 package tests pass, and the kit, app, and extension compile and link against the iOS 26.2 simulator SDK with an iOS 16 deployment target. Full Xcode bundle validation and physical-device testing remain unfinished.

The review branch is `codex/ios-hard-lock` in `/tmp/hardlock-review-20260921`. A local bundle preserves it at `/Users/andrew/ai/hard-lock/ios/review-artifacts/codex-ios-hard-lock.bundle`. Nothing was pushed or merged.

The original checkout’s `.git` is read-only: branch creation failed with `cannot lock ref ... unable to create directory`. Its branch therefore remains `main`, with the implementation files present as working-copy changes. To complete the requested commit history without changing protected metadata, I created a local clone under `/tmp`, replayed the tasks with failing/passing tests, and committed there. The report is the last commit on that review branch. The bundle is intentionally ignored rather than committed into itself.

Tasks and commits:

| Task | Delivered | Commit |
| --- | --- | --- |
| 1 | Config model, defaults, desktop JSON keys, package scaffold | `c4caeaa` |
| 2 | Logical day and nightly cutoff resolution | `e2f142b` |
| 3 | Immediate tightening and deferred weakening | `3d9361b` |
| 4 | Extend-only commitments | `7abea78` |
| 5 | Atomic App Group persistence and strict reads | `dba9dea` |
| 6 | XcodeGen targets, entitlements, individual authorization | `bc2cd77` |
| 7 | Named category shield controller | `5e3db93` |
| 8 | Schedule registration and monitor enforcement | `f1f4714` |
| 9 | Status, cutoff editor, commitment, pending-change screens | `ae02080` |
| Additional corrections | Background pending changes, DST, validation, fail-open handling, UI lifecycle | `5ba830c` |
| 10 | iOS documentation, root README link, SDK check script; soak outstanding | `71269a8` |

Tasks 6–9 have their implementation and SDK checks completed; their physical-device verification steps remain outstanding.

Exact final test command, run from `/tmp/hardlock-review-20260921/ios/HardLockKit`:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer CLANG_MODULE_CACHE_PATH=/tmp/hardlock-module-cache swift test --disable-sandbox --cache-path /tmp/hardlock-swift-cache --jobs 2
```

XCTest result: `Executed 41 tests, with 0 failures (0 unexpected)`. This includes all 27 tests in the plan plus 14 regressions. The literal last output line is:

```text
✔ Test run with 0 tests in 0 suites passed after 0.001 seconds.
```

That trailing line belongs to the separate Swift Testing runner; the XCTest suite above it ran all 41 tests. Failing-before-implementation and passing-after-implementation runs were verified for Tasks 1–5 and 8, and for the added regressions.

From the review checkout root, `ios/scripts/check-sdk.sh` also passed. Its last line is:

```text
SDK compile and link passed for HardLockKit, HardLock, and HardLockMonitor (iOS 16 simulator target).
```

XcodeGen generation and `git diff --check main..HEAD` passed. The review checkout is clean after the report commit.

Deviations from the plan and reasons:

- Used a local Swift package at `ios/HardLockKit`, with `Sources/HardLockKit` and `Tests/HardLockKitTests`, instead of an Xcode framework/test bundle, as requested. The default-model tests have their own `LockConfigTests.swift` file.
- Used `ios/App/project.yml` and ignored generated `.xcodeproj` files. Both targets depend on `../HardLockKit`. Committed the generated Info plists along with the specification. Used Xcode 26.2, SDK 26.2, automatic signing, team `DT8S9V23B6`, the specified bundle IDs and App Group, and iOS 16.0.
- Never ran `xcodebuild test` or booted a simulator. Package tests use two build jobs, `/tmp` caches, and `--disable-sandbox` because the default cache location and nested sandbox are refused on this host.
- Attempted the requested generic simulator `xcodebuild build`, always with `/tmp/hardlock-dd`. Cache redirects, including `CFFIXED_USER_HOME` and `SWIFTPM_MODULECACHE_OVERRIDE`, got past cache failures, but package resolution remained blocked by `sandbox-exec: sandbox_apply: Operation not permitted`. CoreSimulator was also inaccessible. Further command-line/environment attempts did not resolve this. Used direct SDK compilation and linking as partial verification; it does not validate an installable bundle, resources, signing, or extension embedding.
- Used the `/tmp` review clone and ignored bundle because the original Git metadata is protected. No existing user files were removed; the pre-existing `design/ios/` file and `ios/.build/` artifacts were left alone.
- The plan’s required Superpowers execution skills were unavailable after searching locally. Followed the task sequence directly without delegating or consulting Claude.
- Corrected elapsed-hour date arithmetic to preserve local cutoff/reset times across DST. Missing clock times advance to the next valid time; repeated times use the first occurrence.
- Added strict time/config validation, rejected unknown edit keys, applied matured changes before comparing edits, and prevented queued weakening from activating during an active commitment. Validation permits reset hours 0–23 and cooldowns 0–87,600 hours to reject malformed data.
- Expanded monitoring from current cutoff times to current plus future cutoff times and one pending-change wakeup, at most 15 activities, so edits can mature with the app closed. The extension reads effective rules without writing the config. All start/end/warning callbacks reconcile the current lock state rather than blindly applying or clearing a shield.
- Added a tested 15-minute minimum-window adapter with cutoff warnings for short lockouts. A cutoff equal to reset reconciles at the reset callback. These callback paths still need device testing.
- Removed the App Group force unwrap; existing unreadable config is preserved and errors are visible. The app initializes only a missing file, publishes edits after saving, clears shields on failure, reconciles immediately after edits, and refreshes authorization on foreground entry. Added disabled-day controls, pending-change cancellation, and confirmation reset when a commitment choice changes. Temporary shield debug buttons were removed from the final UI.
- Expanded the documentation to state actual platform limits and avoid promising that individual authorization cannot be revoked or that corruption instantly wakes a suspended process.

Unfinished:

- The original checkout cannot be switched to the review branch or committed within this sandbox. The complete branch is available in the local clone and bundle.
- Full `xcodebuild build`, installable app packaging, extension embedding validation, device/distribution provisioning, and entitlement approval were not verified.
- No physical-iPhone authorization, shield coverage, force-quit enforcement, reset, reboot, revoked-access, corrupt-config callback, pending-maturity, or overnight soak checks were performed. No service, launchd agent, backup, or machine setting was changed.

Claude should first inspect `ScheduleManager.swift` and `MonitorExtension.swift`, especially rearming pending changes from the extension and short-window warning timing. Then inspect `LockStore.swift` for fail-open behavior and persistence ordering, and `RegressionTests.swift` for the added boundaries. Follow the physical-device checklist in `ios/README.md` before accepting enforcement as verified. Review the whole branch against the plan; there is no push or merge to undo.

## Review fixes, 2026-09-21

- Task 1: Reject any cutoff with logical minute 0–59, reserving the entire reset hour (04:00–04:59 with the default reset). Apply, strict store load/save (including pending values), pending activation, and monitoring use the same validation. The editor rejects the selection with a reset-hour explanation. Replaced the all-day-lock regression and added rejection, adjacent valid-time, and persisted/pending negative cases. Task 1 verification: 42 tests passed.
- Task 2: Kept reconciliation with a 60-second forward tolerance for start, end, and warning callbacks, including pending changes effective at the evaluated time. A callback one second before cutoff now evaluates inside the lockout and shields; one second before reset evaluates after reset and clears, so neither edge depends on delivery crossing the exact clock boundary. Store and schedule errors still clear shields. Rules tests cover both early edges, weekday selection, short-window warnings, and pending maturity. This intentionally allows enforcement and maturity decisions up to 60 seconds early; lockouts of one minute or less can fall entirely within the tolerance. Actual callback delivery still needs device verification.
- Task 3: Deleted `ios/review-artifacts/` and only its `.gitignore` entry; preserved every other ignore line, including the pre-existing `run/` addition. The historical bundle reference above no longer applies.

Final verification in this working checkout: **45 XCTest tests passed, 0 failures** using the requested package command; `ios/scripts/check-sdk.sh` passed compilation and linking for HardLockKit, HardLock, and HardLockMonitor against the iOS simulator SDK (iOS 16 target). `git diff --check` passed. No simulator was booted and no `xcodebuild test` was run.

All three requested review fixes are complete as working-copy changes. No Git metadata was written and no commits were made; Claude will commit. Full installable-bundle/signing/embedding validation and the previously listed physical-device and overnight-soak checks remain unfinished.
