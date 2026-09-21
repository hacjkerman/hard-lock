# Hard Lock for iOS

Hard Lock requests shields for all application and web-domain categories after a per-day nightly cutoff. Earlier cutoffs apply immediately; later cutoffs and removing a cutoff wait 24 hours by default. A fixed-term commitment rejects weakening and can only be extended.

A time such as Friday 01:30 belongs to Friday night, early Saturday morning. The logical day resets at 04:00. Settings are local to this app; there is no network, analytics, account, or desktop sync.

## Requirements and build

- iOS 16 or later and a physical iPhone for Family Controls verification.
- This checkout was prepared for Xcode 26.2 (17C52), iOS SDK 26.2, and XcodeGen 2.46 at `/opt/homebrew/bin/xcodegen`.
- Both targets use automatic signing with team `DT8S9V23B6`, bundle IDs `com.hardlock.ios` and `com.hardlock.ios.monitor`, and App Group `group.com.hardlock.ios`. Both require Family Controls entitlements. Device/distribution provisioning still needs verification.

From the repository root:

```sh
/opt/homebrew/bin/xcodegen generate --spec ios/App/project.yml
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild build \
  -project ios/App/HardLock.xcodeproj -scheme HardLock \
  -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hardlock-dd
```

The generated `.xcodeproj` is ignored; `project.yml` is authoritative. Open `ios/App/HardLock.xcodeproj`, select your physical device, and run to test authorization and shielding. The app links the local `../HardLockKit` package; the extension links it too.

Do not run simulator-hosted tests on the shared 8 GB Mac. They can start another simulator and disrupt live services. Run all rules and persistence tests on macOS instead:

```sh
cd ios/HardLockKit
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
CLANG_MODULE_CACHE_PATH=/tmp/hardlock-module-cache \
swift test --disable-sandbox --cache-path /tmp/hardlock-swift-cache --jobs 2
```

The extra options keep caches writable under the host sandbox, avoid nested manifest sandboxing, and limit parallel compilation. No simulator is started. All 27 tests specified in the plan are included, plus regression coverage.

In the Codex sandbox, Xcode package resolution remained blocked by `sandbox-exec: sandbox_apply: Operation not permitted` after moving its cache paths. The fallback `ios/scripts/check-sdk.sh` compiles and links the kit, app, and extension against the iOS simulator SDK with an iOS 16 target. It does not build an installable app bundle or verify resources, signing, or extension embedding.

## Behavior and implementation

Grant Screen Time access on first launch. The status screen warns when access is unavailable and displays storage or scheduling errors. It refreshes authorization when the app returns to the foreground.

Cutoff times can be edited or disabled per weekday. Removing a cutoff is weakening. Pending changes show their remaining delay and can be cancelled. Commitments offer 30, 90, 180, or 365 days and require a second confirmation; they discard queued weakening.

`LockRules` uses an explicit clock and injected calendar. It resolves wall-clock dates across daylight-saving transitions: nonexistent times move forward to the next valid time, and repeated times use the first occurrence. `ConfigStore` atomically writes ISO-8601 JSON in the shared App Group.

The app is the only config writer. The monitor reads effective rules at every callback, including matured pending changes, and reconciles shields. It registers current and future cutoff times plus one wakeup for the next pending change (at most 15 activities). Cutoffs less than 15 minutes before reset use an earlier interval start and an end warning at the actual cutoff. DeviceActivity callback timing and this warning path require device testing.

A missing config is initialized by the app on first launch. Unreadable or invalid existing config is preserved and produces an error; the app does not silently overwrite a commitment with defaults. The monitor clears shields on read failure. Scheduling failures also clear shields and are visible in the app. Retry from Status after addressing the error.

## Honest limitations

- iOS offers app shielding, not an API to power off the phone or force the device lock screen. Some system functions remain accessible; emergency calling remains available. Actual shield coverage must be checked on a physical device.
- Deleting the app or revoking individual Screen Time authorization can defeat enforcement. Existing Screen Time restrictions may add friction; this app does not establish or guarantee those restrictions.
- iOS delivers monitoring callbacks. Delayed or missed callbacks, device clock changes, timezone changes while the app is closed, and reboot behavior need physical-device testing. There is no claim of exact background wakeup timing or tamper resistance.
- Fail-open behavior runs when the app or monitor next executes. Corrupting a file cannot itself wake a suspended process to clear shields instantly.
- No physical-device checks or soak test were completed during this build. Simulator compilation does not verify Family Controls behavior.

## Physical-device acceptance checklist

- Grant access, relaunch without a repeated prompt, revoke access in Settings, and confirm a warning on return.
- Set today's cutoff a few minutes ahead, force-quit the app, and verify category shields apply. Check both third-party apps and web browsing.
- Verify reset releases shields, including a cutoff one minute before reset and a cutoff equal to reset.
- Reboot before the cutoff and confirm enforcement still occurs.
- Tighten a cutoff into the past and confirm shields apply immediately while the app is open.
- Queue a later cutoff or removal, force-quit, and verify maturity changes enforcement without reopening. Check multiple queued changes with different deadlines.
- Confirm commitment rejects later or disabled cutoffs, accepts earlier cutoffs, and cannot be shortened. Confirm cancelling a pending change leaves the current rule intact.
- Corrupt the App Group config in a development build and trigger a monitor callback; shields must clear. Reopen the app and verify an error without overwriting the file.
- Verify extension embedding, device signing, App Group access, and Family Controls provisioning for both targets before distribution.
