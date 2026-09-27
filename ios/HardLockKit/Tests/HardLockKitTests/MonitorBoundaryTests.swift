import XCTest
@testable import HardLockKit

/// Each callback is judged at its own scheduled edge when it arrives up to
/// `monitorEarlyTolerance` early, otherwise at the actual time.
final class MonitorBoundaryTests: XCTestCase {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }
    func seconds(_ date: Date, _ s: TimeInterval) -> Date { date.addingTimeInterval(s) }

    let oneMinute = LockConfig.freshInstall.withCutoff("03:59", forWeekdayIndex: 4)   // Friday
    let night = LockConfig.freshInstall.withCutoff("23:30", forWeekdayIndex: 4)

    /// Review finding 2: every on-time callback for a 03:59 cutoff used to say unlocked.
    func testOneMinuteCutoffLocksAtItsWarning() {
        let r = rules(oneMinute)
        let cutoff = MonitorActivity.cutoff("03:59")
        let start = at(2026, 1, 10, 3, 45), warning = at(2026, 1, 10, 3, 59), reset = at(2026, 1, 10, 4, 0)
        XCTAssertFalse(r.isLockedOutForMonitor(activity: cutoff, callback: .intervalStart, now: start))
        XCTAssertTrue(r.isLockedOutForMonitor(activity: cutoff, callback: .endWarning, now: warning))
        XCTAssertTrue(r.isLockedOutForMonitor(activity: cutoff, callback: .endWarning, now: seconds(warning, -30)))
        XCTAssertTrue(r.isLockedOutForMonitor(activity: cutoff, callback: .endWarning, now: seconds(warning, 40)))
        XCTAssertFalse(r.isLockedOutForMonitor(activity: cutoff, callback: .intervalEnd, now: reset))
        XCTAssertFalse(r.isLockedOutForMonitor(activity: cutoff, callback: .intervalEnd, now: seconds(reset, -30)))
        XCTAssertFalse(r.isLockedOutForMonitor(activity: cutoff, callback: .intervalEnd, now: seconds(reset, 120)))
        XCTAssertTrue(r.isLockedOut(now: warning))
    }

    func testOrdinaryCutoffEarlyOnTimeAndLate() {
        let r = rules(night)
        let cutoff = MonitorActivity.cutoff("23:30")
        let edge = at(2026, 1, 9, 23, 30)
        XCTAssertTrue(r.isLockedOutForMonitor(activity: cutoff, callback: .intervalStart, now: seconds(edge, -60)))
        XCTAssertTrue(r.isLockedOutForMonitor(activity: cutoff, callback: .intervalStart, now: edge))
        XCTAssertTrue(r.isLockedOutForMonitor(activity: cutoff, callback: .intervalStart, now: seconds(edge, 300)))
        XCTAssertFalse(r.isLockedOutForMonitor(activity: cutoff, callback: .intervalStart, now: seconds(edge, -61)))
    }

    func testResetEarlyOnTimeAndLate() {
        let r = rules(night)
        let cutoff = MonitorActivity.cutoff("23:30")
        let reset = at(2026, 1, 10, 4, 0)
        for offset: TimeInterval in [-60, -1, 0, 1, 600] {
            XCTAssertFalse(r.isLockedOutForMonitor(activity: cutoff, callback: .intervalEnd, now: seconds(reset, offset)), "\(offset)")
        }
        XCTAssertTrue(r.isLockedOutForMonitor(activity: cutoff, callback: .intervalEnd, now: seconds(reset, -61)))
    }

    /// No blanket look-ahead: a callback between edges is judged at its real time.
    func testUnrelatedTimesAreNotAdvanced() {
        let r = rules(night)
        let beforeReset = at(2026, 1, 10, 3, 59).addingTimeInterval(30)
        XCTAssertTrue(r.isLockedOutForMonitor(activity: .cutoff("23:30"), callback: .intervalStart, now: beforeReset))
        XCTAssertTrue(r.isLockedOutForMonitor(activity: nil, callback: .intervalEnd, now: beforeReset))
        XCTAssertEqual(r.isLockedOutForMonitor(activity: nil, callback: .intervalStart, now: beforeReset),
                       r.isLockedOut(now: beforeReset))
    }

    func testCutoffCallbackOnADayWithoutThatTime() {
        let config = night.withCutoff("01:30", forWeekdayIndex: 5)             // Saturday uses 01:30
        let saturday2330 = at(2026, 1, 10, 23, 30)
        XCTAssertFalse(rules(config).isLockedOutForMonitor(activity: .cutoff("23:30"), callback: .intervalStart, now: saturday2330))
        XCTAssertTrue(rules(config).isLockedOutForMonitor(activity: .cutoff("01:30"), callback: .intervalStart,
                                                          now: seconds(at(2026, 1, 11, 1, 30), -20)))
    }

    func testEditMaturingAtTheEdgeIsUsed() {
        let cutoff = at(2026, 1, 9, 23, 30)
        var config = night
        config.pendingChanges["cutoff_fri"] = PendingChange(value: nil, effectiveAt: cutoff)
        XCTAssertFalse(rules(config).isLockedOutForMonitor(activity: .cutoff("23:30"), callback: .intervalStart,
                                                           now: seconds(cutoff, -1)))
    }

    func testEarlyPendingWakeupUsesTheMaturingChange() {
        let due = at(2026, 1, 10, 1, 0)
        var config = night
        config.pendingChanges["cutoff_fri"] = PendingChange(value: nil, effectiveAt: due)
        let r = rules(config)
        XCTAssertTrue(r.isLockedOutForMonitor(activity: .pendingChange, callback: .intervalStart, now: seconds(due, -61)))
        XCTAssertFalse(r.isLockedOutForMonitor(activity: .pendingChange, callback: .intervalStart, now: seconds(due, -30)))
        XCTAssertFalse(r.isLockedOutForMonitor(activity: .pendingChange, callback: .intervalStart, now: due))
        XCTAssertFalse(r.isLockedOutForMonitor(activity: .pendingChange, callback: .intervalEnd, now: seconds(due, 16 * 60)))
    }

    func testActivityNamesRoundTripAndMatchRegisteredNames() {
        XCTAssertEqual(MonitorActivity.cutoff("23:30").rawValue, "cutoff_23_30")
        XCTAssertEqual(MonitorActivity.pendingChange.rawValue, "pending_change")
        XCTAssertEqual(MonitorActivity(rawValue: "cutoff_01_05"), .cutoff("01:05"))
        XCTAssertEqual(MonitorActivity(rawValue: "pending_change"), .pendingChange)
        for bad in ["cutoff_1_05", "cutoff_25_00", "other", "cutoff_23:30", ""] {
            XCTAssertNil(MonitorActivity(rawValue: bad), bad)
        }
    }

    func testEdgesAcrossMidnightResetUseNearestOccurrence() {
        var config = LockConfig.freshInstall.withCutoff("23:55", forWeekdayIndex: 4)
        config.dayResetHour = 0
        let r = rules(config)
        let midnight = at(2026, 1, 10, 0, 0)
        XCTAssertTrue(r.isLockedOutForMonitor(activity: .cutoff("23:55"), callback: .endWarning, now: at(2026, 1, 9, 23, 55)))
        XCTAssertFalse(r.isLockedOutForMonitor(activity: .cutoff("23:55"), callback: .intervalEnd, now: seconds(midnight, -20)))
        XCTAssertFalse(r.isLockedOutForMonitor(activity: .cutoff("23:55"), callback: .intervalEnd, now: midnight))
    }
}
