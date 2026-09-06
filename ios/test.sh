#!/usr/bin/env bash
# Run the HardLockKit suite (Tasks 1-5) without an Xcode project.
#
# xcode-select on this Mac points at the Command Line Tools, which ship
# Testing.framework but not its runtime interop dylib -- so `swift test` alone
# builds and then dies in dlopen. DEVELOPER_DIR overrides the selected
# toolchain for this command only, no sudo and no global change.
set -euo pipefail
XCODE="${XCODE_APP:-/Applications/Xcode.app}"
if [ ! -d "$XCODE" ]; then
    echo "Xcode not found at $XCODE. Set XCODE_APP to its path." >&2
    exit 1
fi
cd "$(dirname "$0")"
DEVELOPER_DIR="$XCODE/Contents/Developer" exec swift test "$@"
