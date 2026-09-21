import XCTest
@testable import HardLockKit

final class ScheduleWindowTests: XCTestCase {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }

    func testDistinctCutoffTimesDeduplicates() {
        var c = LockConfig.default                         // all 23:30
        c = c.withCutoff("01:30", forWeekdayIndex: 4)      // Fri
        c = c.withCutoff("01:30", forWeekdayIndex: 5)      // Sat
        XCTAssertEqual(rules(c).distinctCutoffTimes(), ["01:30", "23:30"])
    }

    func testDistinctCutoffTimesIgnoresDisabledDays() {
        var c = LockConfig.default
        for i in 0..<7 { c = c.withCutoff(nil, forWeekdayIndex: i) }
        c = c.withCutoff("22:00", forWeekdayIndex: 2)
        XCTAssertEqual(rules(c).distinctCutoffTimes(), ["22:00"])
    }

    /// The extension is woken by every registered schedule, so it must confirm
    /// the current logical day actually uses that time before shielding.
    func testCutoffAppliesOnlyOnMatchingDays() {
        var c = LockConfig.default
        c = c.withCutoff("01:30", forWeekdayIndex: 4)      // Friday only
        let r = rules(c)
        let fridayNight = at(2026, 1, 10, 1, 45)           // logically Friday
        XCTAssertTrue(r.cutoffApplies(hhmm: "01:30", now: fridayNight))
        XCTAssertFalse(r.cutoffApplies(hhmm: "23:30", now: fridayNight))

        let saturdayNight = at(2026, 1, 10, 23, 45)        // logically Saturday
        XCTAssertTrue(r.cutoffApplies(hhmm: "23:30", now: saturdayNight))
        XCTAssertFalse(r.cutoffApplies(hhmm: "01:30", now: saturdayNight))
    }
}
