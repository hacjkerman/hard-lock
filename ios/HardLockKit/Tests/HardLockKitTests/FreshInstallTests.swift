import XCTest
@testable import HardLockKit

/// A new iOS install starts with no lock times: nothing is scheduled or
/// shielded until the user sets a cutoff, even after granting Screen Time access.
final class FreshInstallTests: XCTestCase {
    var dir: URL!
    var configURL: URL { dir.appendingPathComponent("config.json") }

    override func setUpWithError() throws {
        dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: dir)
    }

    func testFreshInstallHasNoCutoffs() {
        let c = LockConfig.freshInstall
        for i in 0..<7 { XCTAssertNil(c.cutoff(forWeekdayIndex: i)) }
        XCTAssertEqual(c.dayResetHour, LockConfig.default.dayResetHour)
        XCTAssertEqual(c.editCooldownHours, LockConfig.default.editCooldownHours)
        XCTAssertTrue(c.pendingChanges.isEmpty)
        XCTAssertNil(c.commitUntil)
    }

    func testDesktopDefaultsAreUnchanged() {
        for i in 0..<7 { XCTAssertEqual(LockConfig.default.cutoff(forWeekdayIndex: i), "23:30") }
    }

    func testMissingConfigIsCreatedWithNoLockTimes() throws {
        let store = ConfigStore(directory: dir)
        XCTAssertEqual(try store.loadOrCreate(), .freshInstall)
        XCTAssertEqual(try store.loadStrict(), .freshInstall)     // written to disk
    }

    func testExistingScheduleIsKept() throws {
        let store = ConfigStore(directory: dir)
        let saved = LockConfig.default.withCutoff("22:00", forWeekdayIndex: 4)
        try store.save(saved)
        let before = try Data(contentsOf: configURL)
        XCTAssertEqual(try store.loadOrCreate(), saved)
        XCTAssertEqual(try Data(contentsOf: configURL), before)
    }

    func testUnreadableConfigIsNotReplaced() throws {
        let store = ConfigStore(directory: dir)
        try "{ not json".write(to: configURL, atomically: true, encoding: .utf8)
        XCTAssertThrowsError(try store.loadOrCreate())
        XCTAssertEqual(try String(contentsOf: configURL, encoding: .utf8), "{ not json")
    }

    func testFreshConfigSchedulesNothing() {
        let rules = LockRules(config: .freshInstall, calendar: testCalendar)
        let now = at(2026, 1, 9, 12, 0)
        XCTAssertEqual(rules.monitoringCutoffTimes(now: now), [])
        XCTAssertNil(rules.cutoffDate(now: now))
    }

    func testFreshConfigNeverShieldsAfterAuthorization() {
        let rules = LockRules(config: .freshInstall, calendar: testCalendar)
        let start = at(2026, 1, 5, 0, 0)
        for minute in stride(from: 0, to: 8 * 24 * 60, by: 5) {
            let now = start.addingTimeInterval(TimeInterval(minute * 60))
            XCTAssertFalse(rules.shouldShield(authorized: true, now: now), "\(now)")
            XCTAssertFalse(rules.isLockedOutForMonitor(now: now), "\(now)")
        }
    }

    func testShieldingNeedsAuthorizationAndALockout() {
        let rules = LockRules(config: .default, calendar: testCalendar)
        let fridayNight = at(2026, 1, 9, 23, 45)
        XCTAssertTrue(rules.shouldShield(authorized: true, now: fridayNight))
        XCTAssertFalse(rules.shouldShield(authorized: false, now: fridayNight))
        XCTAssertFalse(rules.shouldShield(authorized: true, now: at(2026, 1, 9, 12, 0)))
    }
}
