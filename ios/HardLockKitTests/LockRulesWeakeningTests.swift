import Testing
import Foundation
@testable import HardLockKit

struct LockRulesWeakeningTests {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }
    let now = at(2026, 1, 9, 12, 0)

    @Test func earlierCutoffIsTighteningAndAppliesNow() {
        let res = rules(.default).apply(changes: ["cutoff_fri": "22:00"], now: now)
        #expect(res.applied == ["cutoff_fri"])
        #expect(res.deferred.isEmpty)
        #expect(res.config.cutoffFri == "22:00")
        #expect(res.config.pendingChanges.isEmpty)
    }

    @Test func laterCutoffIsWeakeningAndIsQueued() throws {
        let res = rules(.default).apply(changes: ["cutoff_fri": "23:45"], now: now)
        #expect(res.deferred == ["cutoff_fri"])
        #expect(res.applied.isEmpty)
        #expect(res.config.cutoffFri == "23:30")             // not yet in force
        let pending = try #require(res.config.pendingChanges["cutoff_fri"])
        #expect(pending.value == "23:45")
        #expect(pending.effectiveAt == now.addingTimeInterval(24 * 3600))
    }

    /// The bug found on desktop: 01:30 is EARLIER on the clock but LATER at
    /// night, so it must count as weakening.
    @Test func afterMidnightCutoffCountsAsLater() {
        let r = rules(.default)
        #expect(r.cutoffWeakens(oldValue: "23:30", newValue: "01:30"))
        #expect(!r.cutoffWeakens(oldValue: "01:30", newValue: "23:30"))
    }

    @Test func removingACutoffIsWeakening() {
        let r = rules(.default)
        #expect(r.cutoffWeakens(oldValue: "23:30", newValue: nil))
        #expect(!r.cutoffWeakens(oldValue: nil, newValue: "23:30"))
    }

    @Test func duePendingChangeActivates() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(
            value: "23:45", effectiveAt: now.addingTimeInterval(-60))   // already due
        let updated = rules(c).refreshPending(now: now)
        #expect(updated.cutoffFri == "23:45")
        #expect(updated.pendingChanges.isEmpty)
    }

    @Test func notYetDuePendingChangeStays() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(
            value: "23:45", effectiveAt: now.addingTimeInterval(3600))
        let updated = rules(c).refreshPending(now: now)
        #expect(updated.cutoffFri == "23:30")
        #expect(updated.pendingChanges["cutoff_fri"] != nil)
    }

    @Test func reapplyingAQueuedValueIsIdempotent() throws {
        let first = rules(.default).apply(changes: ["cutoff_fri": "23:45"], now: now)
        let effectiveAt = try #require(first.config.pendingChanges["cutoff_fri"]).effectiveAt
        let again = LockRules(config: first.config, calendar: testCalendar)
            .apply(changes: ["cutoff_fri": "23:45"], now: now.addingTimeInterval(600))
        #expect(again.deferred.isEmpty)   // no re-queue
        #expect(again.applied.isEmpty)    // and not cancelled either
        #expect(again.config.pendingChanges["cutoff_fri"]?.effectiveAt == effectiveAt)
    }

    // MARK: - Amendment I additions

    /// The "I changed my mind" path: a tightening cancels a queued weakening.
    /// Implemented on both platforms, never covered here until now.
    @Test func tighteningCancelsAQueuedWeakening() {
        let queued = rules(.default).apply(changes: ["cutoff_fri": "23:45"], now: now)
        #expect(queued.config.pendingChanges["cutoff_fri"] != nil)

        let res = LockRules(config: queued.config, calendar: testCalendar)
            .apply(changes: ["cutoff_fri": "22:00"], now: now)
        #expect(res.applied == ["cutoff_fri"])
        #expect(res.config.cutoffFri == "22:00")
        #expect(res.config.pendingChanges.isEmpty)   // queue dropped
    }

    /// Desktop tests this explicitly: re-submitting the value already in force
    /// cancels a queued change rather than doing nothing.
    @Test func reapplyingTheCurrentValueCancelsAQueuedChange() {
        let queued = rules(.default).apply(changes: ["cutoff_fri": "23:45"], now: now)
        let res = LockRules(config: queued.config, calendar: testCalendar)
            .apply(changes: ["cutoff_fri": "23:30"], now: now)   // back to current
        #expect(res.applied == ["cutoff_fri"])
        #expect(res.config.pendingChanges.isEmpty)
        #expect(res.config.cutoffFri == "23:30")
    }

    /// The API takes a dictionary but was only ever tested with one entry.
    @Test func multipleKeysInOneCall() {
        let res = rules(.default).apply(
            changes: ["cutoff_mon": "22:00", "cutoff_tue": "23:45", "cutoff_wed": nil],
            now: now)
        #expect(res.applied == ["cutoff_mon"])
        #expect(res.deferred.sorted() == ["cutoff_tue", "cutoff_wed"])
        #expect(res.config.cutoffMon == "22:00")
        #expect(res.config.cutoffTue == "23:30")            // still queued
        #expect(res.config.cutoffWed == "23:30")
        #expect(res.config.pendingChanges.count == 2)
    }

    /// Amendment G: previously reported as "applied" while doing nothing.
    @Test func unknownKeysAreReportedNotSilentlyDropped() {
        let res = rules(.default).apply(
            changes: ["edit_cooldown_hours": "1", "cutoff_fri": "22:00"], now: now)
        #expect(res.applied == ["cutoff_fri"])
        #expect(res.unknown == ["edit_cooldown_hours"])
        #expect(res.config.editCooldownHours == 24)         // unchanged
    }

    @Test func noOpChangeDoesNothing() {
        let res = rules(.default).apply(changes: ["cutoff_fri": "23:30"], now: now)
        #expect(res.applied.isEmpty)
        #expect(res.deferred.isEmpty)
        #expect(res.config == LockConfig.default)
    }
}
