# Hard Lock iOS device build — Claude, 2026-09-27

The complete app and monitor extension build for a physical iPhone when signing is disabled, and the extension is embedded correctly. The signed build is blocked: Xcode on the Mac has no signed-in account, and no Hard Lock provisioning profiles exist. Hard Lock is **not installed**. Next action: the user signs in to Xcode on the Mac, then runs `ios/scripts/install-on-phone.sh` in the Mac's Terminal.

## Checkout

- Windows worktree: `C:\Users\admin\Desktop\ai\hard-lock\.claude\worktrees\ios-device-build`, branch `worktree-ios-device-build`, based on `main` at `e541c9e`.
- Mac build worktree: `/Users/andrew/ai/hard-lock/.claude/worktrees/ios-device-build`, same branch, fast-forwarded from a local Git bundle. `.claude/worktrees/` was added to that repository's `.git/info/exclude` so the Mac `main` checkout stays clean.
- Both `main` checkouts are untouched. Nothing was pushed or merged.

## Files changed

- `ios/scripts/install-on-phone.sh` (new): generates the project, builds Debug for the phone with `-allowProvisioningUpdates`, verifies that both bundles are signed with Family Controls and the App Group, and installs without launching. It must run in the Mac's GUI session.
- `ios/README.md`: records today's build state and the install path.
- This report.

No Swift, project spec or entitlement changes were needed.

## Tests and build

| Check | Result |
| --- | --- |
| `swift test` in `ios/HardLockKit` (README command, Mac) | **45 tests, 0 failures** |
| `xcodegen generate` (2.46) | Passed |
| `xcodebuild build`, Debug, `generic/platform=iOS`, `CODE_SIGNING_ALLOWED=NO` (Xcode 26.2) | **BUILD SUCCEEDED**. One warning: iPhone-only portrait app does not support all orientations; harmless here. |
| Bundle inspection | `HardLock.app/PlugIns/HardLockMonitor.appex` present. IDs `com.hardlock.ios` and `com.hardlock.ios.monitor`, extension point `com.apple.deviceactivity.monitor-extension`, principal class `HardLockMonitor.MonitorExtension`, minimum iOS 16.0. |
| Signed build for the phone, over SSH | **BUILD FAILED**: `No Accounts: Add a new account in Accounts settings`, and the only usable profile (`iOS Team Provisioning Profile: *`) lacks App Groups and Family Controls. |
| `install-on-phone.sh` over SSH | Fails at the same point, reports the errors, exits 65. The success path (entitlement check and install) has not run. |

No simulator was started and no `xcodebuild test` was run.

## Device evidence

`xcrun devicectl` on the Mac: iPhone 16 Pro Max (iPhone17,2), iOS 26.6.2, Developer Mode enabled, paired, tunnel connected. devicectl ID `CB422D1F-DF3D-5DBD-8C88-58FFF280CBB6`, UDID `00008140-001A406C2EE0801C`. Hard Lock is not installed.

## Blockers

1. **Xcode account sign-in (native authentication).** `DVTDeveloperAccountManagerAppleIDLists` is empty. The Spin to Eat agent keeps working only because its app fits the existing wildcard profile. Hard Lock needs explicit App IDs with Family Controls (Development) and the `group.com.hardlock.ios` App Group, which automatic signing can create only through a signed-in account. I did not use the App Store Connect API keys on the Mac: they belong to Built, and using them here would widen credential use.
2. **Signing must run in the GUI session.** Over SSH, the login keychain is unavailable to codesign. I did not add a launch agent or run jobs in the GUI session.

Family Controls development builds need no Apple approval. Distribution would require Apple's Family Controls entitlement request; that is out of scope.

## Safety finding: first launch arms a nightly lock

`LockConfig.default` sets a 23:30 cutoff for every day, and `StatusView` requests Screen Time access when it first appears. If the user approves that prompt, the app saves the defaults, registers schedules, and shields every app category from 23:30 until 04:00 tonight and every night. Later cutoffs or removals wait 24 hours. This matches the plan's desktop defaults, but it means **approving access is arming a lock**. Decision for the user and Codex: keep this default or start with no cutoffs. I have not changed it.

## Supervised device test

Do this with the phone in hand and the Mac nearby. Do not choose a commitment during testing.

1. On the Mac, sign in to Xcode (Settings > Accounts) for team DT8S9V23B6. Then in Terminal: `/Users/andrew/ai/hard-lock/.claude/worktrees/ios-device-build/ios/scripts/install-on-phone.sh`. Expect `entitlements present in app and monitor` and an installed message.
2. Before opening the app, find the recovery switch: Settings > Screen Time > Apps with Screen Time Access. Hard Lock will appear there after step 3.
3. Open Hard Lock. The system asks for Screen Time access; approving it arms the 23:30 nightly default above. Relaunch and confirm there is no repeated prompt.
4. For a quick check, set today's cutoff a few minutes ahead (never 04:00–04:59). This locks until 04:00 and cannot be relaxed in the app for 24 hours. Force-quit the app.
5. At the cutoff, confirm a third-party app and Safari browsing are shielded, and confirm Settings and Phone still open.
6. Recover, then confirm shields clear and Hard Lock shows the access warning when reopened.

Recovery, in order:

- Turn Hard Lock off in Settings > Screen Time > Apps with Screen Time Access. This revokes its authorization and should remove its shields; confirming that is part of the test.
- Delete Hard Lock from the Home Screen. This removes its restrictions and normally its App Group data, including saved cutoffs.
- From the Mac, with the phone unlocked: `xcrun devicectl device uninstall app --device CB422D1F-DF3D-5DBD-8C88-58FFF280CBB6 com.hardlock.ios`.
- Without action, shields lift at the 04:00 reset. Emergency calls remain available throughout.

The remaining README checks (reset edges, reboot, pending-change maturity with the app closed, corrupt config, overnight soak) need longer supervised sessions.

## Still open from review

Real callback timing, background pending-change maturation, lockouts of one minute or less inside the 60-second tolerance, desktop/iOS timestamp compatibility for future sync, and repeated shield/schedule updates. None were addressed here; passing package tests do not prove device enforcement.

## Machine state

Mac: created the worktree and exclude entry above, plus `/tmp/hardlock-dd`, `/tmp/hardlock-device-dd`, `/tmp/hardlock-*.log`, `/tmp/hardlock-branch.bundle` and Swift caches in `/tmp`. No launch agents, keychain items, profiles, developer-portal records or phone state were changed.
