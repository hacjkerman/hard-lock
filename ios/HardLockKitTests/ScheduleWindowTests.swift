import Testing
import Foundation
@testable import HardLockKit

struct ScheduleWindowTests {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }

    @Test func distinctCutoffTimesDeduplicates() {
        var c = LockConfig.default                         // all 23:30
        c = c.withCutoff("01:30", forWeekdayIndex: 4)      // Fri
        c = c.withCutoff("01:30", forWeekdayIndex: 5)      // Sat
        #expect(rules(c).distinctCutoffTimes() == ["01:30", "23:30"])
    }

    @Test func distinctCutoffTimesIgnoresDisabledDays() {
        var c = LockConfig.default
        for i in 0..<7 { c = c.withCutoff(nil, forWeekdayIndex: i) }
        c = c.withCutoff("22:00", forWeekdayIndex: 2)
        #expect(rules(c).distinctCutoffTimes() == ["22:00"])
    }

    @Test func cutoffAppliesOnlyOnMatchingDays() {
        var c = LockConfig.default
        c = c.withCutoff("01:30", forWeekdayIndex: 4)      // Friday only
        let r = rules(c)
        let fridayNight = at(2026, 1, 10, 1, 45)           // logically Friday
        #expect(r.cutoffApplies(hhmm: "01:30", now: fridayNight))
        #expect(!r.cutoffApplies(hhmm: "23:30", now: fridayNight))

        let saturdayNight = at(2026, 1, 10, 23, 45)        // logically Saturday
        #expect(r.cutoffApplies(hhmm: "23:30", now: saturdayNight))
        #expect(!r.cutoffApplies(hhmm: "01:30", now: saturdayNight))
    }

    /// Amendment A: isLockedOut stays correct on a night whose own interval
    /// never started -- which is why it, not cutoffApplies, gates shielding.
    /// Here the 01:30 activity wakes on a 23:30 night.
    @Test func isLockedOutIsCorrectWhenWokenByAnotherDaysActivity() {
        var c = LockConfig.default                         // Mon..Sun 23:30
        c = c.withCutoff("01:30", forWeekdayIndex: 4)      // except Friday
        let r = rules(c)
        let mondayNight = at(2026, 1, 6, 1, 30)            // logically Monday
        #expect(!r.cutoffApplies(hhmm: "01:30", now: mondayNight))
        #expect(r.isLockedOut(now: mondayNight))           // still shielded, correctly
    }
}
