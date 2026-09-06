import Testing
import Foundation
@testable import HardLockKit

struct LockRulesCutoffTests {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }

    @Test func logicalWeekdayRollsAtFour() {
        let r = rules(.default)
        // Sat 2026-01-10 02:00 is still logically Friday (index 4).
        #expect(r.logicalWeekdayIndex(now: at(2026, 1, 10, 2, 0)) == 4)
        // Sat 05:00 is Saturday (index 5).
        #expect(r.logicalWeekdayIndex(now: at(2026, 1, 10, 5, 0)) == 5)
    }

    @Test func eveningCutoffLocksOutAfterIt() {
        let r = rules(.default)                     // all days 23:30
        #expect(!r.isLockedOut(now: at(2026, 1, 9, 22, 0)))
        #expect(r.isLockedOut(now: at(2026, 1, 9, 23, 45)))
        #expect(r.isLockedOut(now: at(2026, 1, 10, 2, 0)))   // still Friday night
        #expect(!r.isLockedOut(now: at(2026, 1, 10, 5, 0)))  // past the 04:00 reset
    }

    @Test func afterMidnightCutoffBelongsToThatNight() {
        // Friday 01:30 means 1:30am Saturday -- NOT locked out at 23:45 Friday.
        let c = LockConfig.default.withCutoff("01:30", forWeekdayIndex: 4)
        let r = rules(c)
        #expect(!r.isLockedOut(now: at(2026, 1, 9, 23, 45)))
        #expect(!r.isLockedOut(now: at(2026, 1, 10, 1, 0)))
        #expect(r.isLockedOut(now: at(2026, 1, 10, 1, 45)))
        #expect(!r.isLockedOut(now: at(2026, 1, 10, 5, 0)))  // reset ended it
    }

    @Test func noCutoffMeansNeverLockedOut() {
        let c = LockConfig.default.withCutoff(nil, forWeekdayIndex: 4)
        let r = rules(c)
        #expect(r.cutoffDate(now: at(2026, 1, 9, 23, 45)) == nil)
        #expect(!r.isLockedOut(now: at(2026, 1, 9, 23, 45)))
    }

    @Test func minutesFromHHMM() {
        #expect(LockRules.minutes(fromHHMM: "23:30") == 1410)
        #expect(LockRules.minutes(fromHHMM: "01:30") == 90)
        #expect(LockRules.minutes(fromHHMM: "nonsense") == nil)
    }

    /// Amendment I: resetDate was never covered directly.
    @Test func resetDateIsTheNextDayBoundary() {
        let r = rules(.default)
        #expect(r.resetDate(now: at(2026, 1, 9, 23, 45)) == at(2026, 1, 10, 4, 0))
        #expect(r.resetDate(now: at(2026, 1, 10, 2, 0)) == at(2026, 1, 10, 4, 0))
        #expect(r.resetDate(now: at(2026, 1, 10, 5, 0)) == at(2026, 1, 11, 4, 0))
    }

    /// Amendment I: a malformed time silently disables the lock for that day --
    /// the one fail-open path with no user-visible signal. Pinned so it stays a
    /// decision rather than an accident.
    @Test func malformedCutoffDisablesEnforcementForThatDay() {
        let c = LockConfig.default.withCutoff("25:99", forWeekdayIndex: 4)
        let r = rules(c)
        #expect(r.cutoffDate(now: at(2026, 1, 9, 23, 45)) == nil)
        #expect(!r.isLockedOut(now: at(2026, 1, 9, 23, 45)))
        #expect(r.distinctCutoffTimes() == ["23:30"])   // never registered
    }

    /// Amendment I: a cutoff exactly at the reset hour maps to logical minute 0,
    /// the tightest possible value, and shields the whole logical day.
    @Test func cutoffAtTheResetHourShieldsTheEntireDay() {
        let c = LockConfig.default.withCutoff("04:00", forWeekdayIndex: 4)
        let r = rules(c)
        #expect(r.logicalCutoffMinute("04:00") == 0)
        #expect(r.cutoffDate(now: at(2026, 1, 9, 12, 0)) == at(2026, 1, 9, 4, 0))
        #expect(r.isLockedOut(now: at(2026, 1, 9, 4, 0)))
        #expect(r.isLockedOut(now: at(2026, 1, 9, 12, 0)))
        #expect(r.isLockedOut(now: at(2026, 1, 10, 3, 59)))
        #expect(!r.isLockedOut(now: at(2026, 1, 10, 4, 0)))   // next logical day
    }

    /// Amendment I: DST. New York springs forward 02:00 -> 03:00 on 2026-03-08.
    @Test func lockoutWindowSurvivesSpringForward() throws {
        let cal = zonedCalendar("America/New_York")
        let r = LockRules(config: .default, calendar: cal)          // 23:30 cutoff
        let saturdayNight = at(2026, 3, 7, 23, 45, in: cal)
        let cutoff = try #require(r.cutoffDate(now: saturdayNight))
        #expect(cutoff < r.resetDate(now: saturdayNight))
        #expect(r.isLockedOut(now: saturdayNight))
        // 01:30 EST exists; the reset at 04:00 EDT still ends the window.
        #expect(r.isLockedOut(now: at(2026, 3, 8, 1, 30, in: cal)))
        #expect(!r.isLockedOut(now: at(2026, 3, 8, 5, 0, in: cal)))
    }
}
