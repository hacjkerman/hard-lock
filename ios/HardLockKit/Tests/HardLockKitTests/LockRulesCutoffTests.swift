import XCTest
@testable import HardLockKit

/// Fixed clock helper: builds dates in a stable UTC calendar so tests are
/// deterministic regardless of the machine's timezone.
func at(_ y: Int, _ mo: Int, _ d: Int, _ h: Int, _ mi: Int) -> Date {
    var c = DateComponents()
    c.year = y; c.month = mo; c.day = d; c.hour = h; c.minute = mi
    return testCalendar.date(from: c)!
}

var testCalendar: Calendar = {
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = TimeZone(identifier: "UTC")!
    return cal
}()

final class LockRulesCutoffTests: XCTestCase {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }

    func testLogicalWeekdayRollsAtFour() {
        let r = rules(.default)
        // Sat 2026-01-10 02:00 is still logically Friday (index 4).
        XCTAssertEqual(r.logicalWeekdayIndex(now: at(2026, 1, 10, 2, 0)), 4)
        // Sat 05:00 is Saturday (index 5).
        XCTAssertEqual(r.logicalWeekdayIndex(now: at(2026, 1, 10, 5, 0)), 5)
    }

    func testEveningCutoffLocksOutAfterIt() {
        let r = rules(.default)                     // all days 23:30
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 9, 22, 0)))
        XCTAssertTrue(r.isLockedOut(now: at(2026, 1, 9, 23, 45)))
        XCTAssertTrue(r.isLockedOut(now: at(2026, 1, 10, 2, 0)))   // still Friday night
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 10, 5, 0)))  // past the 04:00 reset
    }

    func testAfterMidnightCutoffBelongsToThatNight() {
        // Friday 01:30 means 1:30am Saturday — you are NOT locked out at 23:45 Friday.
        let c = LockConfig.default.withCutoff("01:30", forWeekdayIndex: 4)
        let r = rules(c)
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 9, 23, 45)))
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 10, 1, 0)))
        XCTAssertTrue(r.isLockedOut(now: at(2026, 1, 10, 1, 45)))
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 10, 5, 0)))  // reset ended it
    }

    func testNoCutoffMeansNeverLockedOut() {
        let c = LockConfig.default.withCutoff(nil, forWeekdayIndex: 4)
        let r = rules(c)
        XCTAssertNil(r.cutoffDate(now: at(2026, 1, 9, 23, 45)))
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 9, 23, 45)))
    }

    func testMinutesFromHHMM() {
        XCTAssertEqual(LockRules.minutes(fromHHMM: "23:30"), 1410)
        XCTAssertEqual(LockRules.minutes(fromHHMM: "01:30"), 90)
        XCTAssertNil(LockRules.minutes(fromHHMM: "nonsense"))
    }
}
