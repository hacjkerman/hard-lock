import Foundation

/// One day's cutoff as the editor sheet holds it. Nothing here touches the
/// saved rules; only an explicit Save passes `value` to `LockRules.apply`.
public struct CutoffDraft: Equatable {
    public static let defaultTime = "23:30"

    public let dayIndex: Int
    /// The rule in force when the sheet opened.
    public let saved: String?
    /// A queued change for this day, if any.
    public let scheduled: PendingChange?
    /// What the day is heading towards: the scheduled value, else the saved one.
    public let initialValue: String?
    public var isEnabled: Bool
    /// Kept while the day is switched off, so switching back on restores it.
    public var time: String

    public init(config: LockConfig, dayIndex: Int) {
        self.dayIndex = dayIndex
        saved = config.cutoff(forWeekdayIndex: dayIndex)
        scheduled = config.pendingChanges[LockConfig.weekdayKeys[dayIndex]]
        if let scheduled { initialValue = scheduled.value } else { initialValue = saved }
        isEnabled = initialValue != nil
        time = initialValue ?? saved ?? Self.defaultTime
    }

    public var key: String { LockConfig.weekdayKeys[dayIndex] }
    public var value: String? { isEnabled ? time : nil }
    public var hasChanges: Bool { value != initialValue }
}

/// What saving a draft would do right now.
public enum CutoffSaveOutcome: Equatable {
    case noChange
    case invalidResetHour
    case appliesNow(locksNow: Bool)
    /// Returns to the saved value, withdrawing the queued change. `keeps` is
    /// the effective saved value at the preview's `now`.
    case cancelsScheduled(keeps: String?)
    /// `keeps` stays in force until `until`.
    case waits(until: Date, keeps: String?, replacesScheduled: Bool)
    case blockedByCommitment(until: Date)

    public var canSave: Bool {
        switch self {
        case .appliesNow, .cancelsScheduled, .waits: return true
        case .noChange, .invalidResetHour, .blockedByCommitment: return false
        }
    }

    /// Same consequence for the user; a cooldown deadline moving on with the
    /// clock doesn't make a preview stale.
    public func isEquivalent(to other: CutoffSaveOutcome) -> Bool {
        if case .waits(_, let keptA, let a) = self, case .waits(_, let keptB, let b) = other {
            return keptA == keptB && a == b
        }
        return self == other
    }
}

public enum CutoffSaveDecision: Equatable {
    case nothing
    /// The rules or clock moved since the preview; show this one instead.
    case outdated(CutoffSaveOutcome)
    case apply(ApplyResult)
}

public extension LockRules {
    func preview(_ draft: CutoffDraft, now: Date) -> CutoffSaveOutcome {
        guard draft.hasChanges else { return .noChange }
        let current = refreshPending(now: now)
        let key = draft.key
        let result = apply(changes: [key: draft.value], now: now)

        if result.rejected.contains(key) {
            if let value = draft.value, !isValidCutoff(value) { return .invalidResetHour }
            return .blockedByCommitment(until: config.commitUntil ?? now)
        }
        if result.deferred.contains(key), let queued = result.config.pendingChanges[key] {
            return .waits(until: queued.effectiveAt, keeps: current.value(forKey: key),
                          replacesScheduled: current.pendingChanges[key] != nil)
        }
        if result.applied.contains(key) {
            if draft.value == current.value(forKey: key) { return .cancelsScheduled(keeps: draft.value) }
            let before = LockRules(config: current, calendar: calendar).isLockedOut(now: now)
            let after = LockRules(config: result.config, calendar: calendar).isLockedOut(now: now)
            return .appliesNow(locksNow: after && !before)
        }
        return .noChange
    }

    /// Save re-checks the draft against the rules at `now`; it applies exactly
    /// once, and only if the consequence is the one the user was shown.
    func decideSave(_ draft: CutoffDraft, expecting shown: CutoffSaveOutcome, now: Date) -> CutoffSaveDecision {
        let fresh = preview(draft, now: now)
        guard fresh.isEquivalent(to: shown) else { return .outdated(fresh) }
        guard fresh.canSave else { return .nothing }
        return .apply(apply(changes: [draft.key: draft.value], now: now))
    }
}

public extension LockRules {
    /// Withdraws the queued change for a day only if the effective rules at
    /// `now` still match what the user confirmed; nil when they have moved on
    /// (the change matured, or was replaced or dropped).
    func withdrawScheduled(key: String, shownSaved: String?, shownChange: PendingChange, now: Date) -> LockConfig? {
        let current = refreshPending(now: now)
        guard current.value(forKey: key) == shownSaved,
              current.pendingChanges[key] == shownChange else { return nil }
        return cancelPending(key: key, now: now)
    }
}

/// One row of the weekly overview.
public struct CutoffDaySummary: Equatable, Identifiable {
    public let dayIndex: Int
    public let saved: String?
    public let scheduled: PendingChange?
    public let isToday: Bool
    public var id: Int { dayIndex }
}

public extension LockRules {
    func daySummaries(now: Date) -> [CutoffDaySummary] {
        let effective = refreshPending(now: now)
        let today = logicalWeekdayIndex(now: now)
        return (0..<7).map { i in
            CutoffDaySummary(dayIndex: i,
                             saved: effective.cutoff(forWeekdayIndex: i),
                             scheduled: effective.pendingChanges[LockConfig.weekdayKeys[i]],
                             isToday: i == today)
        }
    }

    /// A valid cutoff before the reset hour falls on the next calendar morning.
    func isAfterMidnight(_ hhmm: String) -> Bool {
        guard isValidCutoff(hhmm), let minutes = Self.minutes(fromHHMM: hhmm) else { return false }
        return minutes < config.dayResetHour * 60
    }
}

/// Tonight's schedule, kept apart from whether the app can enforce it.
public enum TonightStatus: Equatable {
    case lockedOut(until: Date)
    case lockoutNotEnforced(until: Date)
    case locksAt(Date, enforced: Bool)
    case noCutoff
}

public extension LockRules {
    /// Mirrors `shouldShield`: only an authorized lockout is reported as locked.
    func tonightStatus(authorized: Bool, now: Date) -> TonightStatus {
        if isLockedOut(now: now) {
            let reset = resetDate(now: now)
            return authorized ? .lockedOut(until: reset) : .lockoutNotEnforced(until: reset)
        }
        if let cutoff = cutoffDate(now: now) { return .locksAt(cutoff, enforced: authorized) }
        return .noCutoff
    }
}

/// Whether an edit reached disk, and separately whether it is being enforced.
public enum PersistOutcome: Equatable {
    case unchanged
    case saved
    case savedNotEnforced(String)
    case notSaved(String)

    public var isSaved: Bool {
        switch self {
        case .saved, .savedNotEnforced: return true
        case .unchanged, .notSaved: return false
        }
    }
}

public enum ConfigPersistence {
    /// Writes only a real change, then re-arms enforcement. An unchanged
    /// config is neither saved nor re-registered.
    public static func persist(_ updated: LockConfig, over current: LockConfig,
                               save: (LockConfig) throws -> Void,
                               arm: () throws -> Void) -> PersistOutcome {
        guard updated != current else { return .unchanged }
        do { try save(updated) } catch { return .notSaved(error.localizedDescription) }
        do { try arm() } catch { return .savedNotEnforced(error.localizedDescription) }
        return .saved
    }
}
