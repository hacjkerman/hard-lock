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
