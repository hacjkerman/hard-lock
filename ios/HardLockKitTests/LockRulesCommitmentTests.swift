import Testing
import Foundation
@testable import HardLockKit

struct LockRulesCommitmentTests {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }
    let now = at(2026, 1, 9, 12, 0)

    @Test func notCommittedByDefault() {
        #expect(!rules(.default).isCommitted(now: now))
        #expect(rules(.default).commitRemaining(now: now) == nil)
    }

    @Test func commitSetsFutureEnd() {
        let c = rules(.default).commit(duration: 3600, now: now)
        let r = rules(c)
        #expect(r.isCommitted(now: now))
        #expect(r.commitRemaining(now: now) == 3600)
        #expect(!r.isCommitted(now: now.addingTimeInterval(3601)))
    }

    /// nil means never committed; 0 means committed and expired. Different
    /// states -- StatusView must not conflate them.
    @Test func expiredCommitmentReportsZeroNotNil() {
        let c = rules(.default).commit(duration: 3600, now: now)
        let r = rules(c)
        #expect(r.commitRemaining(now: now.addingTimeInterval(7200)) == 0)
        #expect(r.commitRemaining(now: now.addingTimeInterval(7200)) != nil)
    }

    @Test func commitIsExtendOnly() throws {
        let first = rules(.default).commit(duration: 7200, now: now)
        let shorter = rules(first).commit(duration: 60, now: now)
        #expect(shorter.commitUntil == first.commitUntil)      // never shortens
        let longer = rules(first).commit(duration: 10_000, now: now)
        let a = try #require(longer.commitUntil)
        let b = try #require(first.commitUntil)
        #expect(a > b)
    }

    @Test func commitDropsQueuedWeakenings() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(
            value: "23:45", effectiveAt: now.addingTimeInterval(3600))
        let committed = rules(c).commit(duration: 3600, now: now)
        #expect(committed.pendingChanges.isEmpty)
    }

    @Test func weakeningIsRejectedWhileCommitted() {
        let c = rules(.default).commit(duration: 3600, now: now)
        let res = rules(c).apply(changes: ["cutoff_fri": "23:45"], now: now)
        #expect(res.rejected == ["cutoff_fri"])
        #expect(res.deferred.isEmpty)
        #expect(res.config.cutoffFri == "23:30")
        #expect(res.config.pendingChanges.isEmpty)   // not even queued
    }

    @Test func tighteningStillWorksWhileCommitted() {
        let c = rules(.default).commit(duration: 3600, now: now)
        let res = rules(c).apply(changes: ["cutoff_fri": "22:00"], now: now)
        #expect(res.applied == ["cutoff_fri"])
        #expect(res.rejected.isEmpty)
        #expect(res.config.cutoffFri == "22:00")
    }

    @Test func commitDurationIsClamped() {
        let tiny = rules(.default).commit(duration: 1, now: now)
        #expect(tiny.commitUntil == now.addingTimeInterval(60))
        let huge = rules(.default).commit(duration: 100 * 365 * 24 * 3600, now: now)
        #expect(huge.commitUntil == now.addingTimeInterval(10 * 365 * 24 * 3600))
    }
}
