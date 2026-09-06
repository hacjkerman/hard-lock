// swift-tools-version: 5.9
import PackageDescription

// Amendment F: HardLockKit builds and tests under SwiftPM so the rules engine
// (Tasks 1-5) can be verified with the Command Line Tools alone -- no Xcode
// project, no Apple Developer account, no device. Task 6 later points the Xcode
// targets at these same directories, so nothing has to move.
//
// NOTE for Task 7+: ShieldController/ShieldReconciler import ManagedSettings,
// which does not exist on macOS. When they land they need `#if canImport(...)`
// guards, or an `exclude:` entry here, or `swift test` stops working on this Mac.
let package = Package(
    name: "HardLockKit",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "HardLockKit", targets: ["HardLockKit"]),
    ],
    targets: [
        .target(name: "HardLockKit", path: "HardLockKit"),
        .testTarget(
            name: "HardLockKitTests",
            dependencies: ["HardLockKit"],
            path: "HardLockKitTests"
        ),
    ]
)
