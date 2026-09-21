import Foundation

/// The rules engine. Pure logic: no Apple frameworks, no I/O, and every API
/// takes an explicit `now`, so behaviour is fully testable without waiting.
public struct LockRules {
    public let config: LockConfig
    private let calendar: Calendar

    public init(config: LockConfig, calendar: Calendar = .current) {
        self.config = config
        self.calendar = calendar
    }

    /// "23:30" -> 1410 minutes past midnight. nil if malformed.
    public static func minutes(fromHHMM s: String) -> Int? {
        let parts = s.split(separator: ":")
        guard parts.count == 2,
              let h = Int(parts[0]), let m = Int(parts[1]),
              (0..<24).contains(h), (0..<60).contains(m) else { return nil }
        return h * 60 + m
    }

    /// Start of the logical day containing `now` — the most recent day-reset
    /// boundary at or before it.
    public func logicalDayStart(now: Date) -> Date {
        let midnight = calendar.startOfDay(for: now)
        let reset = calendar.date(byAdding: .hour, value: config.dayResetHour, to: midnight)!
        return now < reset ? calendar.date(byAdding: .day, value: -1, to: reset)! : reset
    }

    /// 0 = Monday … 6 = Sunday, for the logical day containing `now`.
    public func logicalWeekdayIndex(now: Date) -> Int {
        let start = logicalDayStart(now: now)
        // Calendar.weekday: 1 = Sunday … 7 = Saturday. Convert to Monday-first.
        let weekday = calendar.component(.weekday, from: start)
        return (weekday + 5) % 7
    }

    /// When the current logical day ends (the next day reset).
    public func resetDate(now: Date) -> Date {
        calendar.date(byAdding: .day, value: 1, to: logicalDayStart(now: now))!
    }

    /// The absolute instant of this logical day's cutoff, or nil if none is set.
    /// A cutoff earlier than the day reset (e.g. 01:30) belongs to the *end* of
    /// the window, so it lands on the following calendar date.
    public func cutoffDate(now: Date) -> Date? {
        let idx = logicalWeekdayIndex(now: now)
        guard let hhmm = config.cutoff(forWeekdayIndex: idx),
              let mins = LockRules.minutes(fromHHMM: hhmm) else { return nil }

        let start = logicalDayStart(now: now)               // e.g. Fri 04:00
        let dayMidnight = calendar.startOfDay(for: start)   // Fri 00:00
        var cutoff = calendar.date(byAdding: .minute, value: mins, to: dayMidnight)!
        if mins < config.dayResetHour * 60 {
            // 01:30 with a 04:00 reset => the small hours of the NEXT date.
            cutoff = calendar.date(byAdding: .day, value: 1, to: cutoff)!
        }
        return cutoff
    }

    /// True while inside this logical day's lockout window (cutoff -> reset).
    public func isLockedOut(now: Date) -> Bool {
        guard let cutoff = cutoffDate(now: now) else { return false }
        return now >= cutoff && now < resetDate(now: now)
    }
}
public struct ApplyResult: Equatable {
    public let applied: [String]
    public let deferred: [String]
    public let rejected: [String]
    public let config: LockConfig
}

public extension LockRules {

    /// Minutes from the day reset to this cutoff, wrapping past midnight — so a
    /// later *night* sorts after an earlier one even when the clock time is
    /// smaller (01:30 is later than 23:30 with an 04:00 reset).
    func logicalCutoffMinute(_ hhmm: String) -> Int? {
        guard let m = LockRules.minutes(fromHHMM: hhmm) else { return nil }
        return ((m - config.dayResetHour * 60) % 1440 + 1440) % 1440
    }

    /// A later cutoff (or removing it entirely) relaxes the lock.
    func cutoffWeakens(oldValue: String?, newValue: String?) -> Bool {
        if newValue == nil { return oldValue != nil }   // removing a limit
        guard let oldValue else { return false }        // adding one is tightening
        guard let a = logicalCutoffMinute(oldValue),
              let b = logicalCutoffMinute(newValue!) else { return false }
        return b > a
    }

    /// Tightening applies immediately; weakening is queued for the cooldown;
    /// while committed, weakening is rejected outright rather than queued.
    func apply(changes: [String: String?], now: Date) -> ApplyResult {
        var updated = config
        var applied: [String] = [], deferred: [String] = [], rejected: [String] = []
        let committed = isCommitted(now: now)
        let effectiveAt = now.addingTimeInterval(TimeInterval(config.editCooldownHours) * 3600)

        for key in changes.keys.sorted() {
            let newValue = changes[key] ?? nil
            let oldValue = updated.value(forKey: key)
            let queued = updated.pendingChanges[key]

            if newValue == oldValue && queued == nil { continue }
            // Re-submitting a value already queued must not re-defer or cancel it.
            if let queued, queued.value == newValue { continue }

            if cutoffWeakens(oldValue: oldValue, newValue: newValue) {
                if committed { rejected.append(key); continue }
                updated.pendingChanges[key] = PendingChange(value: newValue, effectiveAt: effectiveAt)
                deferred.append(key)
            } else {
                updated = updated.setting(newValue, forKey: key)
                updated.pendingChanges.removeValue(forKey: key)
                applied.append(key)
            }
        }
        return ApplyResult(applied: applied, deferred: deferred,
                           rejected: rejected, config: updated)
    }

    /// Activate any queued change whose cooldown has elapsed.
    func refreshPending(now: Date) -> LockConfig {
        var updated = config
        for (key, change) in config.pendingChanges where change.effectiveAt <= now {
            updated = updated.setting(change.value, forKey: key)
            updated.pendingChanges.removeValue(forKey: key)
        }
        return updated
    }
}
public extension LockRules {

    /// A commitment is active until `commitUntil` passes. While active, nothing
    /// can be weakened — only tightened.
    func isCommitted(now: Date) -> Bool {
        guard let until = config.commitUntil else { return false }
        return now < until
    }

    func commitRemaining(now: Date) -> TimeInterval? {
        guard let until = config.commitUntil else { return nil }
        return max(0, until.timeIntervalSince(now))
    }

    /// Lock in for a term. Extend-only: never shortens an existing commitment.
    /// Queued weakenings are dropped — they cannot benefit you during the term.
    func commit(duration: TimeInterval, now: Date) -> LockConfig {
        let clamped = min(max(duration, 60), 10 * 365 * 24 * 3600)   // 1 min … ~10 years
        var updated = config
        let end = now.addingTimeInterval(clamped)
        updated.commitUntil = max(end, config.commitUntil ?? end)
        updated.pendingChanges = [:]
        return updated
    }
}
public extension LockRules {

    /// Every distinct cutoff time in the schedule. A DeviceActivitySchedule
    /// repeats daily rather than weekly, so we register one activity per
    /// distinct time (at most seven) instead of one per weekday.
    func distinctCutoffTimes() -> [String] {
        var seen = Set<String>()
        for i in 0..<7 {
            if let t = config.cutoff(forWeekdayIndex: i), LockRules.minutes(fromHHMM: t) != nil {
                seen.insert(t)
            }
        }
        return seen.sorted()
    }

    /// True when the logical day containing `now` uses this cutoff time — the
    /// check the extension makes before shielding, since it is woken by every
    /// registered schedule regardless of which day it is.
    func cutoffApplies(hhmm: String, now: Date) -> Bool {
        config.cutoff(forWeekdayIndex: logicalWeekdayIndex(now: now)) == hhmm
    }
}
