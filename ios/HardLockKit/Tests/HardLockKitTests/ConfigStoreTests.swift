import XCTest
@testable import HardLockKit
final class ConfigStoreTests: XCTestCase {
    var dir: URL!

    override func setUpWithError() throws {
        dir = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    }

    func testMissingFileReturnsDefaults() {
        XCTAssertEqual(ConfigStore(directory: dir).load(), .default)
    }

    func testSaveThenLoadRoundTrip() throws {
        let store = ConfigStore(directory: dir)
        let c = LockConfig.default.withCutoff("01:30", forWeekdayIndex: 5)
        try store.save(c)
        XCTAssertEqual(store.load(), c)
    }

    func testCorruptFileFallsBackToDefaults() throws {
        let store = ConfigStore(directory: dir)
        try "{ not json".write(to: dir.appendingPathComponent("config.json"),
                               atomically: true, encoding: .utf8)
        XCTAssertEqual(store.load(), .default)          // never crashes
        XCTAssertThrowsError(try store.loadStrict())    // but strict callers can tell
    }
}
