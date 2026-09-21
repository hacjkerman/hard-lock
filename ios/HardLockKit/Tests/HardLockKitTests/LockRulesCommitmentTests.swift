import XCTest
@testable import HardLockKit

final class LockRulesCommitmentTests: XCTestCase {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }
    let now = at(2026, 1, 9, 12, 0)

    func testNotCommittedByDefault() {
        XCTAssertFalse(rules(.default).isCommitted(now: now))
        XCTAssertNil(rules(.default).commitRemaining(now: now))
    }

    func testCommitSetsFutureEnd() {
        let c = rules(.default).commit(duration: 3600, now: now)
        let r = rules(c)
        XCTAssertTrue(r.isCommitted(now: now))
        XCTAssertEqual(r.commitRemaining(now: now), 3600)
        XCTAssertFalse(r.isCommitted(now: now.addingTimeInterval(3601)))
    }

    func testCommitIsExtendOnly() {
        let first = rules(.default).commit(duration: 7200, now: now)
        let shorter = rules(first).commit(duration: 60, now: now)
        XCTAssertEqual(shorter.commitUntil, first.commitUntil)      // never shortens
        let longer = rules(first).commit(duration: 10_000, now: now)
        XCTAssertGreaterThan(longer.commitUntil!, first.commitUntil!)
    }

    func testCommitDropsQueuedWeakenings() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(
            value: "23:45", effectiveAt: now.addingTimeInterval(3600))
        let committed = rules(c).commit(duration: 3600, now: now)
        XCTAssertTrue(committed.pendingChanges.isEmpty)
    }

    func testWeakeningIsRejectedWhileCommitted() {
        let c = rules(.default).commit(duration: 3600, now: now)
        let res = rules(c).apply(changes: ["cutoff_fri": "23:45"], now: now)
        XCTAssertEqual(res.rejected, ["cutoff_fri"])
        XCTAssertTrue(res.deferred.isEmpty)
        XCTAssertEqual(res.config.cutoffFri, "23:30")
        XCTAssertTrue(res.config.pendingChanges.isEmpty)   // not even queued
    }

    func testTighteningStillWorksWhileCommitted() {
        let c = rules(.default).commit(duration: 3600, now: now)
        let res = rules(c).apply(changes: ["cutoff_fri": "22:00"], now: now)
        XCTAssertEqual(res.applied, ["cutoff_fri"])
        XCTAssertTrue(res.rejected.isEmpty)
        XCTAssertEqual(res.config.cutoffFri, "22:00")
    }
}
