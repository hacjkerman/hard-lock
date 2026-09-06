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

/// The rules document. Keys mirror the desktop app's config.json.
///
/// Amendment C: key *names* mirror, but values do not round-trip for free --
/// the desktop writes naive local timestamps and can queue non-String values.
/// ConfigStore is what absorbs that; see its decoding notes.
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

    public init(cutoffMon: String?, cutoffTue: String?, cutoffWed: String?,
                cutoffThu: String?, cutoffFri: String?, cutoffSat: String?,
                cutoffSun: String?, dayResetHour: Int, editCooldownHours: Int,
                pendingChanges: [String: PendingChange], commitUntil: Date?) {
        self.cutoffMon = cutoffMon
        self.cutoffTue = cutoffTue
        self.cutoffWed = cutoffWed
        self.cutoffThu = cutoffThu
        self.cutoffFri = cutoffFri
        self.cutoffSat = cutoffSat
        self.cutoffSun = cutoffSun
        self.dayResetHour = dayResetHour
        self.editCooldownHours = editCooldownHours
        self.pendingChanges = pendingChanges
        self.commitUntil = commitUntil
    }

    public static let `default` = LockConfig(
        cutoffMon: "23:30", cutoffTue: "23:30", cutoffWed: "23:30",
        cutoffThu: "23:30", cutoffFri: "23:30", cutoffSat: "23:30",
        cutoffSun: "23:30",
        dayResetHour: 4, editCooldownHours: 24,
        pendingChanges: [:], commitUntil: nil
    )

    /// Config keys for each weekday, Monday-first to match the Calendar
    /// arithmetic in LockRules.
    public static let weekdayKeys = ["cutoff_mon", "cutoff_tue", "cutoff_wed",
                                     "cutoff_thu", "cutoff_fri", "cutoff_sat",
                                     "cutoff_sun"]

    /// Amendment G: `apply` must reject keys it cannot actually write, rather
    /// than reporting a silent no-op as "applied".
    public static func isKnownKey(_ key: String) -> Bool {
        weekdayKeys.contains(key)
    }

    /// 0 = Monday ... 6 = Sunday.
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

/// Decodes a value, yielding nil instead of throwing when it does not parse.
/// Used to keep one malformed `pending_changes` entry from discarding the
/// entire rules document (Amendment C).
struct Failable<T: Decodable>: Decodable {
    let value: T?
    init(from decoder: Decoder) throws {
        value = try? T(from: decoder)
    }
}

public extension LockConfig {
    /// Amendment C: tolerant decoding.
    ///
    /// - A missing scalar falls back to its default rather than throwing, so a
    ///   config written by an older build still loads.
    /// - A malformed `pending_changes` entry is dropped and the rest survive.
    ///   The desktop does exactly this and has two tests for it; Codable's
    ///   all-or-nothing default would instead reset every rule the user has.
    /// - A `pending_changes` value that is not a dictionary at all is still a
    ///   hard error: that is genuine corruption, not one bad row.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let fallback = LockConfig.default

        self.cutoffMon = try c.decodeIfPresent(String.self, forKey: .cutoffMon)
        self.cutoffTue = try c.decodeIfPresent(String.self, forKey: .cutoffTue)
        self.cutoffWed = try c.decodeIfPresent(String.self, forKey: .cutoffWed)
        self.cutoffThu = try c.decodeIfPresent(String.self, forKey: .cutoffThu)
        self.cutoffFri = try c.decodeIfPresent(String.self, forKey: .cutoffFri)
        self.cutoffSat = try c.decodeIfPresent(String.self, forKey: .cutoffSat)
        self.cutoffSun = try c.decodeIfPresent(String.self, forKey: .cutoffSun)

        self.dayResetHour = try c.decodeIfPresent(Int.self, forKey: .dayResetHour)
            ?? fallback.dayResetHour
        self.editCooldownHours = try c.decodeIfPresent(Int.self, forKey: .editCooldownHours)
            ?? fallback.editCooldownHours
        self.commitUntil = try c.decodeIfPresent(Date.self, forKey: .commitUntil)

        let raw = try c.decodeIfPresent([String: Failable<PendingChange>].self,
                                        forKey: .pendingChanges) ?? [:]
        self.pendingChanges = raw.compactMapValues { $0.value }
    }
}
