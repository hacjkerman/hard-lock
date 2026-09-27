import XCTest
@testable import HardLockKit

/// Review finding 4: every mutation starts from the effective rules at one `now`.
final class MutationFreshnessTests: XCTestCase {
    let due = at(2026, 1, 9, 12, 0)
    var queued: LockConfig {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(value: "01:00", effectiveAt: due)
        return c
    }
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }

    func testCommitBeforeMaturityDropsTheQueuedChange() {
        let committed = rules(queued).commit(duration: 86400, now: due.addingTimeInterval(-1))
        XCTAssertEqual(committed.cutoffFri, "23:30")
        XCTAssertTrue(committed.pendingChanges.isEmpty)
    }

    func testCommitAtAndAfterMaturityKeepsTheMaturedChange() {
        for now in [due, due.addingTimeInterval(1)] {
            let committed = rules(queued).commit(duration: 86400, now: now)
            XCTAssertEqual(committed.cutoffFri, "01:00")
            XCTAssertTrue(committed.pendingChanges.isEmpty)
            XCTAssertEqual(committed.commitUntil, now.addingTimeInterval(86400))
        }
    }

    func testCommitStillOnlyExtends() {
        var c = queued
        let far = due.addingTimeInterval(10 * 86400)
        c.commitUntil = far
        XCTAssertEqual(rules(c).commit(duration: 60, now: due).commitUntil, far)
    }

    func testCancelBeforeMaturityKeepsTheSavedRule() {
        let cancelled = rules(queued).cancelPending(key: "cutoff_fri", now: due.addingTimeInterval(-1))
        XCTAssertEqual(cancelled.cutoffFri, "23:30")
        XCTAssertTrue(cancelled.pendingChanges.isEmpty)
    }

    func testCancelAtAndAfterMaturityCannotUndoTheMaturedChange() {
        for now in [due, due.addingTimeInterval(1)] {
            let cancelled = rules(queued).cancelPending(key: "cutoff_fri", now: now)
            XCTAssertEqual(cancelled.cutoffFri, "01:00")
            XCTAssertTrue(cancelled.pendingChanges.isEmpty)
        }
    }

    func testCancelLeavesOtherQueuedChanges() {
        var c = queued
        let later = due.addingTimeInterval(3600)
        c.pendingChanges["cutoff_sat"] = PendingChange(value: nil, effectiveAt: later)
        let cancelled = rules(c).cancelPending(key: "cutoff_fri", now: due.addingTimeInterval(-1))
        XCTAssertEqual(cancelled.pendingChanges, ["cutoff_sat": PendingChange(value: nil, effectiveAt: later)])
    }
}

/// Review finding 6: storage and enforcement outcomes are reported separately.
final class ConfigPersistenceTests: XCTestCase {
    struct Boom: Error, LocalizedError { var errorDescription: String? { "boom" } }
    var changed: LockConfig { LockConfig.freshInstall.withCutoff("22:00", forWeekdayIndex: 0) }

    func testUnchangedConfigIsNeitherSavedNorRearmed() {
        var saves = 0, arms = 0
        let outcome = ConfigPersistence.persist(.freshInstall, over: .freshInstall,
                                                save: { _ in saves += 1 }, arm: { arms += 1 })
        XCTAssertEqual(outcome, .unchanged)
        XCTAssertEqual(saves, 0)
        XCTAssertEqual(arms, 0)
    }

    func testSuccessfulSaveArmsOnce() {
        var saved: [LockConfig] = [], arms = 0
        let outcome = ConfigPersistence.persist(changed, over: .freshInstall,
                                                save: { saved.append($0) }, arm: { arms += 1 })
        XCTAssertEqual(outcome, .saved)
        XCTAssertEqual(saved, [changed])
        XCTAssertEqual(arms, 1)
    }

    func testWriteFailureIsNotSavedAndNeverArms() {
        var arms = 0
        let outcome = ConfigPersistence.persist(changed, over: .freshInstall,
                                                save: { _ in throw Boom() }, arm: { arms += 1 })
        XCTAssertEqual(outcome, .notSaved("boom"))
        XCTAssertEqual(arms, 0)
        XCTAssertFalse(outcome.isSaved)
    }

    func testSchedulingFailureIsSavedButNotEnforced() {
        var saved: [LockConfig] = []
        let outcome = ConfigPersistence.persist(changed, over: .freshInstall,
                                                save: { saved.append($0) }, arm: { throw Boom() })
        XCTAssertEqual(outcome, .savedNotEnforced("boom"))
        XCTAssertEqual(saved, [changed])
        XCTAssertTrue(outcome.isSaved)
    }

    func testRealStoreWriteFailureLeavesNothingOnDisk() throws {
        let missing = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString).appendingPathComponent("absent")
        let store = ConfigStore(directory: missing)
        let outcome = ConfigPersistence.persist(changed, over: .freshInstall, save: store.save, arm: {})
        guard case .notSaved = outcome else { return XCTFail("\(outcome)") }
        XCTAssertThrowsError(try store.loadStrict())
    }
}

/// Review finding 5: the schedule and actual enforcement are reported apart.
final class TonightStatusTests: XCTestCase {
    let night = LockConfig.freshInstall.withCutoff("23:30", forWeekdayIndex: 4)
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }

    func testLockedOutOnlyWhenAuthorized() {
        let now = at(2026, 1, 10, 1, 0)
        let reset = at(2026, 1, 10, 4, 0)
        XCTAssertEqual(rules(night).tonightStatus(authorized: true, now: now), .lockedOut(until: reset))
        XCTAssertEqual(rules(night).tonightStatus(authorized: false, now: now), .lockoutNotEnforced(until: reset))
    }

    func testUpcomingCutoffStatesWhetherItWillBeEnforced() {
        let now = at(2026, 1, 9, 20, 0)
        let cutoff = at(2026, 1, 9, 23, 30)
        XCTAssertEqual(rules(night).tonightStatus(authorized: true, now: now), .locksAt(cutoff, enforced: true))
        XCTAssertEqual(rules(night).tonightStatus(authorized: false, now: now), .locksAt(cutoff, enforced: false))
    }

    func testNoCutoff() {
        for authorized in [true, false] {
            XCTAssertEqual(rules(.freshInstall).tonightStatus(authorized: authorized, now: at(2026, 1, 9, 20, 0)), .noCutoff)
        }
    }

    func testStatusMatchesTheShieldDecision() {
        for authorized in [true, false] {
            for now in [at(2026, 1, 9, 20, 0), at(2026, 1, 10, 1, 0)] {
                let status = rules(night).tonightStatus(authorized: authorized, now: now)
                if case .lockedOut = status {
                    XCTAssertTrue(rules(night).shouldShield(authorized: authorized, now: now))
                } else {
                    XCTAssertFalse(rules(night).shouldShield(authorized: authorized, now: now))
                }
            }
        }
    }
}
