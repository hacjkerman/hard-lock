import XCTest
@testable import HardLockKit

/// The editor edits a local draft; only an explicit Save reaches the rules.
final class CutoffDraftTests: XCTestCase {
    let sunday = 6
    let sundayEvening = at(2026, 1, 11, 18, 0)          // logically Sunday
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }

    /// Review finding 1: enable, pass through 10:30, settle on 22:30.
    func testIntermediatePickerValuesNeverReachTheRules() {
        let config = LockConfig.freshInstall
        var draft = CutoffDraft(config: config, dayIndex: sunday)
        XCTAssertFalse(draft.isEnabled)
        draft.isEnabled = true
        draft.time = "10:30"
        XCTAssertEqual(rules(config).preview(draft, now: sundayEvening), .appliesNow(locksNow: true))
        draft.time = "22:30"
        let outcome = rules(config).preview(draft, now: sundayEvening)
        XCTAssertEqual(outcome, .appliesNow(locksNow: false))

        guard case .apply(let result) = rules(config).decideSave(draft, expecting: outcome, now: sundayEvening)
        else { return XCTFail("expected a save") }
        XCTAssertEqual(result.applied, ["cutoff_sun"])
        XCTAssertEqual(result.config.cutoffSun, "22:30")
        XCTAssertTrue(result.config.pendingChanges.isEmpty)
        XCTAssertFalse(rules(result.config).isLockedOut(now: sundayEvening))
    }

    func testUnchangedDraftSavesNothing() {
        let config = LockConfig.default
        let draft = CutoffDraft(config: config, dayIndex: sunday)
        XCTAssertEqual(draft.value, "23:30")
        XCTAssertFalse(draft.hasChanges)
        XCTAssertEqual(rules(config).preview(draft, now: sundayEvening), .noChange)
        XCTAssertEqual(rules(config).decideSave(draft, expecting: .noChange, now: sundayEvening), .nothing)
    }

    func testToggleOffAndBackOnIsNoChange() {
        var draft = CutoffDraft(config: .default, dayIndex: sunday)
        draft.isEnabled = false
        draft.isEnabled = true
        XCTAssertFalse(draft.hasChanges)
        XCTAssertEqual(draft.time, "23:30")
    }

    func testDraftForOffDayDefaultsToLateEveningButStaysOff() {
        let draft = CutoffDraft(config: .freshInstall, dayIndex: 0)
        XCTAssertNil(draft.value)
        XCTAssertEqual(draft.time, "23:30")
        XCTAssertEqual(draft.key, "cutoff_mon")
    }

    func testLaterTimeWaitsForCooldown() {
        var draft = CutoffDraft(config: .default, dayIndex: sunday)
        draft.time = "23:45"
        XCTAssertEqual(rules(.default).preview(draft, now: sundayEvening),
                       .waits(until: sundayEvening.addingTimeInterval(24 * 3600), replacesScheduled: false))
    }

    func testTurningOffWaitsForCooldown() {
        var draft = CutoffDraft(config: .default, dayIndex: sunday)
        draft.isEnabled = false
        XCTAssertEqual(rules(.default).preview(draft, now: sundayEvening),
                       .waits(until: sundayEvening.addingTimeInterval(24 * 3600), replacesScheduled: false))
    }

    /// A queued Off must open as Off, and saving it unchanged must not cancel
    /// or restart the queued removal.
    func testPendingRemovalOpensAsScheduledValue() {
        var config = LockConfig.default
        let due = sundayEvening.addingTimeInterval(3600)
        config.pendingChanges["cutoff_sun"] = PendingChange(value: nil, effectiveAt: due)
        let draft = CutoffDraft(config: config, dayIndex: sunday)
        XCTAssertEqual(draft.saved, "23:30")
        XCTAssertEqual(draft.scheduled, PendingChange(value: nil, effectiveAt: due))
        XCTAssertFalse(draft.isEnabled)
        XCTAssertEqual(draft.time, "23:30")
        XCTAssertEqual(rules(config).preview(draft, now: sundayEvening), .noChange)
    }

    func testReturningToSavedValueCancelsScheduledChange() {
        var config = LockConfig.default
        config.pendingChanges["cutoff_sun"] = PendingChange(value: nil, effectiveAt: sundayEvening.addingTimeInterval(3600))
        var draft = CutoffDraft(config: config, dayIndex: sunday)
        draft.isEnabled = true
        XCTAssertEqual(rules(config).preview(draft, now: sundayEvening), .cancelsScheduled)
        guard case .apply(let result) = rules(config).decideSave(draft, expecting: .cancelsScheduled, now: sundayEvening)
        else { return XCTFail("expected a save") }
        XCTAssertEqual(result.config.cutoffSun, "23:30")
        XCTAssertTrue(result.config.pendingChanges.isEmpty)
    }

    func testRevisingAScheduledChangeRestartsTheWait() {
        var config = LockConfig.default
        config.pendingChanges["cutoff_sun"] = PendingChange(value: "23:45", effectiveAt: sundayEvening.addingTimeInterval(3600))
        var draft = CutoffDraft(config: config, dayIndex: sunday)
        XCTAssertEqual(draft.time, "23:45")
        draft.time = "23:50"
        XCTAssertEqual(rules(config).preview(draft, now: sundayEvening),
                       .waits(until: sundayEvening.addingTimeInterval(24 * 3600), replacesScheduled: true))
    }

    func testCommitmentBlocksLaterTimesButAllowsEarlier() {
        var config = LockConfig.default
        let until = sundayEvening.addingTimeInterval(30 * 86400)
        config.commitUntil = until
        var draft = CutoffDraft(config: config, dayIndex: sunday)
        draft.time = "23:45"
        XCTAssertEqual(rules(config).preview(draft, now: sundayEvening), .blockedByCommitment(until: until))
        XCTAssertEqual(rules(config).decideSave(draft, expecting: .blockedByCommitment(until: until), now: sundayEvening), .nothing)
        draft.time = "22:00"
        XCTAssertEqual(rules(config).preview(draft, now: sundayEvening), .appliesNow(locksNow: false))
    }

    func testResetHourIsRejectedInline() {
        var draft = CutoffDraft(config: .default, dayIndex: sunday)
        draft.time = "04:15"
        XCTAssertEqual(rules(.default).preview(draft, now: sundayEvening), .invalidResetHour)
        XCTAssertEqual(rules(.default).decideSave(draft, expecting: .invalidResetHour, now: sundayEvening), .nothing)
    }

    /// Save re-checks the current rules and refuses to act on a stale preview.
    func testSaveRevalidatesAgainstCurrentState() {
        var draft = CutoffDraft(config: .freshInstall, dayIndex: sunday)
        draft.isEnabled = true
        draft.time = "22:30"
        let shown = rules(.freshInstall).preview(draft, now: sundayEvening)
        XCTAssertEqual(shown, .appliesNow(locksNow: false))
        let later = at(2026, 1, 11, 22, 31)
        XCTAssertEqual(rules(.freshInstall).decideSave(draft, expecting: shown, now: later),
                       .outdated(.appliesNow(locksNow: true)))
    }

    func testWaitDeadlineMovingDoesNotInvalidateSave() {
        var draft = CutoffDraft(config: .default, dayIndex: sunday)
        draft.time = "23:45"
        let shown = rules(.default).preview(draft, now: sundayEvening)
        guard case .apply(let result) = rules(.default).decideSave(draft, expecting: shown, now: sundayEvening.addingTimeInterval(5))
        else { return XCTFail("expected a save") }
        XCTAssertEqual(result.deferred, ["cutoff_sun"])
    }

    func testCommitmentStartedWhileEditingBlocksSave() {
        var draft = CutoffDraft(config: .default, dayIndex: sunday)
        draft.time = "23:45"
        let shown = rules(.default).preview(draft, now: sundayEvening)
        var committed = LockConfig.default
        committed.commitUntil = sundayEvening.addingTimeInterval(86400)
        XCTAssertEqual(rules(committed).decideSave(draft, expecting: shown, now: sundayEvening),
                       .outdated(.blockedByCommitment(until: committed.commitUntil!)))
    }
}

final class CutoffOverviewTests: XCTestCase {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }

    func testDaySummariesShowSavedAndScheduledValues() {
        var config = LockConfig.default.withCutoff(nil, forWeekdayIndex: 2)
        let due = at(2026, 1, 10, 12, 0)
        config.pendingChanges["cutoff_fri"] = PendingChange(value: nil, effectiveAt: due)
        let days = rules(config).daySummaries(now: at(2026, 1, 10, 1, 0))   // logically Friday
        XCTAssertEqual(days.map(\.dayIndex), Array(0..<7))
        XCTAssertEqual(days.filter(\.isToday).map(\.dayIndex), [4])
        XCTAssertNil(days[2].saved)
        XCTAssertEqual(days[4].saved, "23:30")
        XCTAssertEqual(days[4].scheduled, PendingChange(value: nil, effectiveAt: due))
        XCTAssertNil(days[0].scheduled)
    }

    func testDaySummariesUseMaturedChanges() {
        var config = LockConfig.default
        let due = at(2026, 1, 9, 12, 0)
        config.pendingChanges["cutoff_fri"] = PendingChange(value: "01:00", effectiveAt: due)
        let days = rules(config).daySummaries(now: due)
        XCTAssertEqual(days[4].saved, "01:00")
        XCTAssertNil(days[4].scheduled)
    }

    func testAfterMidnightTimesBelongToTheFollowingMorning() {
        let r = rules(.default)
        XCTAssertTrue(r.isAfterMidnight("01:30"))
        XCTAssertTrue(r.isAfterMidnight("00:00"))
        XCTAssertTrue(r.isAfterMidnight("03:59"))
        XCTAssertFalse(r.isAfterMidnight("23:30"))
        XCTAssertFalse(r.isAfterMidnight("04:30"))   // reserved, not a morning
        XCTAssertFalse(r.isAfterMidnight("12:00"))
    }
}
