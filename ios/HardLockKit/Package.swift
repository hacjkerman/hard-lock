// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "HardLockKit",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [.library(name: "HardLockKit", targets: ["HardLockKit"])],
    targets: [
        .target(name: "HardLockKit"),
        .testTarget(name: "HardLockKitTests", dependencies: ["HardLockKit"])
    ]
)
