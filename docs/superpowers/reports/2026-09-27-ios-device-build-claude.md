# Hard Lock iOS device build — Claude, 2026-09-27

The complete app and monitor extension build for a physical iPhone when signing is disabled, and the extension is embedded correctly. New iOS installs now start with no lock times. The install script has been hardened after Codex's review. Hard Lock is **not installed or signed yet**: that waits for Codex's review of this branch, then runs `ios/scripts/install-on-phone.sh` in the Mac's GUI session with the existing Xcode account.

## Checkout

- Windows worktree: `C:\Users\admin\Desktop\ai\hard-lock\.claude\worktrees\ios-device-build`, branch `worktree-ios-device-build`, based on `main` at `e541c9e`.
- Mac build worktree: `/Users/andrew/ai/hard-lock/.claude/worktrees/ios-device-build`, same branch, fast-forwarded from local Git bundles. `.claude/worktrees/` was added to that repository's `.git/info/exclude` so the Mac `main` checkout stays clean.
- Both `main` checkouts are untouched. Nothing was pushed or merged.

## Files changed

- `ios/scripts/install-on-phone.sh` (new): generates the project, builds Debug for the phone with `-allowProvisioningUpdates`, checks both signed bundles' entitlements, and installs without launching. Must run in the Mac's GUI session.
- `ios/scripts/test-install-on-phone.sh` (new): mocked checks for the install script.
- `ios/HardLockKit/Sources/HardLockKit/LockConfig.swift`: adds `LockConfig.freshInstall` (no cutoffs, 04:00 reset, 24-hour cooldown). `LockConfig.default` is unchanged and still mirrors the desktop app.
- `ios/HardLockKit/Sources/HardLockKit/ConfigStore.swift`: adds `loadOrCreate()`, which creates only a missing file, using `freshInstall`. An existing file is returned unchanged; an unreadable one throws and is left untouched.
- `ios/HardLockKit/Sources/HardLockKit/LockRules.swift`: adds `shouldShield(authorized:now:)`, the app's shield decision.
- `ios/HardLock/Services/LockStore.swift`: uses `loadOrCreate()` and `shouldShield`; its placeholder before loading is `freshInstall`.
- `ios/HardLockKit/Tests/HardLockKitTests/FreshInstallTests.swift` (new): 8 regressions.
- `ios/README.md` and this report.

The desktop app was not touched.

## Review round 1 (Codex, `e541c9e..f25e8be`)

1. **Shared temporary paths.** Each run now makes its own `mktemp -d` directory under `$TMPDIR` and removes only its own derived data on exit. `build.log`, `install.log`, `xcodegen.log`, `codesign.log` and the extracted entitlements stay there, and the script prints `logs in <dir>` on every exit.
2. **Loose entitlement check.** The script now requires `codesign -d` to succeed. It then reads the plist with `plutil -extract … -expect`, requiring `com.apple.developer.family-controls` to be boolean `true` and `group.com.hardlock.ios` to be an exact element of the `com.apple.security.application-groups` array. It checks both the app and the monitor.
3. **Install status.** The script exits with devicectl's own status. Earlier, a pipeline status could replace it.

## Fresh-install defaults (user decision)

The user chose no lock times for new iOS installs. A fresh config registers no cutoff activities and no pending wakeup. The app does not shield it at any time, even with Screen Time access, and neither does the monitor. Saved schedules are kept exactly, and unreadable files are still preserved. This removes the earlier safety finding: approving Screen Time access no longer arms a 23:30 nightly lock.

## Tests and build

| Check | Result |
| --- | --- |
| `swift test` in `ios/HardLockKit` (README command, Mac) | **53 tests, 0 failures** (45 existing + 8 new). New tests failed to compile before implementation. |
| `ios/scripts/test-install-on-phone.sh` (Mac, stand-in tools) | **46 checks passed**. Before the fix, 30 failed: `false`, string `"true"`, misplaced or prefixed groups were accepted; paths were fixed; install status 7 became 1. |
| `bash -n` on both scripts | Passed |
| `xcodebuild build`, Debug, `generic/platform=iOS`, `CODE_SIGNING_ALLOWED=NO` (Xcode 26.2) | **BUILD SUCCEEDED**, `HardLockMonitor.appex` embedded |
| Signed build | Not attempted this round; waits for review. Earlier over SSH: `No Accounts`. |

The mocked checks cover a rejected install for each of these, in the app and the monitor: Family Controls `false`, string `"true"` or missing; the group only in another key, as a prefix, or as a string instead of an array; and an unsigned bundle. They also cover success without launching, separate per-run directories that leave other runs alone, removed derived data with logs kept, and install and build failures keeping their status (7 and 65). Nothing contacted Apple or the phone. No simulator was started.

## Device evidence

`xcrun devicectl`: iPhone 16 Pro Max (iPhone17,2), iOS 26.6.2, Developer Mode enabled, paired, tunnel connected. devicectl ID `CB422D1F-DF3D-5DBD-8C88-58FFF280CBB6`, UDID `00008140-001A406C2EE0801C`. Hard Lock is not installed.

## Blockers and next action

- **Codex review of this branch** is next. After approval, run the script in Terminal on the Mac (GUI session): `/Users/andrew/ai/hard-lock/.claude/worktrees/ios-device-build/ios/scripts/install-on-phone.sh`.
- The user reports that Xcode is signed in. Over SSH, `DVTDeveloperAccountManagerAppleIDLists` still reads empty. The GUI-session build will confirm either way. If it reports `No Accounts` or an authentication prompt appears, stop; do not handle the prompt.
- The Built App Store Connect keys are not used. Family Controls development signing needs no Apple approval; distribution would.

## Supervised device test

Do this with the phone in hand and the Mac nearby. Do not choose a commitment during testing.

1. Install with the script above. Expect `entitlements present in app and monitor`, an installed message, and a `logs in` path.
2. Open Hard Lock and approve Screen Time access. Status should show **No cutoff today**, and nothing should be shielded. Relaunch and confirm there is no repeated prompt. Confirm Hard Lock is listed in Settings > Screen Time > Apps with Screen Time Access, which is the recovery switch.
3. To test a lock: in Cutoff times, turn today's cutoff on. It applies 23:30 immediately. Then move it to a few minutes ahead; an earlier time also applies immediately. Never pick 04:00–04:59. This locks until 04:00, and turning the cutoff off or making it later waits 24 hours. Force-quit the app.
4. At the cutoff, confirm a third-party app and Safari browsing are shielded, and confirm Settings and Phone still open.
5. Recover (below), then confirm shields clear and Hard Lock shows the access warning when reopened.

Recovery, in order:

- Turn Hard Lock off in Settings > Screen Time > Apps with Screen Time Access. This revokes its authorization and should remove its shields; confirming that is part of the test.
- Delete Hard Lock from the Home Screen. This removes its restrictions and normally its App Group data, including saved cutoffs.
- From the Mac, with the phone unlocked: `xcrun devicectl device uninstall app --device CB422D1F-DF3D-5DBD-8C88-58FFF280CBB6 com.hardlock.ios`.
- Without action, shields lift at the 04:00 reset. Emergency calls remain available throughout.

The remaining README checks (reset edges, reboot, pending-change maturity with the app closed, corrupt config, overnight soak) need longer supervised sessions.

## Still open from review

Real callback timing, background pending-change maturation, lockouts of one minute or less inside the 60-second tolerance, desktop/iOS timestamp compatibility for future sync, and repeated shield/schedule updates. None were addressed here; passing package tests do not prove device enforcement. The lenient `ConfigStore.load()` still falls back to `LockConfig.default`, but only tests call it.

## Machine state

Mac: created the worktree and exclude entry above, plus `/tmp/hardlock-dd`, `/tmp/hardlock-device-dd`, `/tmp/hardlock-*.log`, `/tmp/hardlock-branch.bundle` and Swift caches in `/tmp`. The mocked tests clean up their own temporary directories. No launch agents, keychain items, profiles, developer-portal records or phone state were changed.
