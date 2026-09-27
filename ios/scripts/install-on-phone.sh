#!/bin/bash
# Build Hard Lock for Andrew's iPhone and install it, from the checkout this
# script lives in. Run it in Terminal on the Mac itself, after signing in to
# Xcode (Settings > Accounts) with the account for team DT8S9V23B6. Over SSH the
# login keychain is unavailable: xcodebuild reports "No Accounts" and codesign
# fails with errSecInternalComponent.
#
# It installs but does not launch. Opening the app is the first step of the
# supervised device test, because it asks for Screen Time access.
set -o pipefail
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
export PATH=/Applications/Xcode.app/Contents/Developer/usr/bin:/opt/homebrew/bin:/usr/bin:/bin
XCID=${HARDLOCK_XCID:-00008140-001A406C2EE0801C}                # the phone as xcodebuild names it
DCID=${HARDLOCK_DCID:-CB422D1F-DF3D-5DBD-8C88-58FFF280CBB6}     # the phone as devicectl names it
IOSDIR="$(cd "$(dirname "$0")/.." && pwd)"
DD=/tmp/hardlock-device-dd
LOG=/tmp/hardlock-device-build.log
stamp() { date "+%Y-%m-%d %H:%M:%S"; }
cd "$IOSDIR/App" || exit 1
echo "$(stamp) build from $(git rev-parse --short HEAD) ($(git branch --show-current))"
xcodegen generate --spec project.yml >/dev/null || exit 1
rm -rf "$DD"
xcodebuild build -project HardLock.xcodeproj -scheme HardLock -configuration Debug \
  -destination "platform=iOS,id=$XCID" -derivedDataPath "$DD" -allowProvisioningUpdates -jobs 2 > "$LOG" 2>&1
rc=$?
grep -E "BUILD (SUCCEEDED|FAILED)|error:" "$LOG" | sort -u | head -8 | sed "s/^/$(stamp) /"
[ $rc -eq 0 ] || { echo "$(stamp) build failed, log $LOG"; exit $rc; }
APP="$DD/Build/Products/Debug-iphoneos/HardLock.app"
# Both bundles must carry Family Controls and the App Group, or the monitor
# cannot read the config or apply shields.
for B in "$APP" "$APP/PlugIns/HardLockMonitor.appex"; do
  ents=$(codesign -d --entitlements - --xml "$B" 2>/dev/null)
  for key in com.apple.developer.family-controls group.com.hardlock.ios; do
    grep -q "$key" <<<"$ents" || { echo "$(stamp) $(basename "$B") is missing $key"; exit 1; }
  done
done
echo "$(stamp) entitlements present in app and monitor"
xcrun devicectl device install app --device "$DCID" "$APP" 2>&1 | grep -iE "installed|error|fail" | tail -3 | sed "s/^/$(stamp) /"
