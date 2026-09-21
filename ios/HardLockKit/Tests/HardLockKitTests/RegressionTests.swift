import XCTest
@testable import HardLockKit

final class RegressionTests: XCTestCase {
    let now = at(2026, 1, 9, 12, 0)

    func testMalformedCutoffsAndUnknownKeysAreRejected() {
        for value in ["25:00", "1:30", "12:3", "+1:30", "12:00:00", " 12:00"] {
            XCTAssertNil(LockRules.minutes(fromHHMM: value))
            let result = LockRules(config: .default).apply(changes: ["cutoff_fri": value], now: now)
            XCTAssertEqual(result.rejected, ["cutoff_fri"])
            XCTAssertEqual(result.config, .default)
        }
        XCTAssertEqual(LockRules(config: .default).apply(changes: ["day_reset_hour": "9"], now: now).rejected, ["day_reset_hour"])
    }

    func testDueChangesAreAppliedBeforeComparingAnEdit() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(value: "01:30", effectiveAt: now)
        let result = LockRules(config: c).apply(changes: ["cutoff_fri": "23:45"], now: now)
        XCTAssertEqual(result.applied, ["cutoff_fri"])
        XCTAssertTrue(result.deferred.isEmpty)
    }

    func testCommitmentBlocksInjectedPendingWeakening() {
        var c = LockConfig.default
        c.commitUntil = now.addingTimeInterval(3600)
        c.pendingChanges["cutoff_fri"] = PendingChange(value: nil, effectiveAt: now)
        let refreshed = LockRules(config: c).refreshPending(now: now)
        XCTAssertEqual(refreshed.cutoffFri, "23:30")
        XCTAssertTrue(refreshed.pendingChanges.isEmpty)
    }

    func testReturningToCurrentValueCancelsQueue() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(value: nil, effectiveAt: now.addingTimeInterval(3600))
        let result = LockRules(config: c).apply(changes: ["cutoff_fri": "23:30"], now: now)
        XCTAssertTrue(result.config.pendingChanges.isEmpty)
    }

    func testScheduleIncludesFutureCutoffsWithoutActivatingThemEarly() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(value: "01:30", effectiveAt: now.addingTimeInterval(3600))
        let r = LockRules(config: c)
        XCTAssertEqual(r.monitoringCutoffTimes(now: now), ["01:30", "23:30"])
        XCTAssertEqual(r.refreshPending(now: now).cutoffFri, "23:30")
    }

    func testDSTKeepsResetAndCutoffAtWallClockTimes() {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "Australia/Sydney")!
        for day in [DateComponents(year: 2026, month: 10, day: 4, hour: 12),
                    DateComponents(year: 2026, month: 4, day: 5, hour: 12)] {
            let noon = cal.date(from: day)!
            let r = LockRules(config: .default, calendar: cal)
            XCTAssertEqual(cal.component(.hour, from: r.logicalDayStart(now: noon)), 4)
            XCTAssertEqual(cal.component(.hour, from: r.resetDate(now: noon)), 4)
            XCTAssertEqual(cal.component(.hour, from: r.cutoffDate(now: noon)!), 23)
            XCTAssertEqual(cal.component(.minute, from: r.cutoffDate(now: noon)!), 30)
        }
    }

    func testExactCutoffAndResetBoundaries() {
        let r = LockRules(config: .default, calendar: testCalendar)
        XCTAssertTrue(r.isLockedOut(now: at(2026, 1, 9, 23, 30)))
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 10, 4, 0)))
    }

    func testInvalidConfigFailsStrictLoad() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let store = ConfigStore(directory: dir)
        var c = LockConfig.default
        c.dayResetHour = 99
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        try encoder.encode(c).write(to: dir.appendingPathComponent("config.json"))
        XCTAssertThrowsError(try store.loadStrict())
        XCTAssertThrowsError(try store.save(c))
        XCTAssertEqual(store.load(), .default)
    }

    func testStoreRoundTripsPendingRemovalAndCommitmentDates() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(value: nil, effectiveAt: now)
        c.commitUntil = now.addingTimeInterval(3600)
        let store = ConfigStore(directory: dir)
        try store.save(c)
        XCTAssertEqual(try store.loadStrict(), c)
    }
}

final class MonitoringWindowTests: XCTestCase {
    func testOrdinaryWindowStartsAtCutoff() throws {
        let window = try XCTUnwrap(LockRules(config: .default).monitoringWindow(hhmm: "23:30"))
        XCTAssertEqual(window.startMinute, 23 * 60 + 30)
        XCTAssertEqual(window.endMinute, 4 * 60)
        XCTAssertNil(window.warningMinutes)
    }

    func testShortWindowUsesWarningAtActualCutoff() throws {
        let window = try XCTUnwrap(LockRules(config: .default).monitoringWindow(hhmm: "03:59"))
        XCTAssertEqual(window.startMinute, 3 * 60 + 45)
        XCTAssertEqual(window.endMinute, 4 * 60)
        XCTAssertEqual(window.warningMinutes, 1)
    }

    func testCutoffAtResetUsesResetCallback() throws {
        let window = try XCTUnwrap(LockRules(config: .default).monitoringWindow(hhmm: "04:00"))
        XCTAssertEqual(window.startMinute, 225)
        XCTAssertNil(window.warningMinutes)
        let config = LockConfig.default.withCutoff("04:00", forWeekdayIndex: 4)
        XCTAssertTrue(LockRules(config: config, calendar: testCalendar).isLockedOut(now: at(2026, 1, 9, 4, 0)))
    }

    func testShortWindowWrapsAcrossMidnight() throws {
        var config = LockConfig.default
        config.dayResetHour = 0
        let window = try XCTUnwrap(LockRules(config: config).monitoringWindow(hhmm: "23:55"))
        XCTAssertEqual(window.startMinute, 1425)
        XCTAssertEqual(window.endMinute, 0)
        XCTAssertEqual(window.warningMinutes, 5)
    }

    func testMaturedRemovalClearsLogicalLockoutWithoutAppWrite() {
        let now = at(2026, 1, 10, 1, 0)
        var config = LockConfig.default
        config.pendingChanges["cutoff_fri"] = PendingChange(value: nil, effectiveAt: now)
        XCTAssertTrue(LockRules(config: config, calendar: testCalendar).isLockedOut(now: now))
        let effective = LockRules(config: config, calendar: testCalendar).refreshPending(now: now)
        XCTAssertFalse(LockRules(config: effective, calendar: testCalendar).isLockedOut(now: now))
    }
}
