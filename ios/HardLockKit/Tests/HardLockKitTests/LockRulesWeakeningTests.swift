import XCTest
@testable import HardLockKit

final class LockRulesWeakeningTests: XCTestCase {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }
    let now = at(2026, 1, 9, 12, 0)

    func testEarlierCutoffIsTighteningAndAppliesNow() {
        let r = rules(.default)                      // Fri 23:30
        let res = r.apply(changes: ["cutoff_fri": "22:00"], now: now)
        XCTAssertEqual(res.applied, ["cutoff_fri"])
        XCTAssertTrue(res.deferred.isEmpty)
        XCTAssertEqual(res.config.cutoffFri, "22:00")
        XCTAssertTrue(res.config.pendingChanges.isEmpty)
    }

    func testLaterCutoffIsWeakeningAndIsQueued() {
        let r = rules(.default)
        let res = r.apply(changes: ["cutoff_fri": "23:45"], now: now)
        XCTAssertEqual(res.deferred, ["cutoff_fri"])
        XCTAssertTrue(res.applied.isEmpty)
        XCTAssertEqual(res.config.cutoffFri, "23:30")             // not yet in force
        let pending = try! XCTUnwrap(res.config.pendingChanges["cutoff_fri"])
        XCTAssertEqual(pending.value, "23:45")
        XCTAssertEqual(pending.effectiveAt, now.addingTimeInterval(24 * 3600))
    }

    /// The bug found on desktop: 01:30 is EARLIER on the clock but LATER at
    /// night, so it must count as weakening.
    func testAfterMidnightCutoffCountsAsLater() {
        let r = rules(.default)
        XCTAssertTrue(r.cutoffWeakens(oldValue: "23:30", newValue: "01:30"))
        XCTAssertFalse(r.cutoffWeakens(oldValue: "01:30", newValue: "23:30"))
    }

    func testRemovingACutoffIsWeakening() {
        let r = rules(.default)
        XCTAssertTrue(r.cutoffWeakens(oldValue: "23:30", newValue: nil))
        XCTAssertFalse(r.cutoffWeakens(oldValue: nil, newValue: "23:30"))
    }

    func testDuePendingChangeActivates() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(
            value: "23:45", effectiveAt: now.addingTimeInterval(-60))   // already due
        let updated = rules(c).refreshPending(now: now)
        XCTAssertEqual(updated.cutoffFri, "23:45")
        XCTAssertTrue(updated.pendingChanges.isEmpty)
    }

    func testNotYetDuePendingChangeStays() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(
            value: "23:45", effectiveAt: now.addingTimeInterval(3600))
        let updated = rules(c).refreshPending(now: now)
        XCTAssertEqual(updated.cutoffFri, "23:30")
        XCTAssertNotNil(updated.pendingChanges["cutoff_fri"])
    }

    func testReapplyingAQueuedValueIsIdempotent() {
        let r = rules(.default)
        let first = r.apply(changes: ["cutoff_fri": "23:45"], now: now)
        let effectiveAt = first.config.pendingChanges["cutoff_fri"]!.effectiveAt
        let again = LockRules(config: first.config, calendar: testCalendar)
            .apply(changes: ["cutoff_fri": "23:45"], now: now.addingTimeInterval(600))
        XCTAssertTrue(again.deferred.isEmpty)   // no re-queue
        XCTAssertTrue(again.applied.isEmpty)    // and not cancelled either
        XCTAssertEqual(again.config.pendingChanges["cutoff_fri"]?.effectiveAt, effectiveAt)
    }
}
