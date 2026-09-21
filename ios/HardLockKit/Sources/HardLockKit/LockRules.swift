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
        guard s.utf8.count == 5, s.utf8.enumerated().allSatisfy({ $0.offset == 2 ? $0.element == 58 : (48...57).contains($0.element) }) else { return nil }
        let parts = s.split(separator: ":")
        guard parts.count == 2,
              let h = Int(parts[0]), let m = Int(parts[1]),
              (0..<24).contains(h), (0..<60).contains(m) else { return nil }
        return h * 60 + m
    }

    /// Start of the logical day containing `now` — the most recent day-reset
    /// boundary at or before it.
    public func logicalDayStart(now: Date) -> Date {
        let reset = wallTime(hour: config.dayResetHour, minute: 0, on: now)
        if now >= reset { return reset }
        let yesterday = calendar.date(byAdding: .day, value: -1, to: calendar.startOfDay(for: now))!
        return wallTime(hour: config.dayResetHour, minute: 0, on: yesterday)
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
        let tomorrow = calendar.date(byAdding: .day, value: 1, to: calendar.startOfDay(for: logicalDayStart(now: now)))!
        return wallTime(hour: config.dayResetHour, minute: 0, on: tomorrow)
    }

    /// The absolute instant of this logical day's cutoff, or nil if none is set.
    /// A cutoff earlier than the day reset (e.g. 01:30) belongs to the *end* of
    /// the window, so it lands on the following calendar date.
    public func cutoffDate(now: Date) -> Date? {
        let idx = logicalWeekdayIndex(now: now)
        guard let hhmm = config.cutoff(forWeekdayIndex: idx),
              let mins = LockRules.minutes(fromHHMM: hhmm) else { return nil }

        var day = calendar.startOfDay(for: logicalDayStart(now: now))
        if mins < config.dayResetHour * 60 {
            day = calendar.date(byAdding: .day, value: 1, to: day)!
        }
        return wallTime(hour: mins / 60, minute: mins % 60, on: day)
    }

    /// Resolve local clock components instead of adding elapsed hours over DST.
    /// Missing times move forward; repeated times use the first occurrence.
    private func wallTime(hour: Int, minute: Int, on day: Date) -> Date {
        calendar.date(bySettingHour: hour, minute: minute, second: 0, of: day,
                      matchingPolicy: .nextTime, repeatedTimePolicy: .first,
                      direction: .forward)!
    }

    /// True while inside
    /// this logical day's lockout window (cutoff -> reset).
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
        var updated = refreshPending(now: now)
        var applied: [String] = [], deferred: [String] = [], rejected: [String] = []
        let committed = isCommitted(now: now)
        let effectiveAt = now.addingTimeInterval(TimeInterval(config.editCooldownHours) * 3600)

        for key in changes.keys.sorted() {
            let newValue = changes[key] ?? nil
            guard LockConfig.weekdayKeys.contains(key),
                  newValue == nil || Self.minutes(fromHHMM: newValue!) != nil else {
                rejected.append(key)
                continue
            }
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
        if isCommitted(now: now) {
            updated.pendingChanges = [:]
            return updated
        }
        for (key, change) in config.pendingChanges where change.effectiveAt <= now {
            guard LockConfig.weekdayKeys.contains(key),
                  change.value == nil || Self.minutes(fromHHMM: change.value!) != nil else {
                updated.pendingChanges.removeValue(forKey: key)
                continue
            }
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

public extension LockRules {
    /// Register future values too so a closed app can enforce a matured edit.
    /// At most fourteen cutoff schedules, plus one pending-change wakeup.
    func monitoringCutoffTimes(now: Date) -> [String] {
        let effective = refreshPending(now: now)
        var times = Set(LockRules(config: effective, calendar: calendar).distinctCutoffTimes())
        for change in effective.pendingChanges.values {
            if let value = change.value, Self.minutes(fromHHMM: value) != nil { times.insert(value) }
        }
        return times.sorted()
    }
}

/// A daily interval supported by DeviceActivity's minimum duration. Warnings
/// let the monitor reconcile at cutoffs less than fifteen minutes before reset.
public struct MonitoringWindow: Equatable {
    public let startMinute: Int
    public let endMinute: Int
    public let warningMinutes: Int?
}

public extension LockRules {
    func monitoringWindow(hhmm: String) -> MonitoringWindow? {
        guard let mins = Self.minutes(fromHHMM: hhmm), (0..<24).contains(config.dayResetHour) else { return nil }
        let reset = config.dayResetHour * 60
        let duration = (reset - mins + 1440) % 1440
        let short = duration < 15
        return MonitoringWindow(
            startMinute: short ? (reset - 15 + 1440) % 1440 : mins,
            endMinute: reset,
            warningMinutes: short && duration > 0 ? duration : nil
        )
    }
}
