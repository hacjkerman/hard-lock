import Foundation

/// One queued weakening: the value to apply, and when it becomes effective.
public struct PendingChange: Codable, Equatable {
    public let value: String?
    public let effectiveAt: Date

    public init(value: String?, effectiveAt: Date) {
        self.value = value
        self.effectiveAt = effectiveAt
    }

    enum CodingKeys: String, CodingKey {
        case value
        case effectiveAt = "effective_at"
    }
}

/// The rules document. Keys mirror the desktop app's config.json so a later
/// sync project can transport this unchanged.
public struct LockConfig: Codable, Equatable {
    public var cutoffMon: String?
    public var cutoffTue: String?
    public var cutoffWed: String?
    public var cutoffThu: String?
    public var cutoffFri: String?
    public var cutoffSat: String?
    public var cutoffSun: String?
    public var dayResetHour: Int
    public var editCooldownHours: Int
    public var pendingChanges: [String: PendingChange]
    public var commitUntil: Date?

    enum CodingKeys: String, CodingKey {
        case cutoffMon = "cutoff_mon"
        case cutoffTue = "cutoff_tue"
        case cutoffWed = "cutoff_wed"
        case cutoffThu = "cutoff_thu"
        case cutoffFri = "cutoff_fri"
        case cutoffSat = "cutoff_sat"
        case cutoffSun = "cutoff_sun"
        case dayResetHour = "day_reset_hour"
        case editCooldownHours = "edit_cooldown_hours"
        case pendingChanges = "pending_changes"
        case commitUntil = "commit_until"
    }

    public static let `default` = LockConfig(
        cutoffMon: "23:30", cutoffTue: "23:30", cutoffWed: "23:30",
        cutoffThu: "23:30", cutoffFri: "23:30", cutoffSat: "23:30",
        cutoffSun: "23:30",
        dayResetHour: 4, editCooldownHours: 24,
        pendingChanges: [:], commitUntil: nil
    )

    /// Config keys for each weekday, Monday-first to match Calendar arithmetic
    /// used in LockRules.
    public static let weekdayKeys = ["cutoff_mon", "cutoff_tue", "cutoff_wed",
                                     "cutoff_thu", "cutoff_fri", "cutoff_sat",
                                     "cutoff_sun"]

    /// 0 = Monday … 6 = Sunday.
    public func cutoff(forWeekdayIndex i: Int) -> String? {
        switch i {
        case 0: return cutoffMon
        case 1: return cutoffTue
        case 2: return cutoffWed
        case 3: return cutoffThu
        case 4: return cutoffFri
        case 5: return cutoffSat
        default: return cutoffSun
        }
    }

    public func withCutoff(_ value: String?, forWeekdayIndex i: Int) -> LockConfig {
        var c = self
        switch i {
        case 0: c.cutoffMon = value
        case 1: c.cutoffTue = value
        case 2: c.cutoffWed = value
        case 3: c.cutoffThu = value
        case 4: c.cutoffFri = value
        case 5: c.cutoffSat = value
        default: c.cutoffSun = value
        }
        return c
    }

    /// Value for a config key, used by the generic apply/weakening path.
    public func value(forKey key: String) -> String? {
        guard let i = LockConfig.weekdayKeys.firstIndex(of: key) else { return nil }
        return cutoff(forWeekdayIndex: i)
    }

    public func setting(_ value: String?, forKey key: String) -> LockConfig {
        guard let i = LockConfig.weekdayKeys.firstIndex(of: key) else { return self }
        return withCutoff(value, forWeekdayIndex: i)
    }
}

public enum ConfigValidationError: Error, LocalizedError {
    case invalidRules
    public var errorDescription: String? { "The saved lock rules are invalid. Shields have been cleared." }
}

public extension LockConfig {
    func validate() throws {
        guard (0..<24).contains(dayResetHour), (0...87600).contains(editCooldownHours),
              (0..<7).allSatisfy({ cutoff(forWeekdayIndex: $0).map { LockRules.minutes(fromHHMM: $0) != nil } ?? true }),
              pendingChanges.allSatisfy({ key, change in
                  Self.weekdayKeys.contains(key) && (change.value.map { LockRules.minutes(fromHHMM: $0) != nil } ?? true)
              }) else { throw ConfigValidationError.invalidRules }
    }
}
