#!/bin/bash
# Checks install-on-phone.sh against stand-in xcodegen, xcodebuild, codesign
# and xcrun. Nothing is built, signed or installed, and nothing contacts Apple
# or the phone. macOS only: the script reads entitlements with plutil.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/install-on-phone.sh"
command -v plutil >/dev/null || { echo "needs macOS plutil"; exit 2; }
# Without the override the script would run the real tools.
grep -q HARDLOCK_TEST_BIN "$SCRIPT" || { echo "install-on-phone.sh has no HARDLOCK_TEST_BIN override"; exit 2; }
WORK=$(mktemp -d "${TMPDIR:-/tmp}/hardlock-install-test.XXXXXX") || exit 2
trap 'rm -rf "$WORK"' EXIT
BIN="$WORK/bin"
mkdir -p "$BIN"

cat > "$BIN/xcodegen" <<'EOF'
#!/bin/bash
exit 0
EOF
cat > "$BIN/xcodebuild" <<'EOF'
#!/bin/bash
# Records the derived-data path and fakes both bundles there.
while [ $# -gt 0 ]; do [ "$1" = -derivedDataPath ] && dd=$2; shift; done
echo "$dd" >> "$MOCK_DIR/derived-data"
mkdir -p "$dd/Build/Products/Debug-iphoneos/HardLock.app/PlugIns/HardLockMonitor.appex"
if [ "${MOCK_BUILD_RC:-0}" -ne 0 ]; then echo "error: stand-in failure"; echo "** BUILD FAILED **"; exit "$MOCK_BUILD_RC"; fi
echo "** BUILD SUCCEEDED **"
EOF
cat > "$BIN/codesign" <<'EOF'
#!/bin/bash
# Prints the fixture named after the bundle; no fixture means unsigned.
f="$MOCK_DIR/$(basename "${@: -1}").plist"
[ -f "$f" ] || { echo "${@: -1}: code object is not signed at all" >&2; exit 1; }
cat "$f"
EOF
cat > "$BIN/xcrun" <<'EOF'
#!/bin/bash
echo "$*" >> "$MOCK_DIR/xcrun-calls"
echo "${MOCK_INSTALL_OUT:-App installed:}"
exit "${MOCK_INSTALL_RC:-0}"
EOF
chmod +x "$BIN"/*

plist() { # body of the entitlements dict
  printf '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>%s</dict></plist>\n' "$1"
}
FC='<key>com.apple.developer.family-controls</key>'
AG='<key>com.apple.security.application-groups</key>'
fixture() {
  case $1 in
    good)          plist "$FC<true/>$AG<array><string>group.com.hardlock.ios</string></array>" ;;
    second-group)  plist "$FC<true/>$AG<array><string>group.other</string><string>group.com.hardlock.ios</string></array>" ;;
    fc-false)      plist "$FC<false/>$AG<array><string>group.com.hardlock.ios</string></array>" ;;
    fc-string)     plist "$FC<string>true</string>$AG<array><string>group.com.hardlock.ios</string></array>" ;;
    fc-missing)    plist "$AG<array><string>group.com.hardlock.ios</string></array>" ;;
    group-elsewhere) plist "$FC<true/>$AG<array><string>group.other</string></array><key>keychain-access-groups</key><array><string>group.com.hardlock.ios</string></array>" ;;
    group-prefix)  plist "$FC<true/>$AG<array><string>group.com.hardlock.ios.extra</string></array>" ;;
    group-string)  plist "$FC<true/>$AG<string>group.com.hardlock.ios</string>" ;;
  esac
}

fails=0
check() { # description, command...
  local what=$1; shift
  if "$@"; then echo "ok   $what"; else echo "FAIL $what"; fails=$((fails + 1)); fi
}

# run NAME APP MONITOR [VAR=value...]: APP/MONITOR name a fixture or "unsigned".
# Leaves $M (case dir), $RC and $OUT (combined output) for the checks.
run() {
  local name=$1 app=$2 mon=$3; shift 3
  M="$WORK/$name"
  mkdir -p "$M/tmp"
  [ "$app" = unsigned ] || fixture "$app" > "$M/HardLock.app.plist"
  [ "$mon" = unsigned ] || fixture "$mon" > "$M/HardLockMonitor.appex.plist"
  OUT=$(env MOCK_DIR="$M" HARDLOCK_TEST_BIN="$BIN" TMPDIR="$M/tmp" "$@" "$SCRIPT" 2>&1)
  RC=$?
}
installed() { grep -q "device install app" "$M/xcrun-calls" 2>/dev/null; }
not_installed() { ! installed; }
launched() { grep -q "launch" "$M/xcrun-calls" 2>/dev/null; }
logdir() { sed -n 's/.*logs in //p' <<<"$OUT" | tail -1; }
says() { grep -q -- "$1" <<<"$OUT"; }
rejects() { # name app monitor bundle-in-message
  run "$1" "$2" "$3"
  check "$1: exits non-zero" test "$RC" -ne 0
  check "$1: does not install" not_installed
  check "$1: names $4" says "$4"
}

rejects fc-false fc-false good HardLock.app
rejects fc-string fc-string good HardLock.app
rejects fc-missing fc-missing good HardLock.app
rejects group-elsewhere group-elsewhere good HardLock.app
rejects group-prefix group-prefix good HardLock.app
rejects group-string group-string good HardLock.app
rejects app-unsigned unsigned good HardLock.app
rejects monitor-unsigned good unsigned HardLockMonitor.appex
rejects monitor-fc-false good fc-false HardLockMonitor.appex
rejects monitor-group-elsewhere good group-elsewhere HardLockMonitor.appex

run success good second-group
check "success: exits 0" test "$RC" -eq 0
check "success: installs" installed
check "success: does not launch" eval '! launched'
check "success: reports entitlements" says "entitlements present"
first_log=$(logdir)
check "success: keeps logs at the printed path" test -f "$first_log/build.log"
check "success: log dir is inside TMPDIR" eval '[[ "$first_log" == "$M/tmp/"* ]]'
check "success: removes its derived data" eval '! test -e "$(head -1 "$M/derived-data")"'

# A second run in the same TMPDIR gets its own directory and leaves the first alone.
mkdir -p "$M/tmp/hardlock-install.other/DerivedData"
run success good good
check "second run: separate derived data" test "$(sort -u "$M/derived-data" | wc -l)" -eq 2
check "second run: separate log dir" test "$(logdir)" != "$first_log"
check "second run: first run's log survives" test -f "$first_log/build.log"
check "second run: another run's directory survives" test -d "$M/tmp/hardlock-install.other/DerivedData"

run install-fails good good MOCK_INSTALL_RC=7 MOCK_INSTALL_OUT="Something went wrong"
check "install-fails: keeps devicectl's status 7" test "$RC" -eq 7
check "install-fails: keeps the install log" test -f "$(logdir)/install.log"

run build-fails good good MOCK_BUILD_RC=65
check "build-fails: keeps xcodebuild's status 65" test "$RC" -eq 65
check "build-fails: does not install" not_installed
check "build-fails: keeps the build log" grep -q "BUILD FAILED" "$(logdir)/build.log"

echo
[ $fails -eq 0 ] && echo "all install-script checks passed" || echo "$fails install-script checks failed"
[ $fails -eq 0 ]
