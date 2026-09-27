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
# test-install-on-phone.sh puts stand-in tools first with HARDLOCK_TEST_BIN.
export PATH=${HARDLOCK_TEST_BIN:+$HARDLOCK_TEST_BIN:}/Applications/Xcode.app/Contents/Developer/usr/bin:/opt/homebrew/bin:/usr/bin:/bin
XCID=${HARDLOCK_XCID:-00008140-001A406C2EE0801C}                # the phone as xcodebuild names it
DCID=${HARDLOCK_DCID:-CB422D1F-DF3D-5DBD-8C88-58FFF280CBB6}     # the phone as devicectl names it
GROUP=group.com.hardlock.ios
IOSDIR="$(cd "$(dirname "$0")/.." && pwd)"
stamp() { date "+%Y-%m-%d %H:%M:%S"; }

# Each run owns a fresh directory, so runs from other checkouts cannot delete
# each other's build. The derived data goes on exit; the logs stay.
TMP=${TMPDIR:-/tmp}
RUN=$(mktemp -d "${TMP%/}/hardlock-install.XXXXXX") || exit 1
DD="$RUN/DerivedData"
trap 'rm -rf "$DD"; echo "$(stamp) logs in $RUN"' EXIT

# Fails unless the bundle's signature grants Family Controls as true and lists
# the App Group in its application groups.
check_entitlements() {
  local bundle=$1 name ents count i
  name=$(basename "$bundle")
  ents="$RUN/$name.entitlements.plist"
  if ! codesign -d --entitlements - --xml "$bundle" > "$ents" 2>> "$RUN/codesign.log"; then
    echo "$(stamp) $name: cannot read its signature (see $RUN/codesign.log)"
    return 1
  fi
  if [ "$(plutil -extract 'com\.apple\.developer\.family-controls' raw -expect bool "$ents" 2>/dev/null)" != true ]; then
    echo "$(stamp) $name: com.apple.developer.family-controls is not true"
    return 1
  fi
  count=$(plutil -extract 'com\.apple\.security\.application-groups' raw -expect array "$ents" 2>/dev/null) || count=0
  for ((i = 0; i < count; i++)); do
    [ "$(plutil -extract "com\.apple\.security\.application-groups.$i" raw -expect string "$ents" 2>/dev/null)" = "$GROUP" ] && return 0
  done
  echo "$(stamp) $name: $GROUP is not in com.apple.security.application-groups"
  return 1
}

cd "$IOSDIR/App" || exit 1
echo "$(stamp) build from $(git rev-parse --short HEAD) ($(git branch --show-current))"
xcodegen generate --spec project.yml > "$RUN/xcodegen.log" 2>&1 || { echo "$(stamp) xcodegen failed"; exit 1; }
xcodebuild build -project HardLock.xcodeproj -scheme HardLock -configuration Debug \
  -destination "platform=iOS,id=$XCID" -derivedDataPath "$DD" -allowProvisioningUpdates -jobs 2 > "$RUN/build.log" 2>&1
rc=$?
grep -E "BUILD (SUCCEEDED|FAILED)|error:" "$RUN/build.log" | sort -u | head -8 | sed "s/^/$(stamp) /"
[ $rc -eq 0 ] || { echo "$(stamp) build failed with status $rc"; exit $rc; }

APP="$DD/Build/Products/Debug-iphoneos/HardLock.app"
# Both bundles need these, or the monitor cannot read the config or shield.
check_entitlements "$APP" || exit 1
check_entitlements "$APP/PlugIns/HardLockMonitor.appex" || exit 1
echo "$(stamp) entitlements present in app and monitor"

xcrun devicectl device install app --device "$DCID" "$APP" > "$RUN/install.log" 2>&1
rc=$?
grep -iE "installed|error|fail" "$RUN/install.log" | tail -3 | sed "s/^/$(stamp) /"
[ $rc -eq 0 ] || echo "$(stamp) install failed with status $rc"
exit $rc
