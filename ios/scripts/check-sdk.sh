#!/bin/sh
# Compile and link Swift against the installed simulator SDK without starting it.
# This does not replace Xcode's resource, signing, or extension-embedding checks.
set -eu
cd "$(dirname "$0")/../.."
compiler=/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/swiftc
sdk=/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator26.2.sdk
output=/tmp/hardlock-sdk-check
mkdir -p "$output"
compile() {
    "$compiler" -swift-version 5 -target arm64-apple-ios16.0-simulator \
        -sdk "$sdk" -module-cache-path /tmp/hardlock-module-cache "$@"
}
compile -emit-library -emit-module -parse-as-library -module-name HardLockKit \
    ios/HardLockKit/Sources/HardLockKit/*.swift \
    -emit-module-path "$output/HardLockKit.swiftmodule" -o "$output/libHardLockKit.dylib"
compile -I "$output" -L "$output" -lHardLockKit -emit-executable -module-name HardLock \
    ios/HardLock/HardLockApp.swift ios/HardLock/Services/*.swift ios/HardLock/Views/*.swift \
    -o "$output/HardLock"
compile -I "$output" -L "$output" -lHardLockKit -emit-library -application-extension \
    -module-name HardLockMonitor ios/HardLockMonitor/MonitorExtension.swift \
    ios/HardLock/Services/ShieldController.swift ios/HardLock/Services/ScheduleManager.swift \
    -o "$output/HardLockMonitor.dylib"
echo 'SDK compile and link passed for HardLockKit, HardLock, and HardLockMonitor (iOS 16 simulator target).'
