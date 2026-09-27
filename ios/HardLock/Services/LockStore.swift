import Combine
import FamilyControls
import Foundation
import HardLockKit

/// The app is the only config writer. A failed read never silently replaces a
/// commitment with defaults; a failed write never publishes an unsaved edit.
@MainActor
public final class LockStore: ObservableObject {
    @Published public private(set) var config = LockConfig.freshInstall
    @Published public private(set) var lastError: String?
    @Published public private(set) var isReady = false

    private let store: ConfigStore?
    private let shields = ShieldController()

    public init(store: ConfigStore?) {
        self.store = store
        reload()
    }

    public var rules: LockRules { LockRules(config: config) }

    public func reload() {
        guard let store else {
            fail("Shared storage is unavailable. Check the App Group entitlement.")
            return
        }
        do {
            let saved = try store.loadOrCreate()
            let refreshed = LockRules(config: saved).refreshPending(now: Date())
            if refreshed != saved { try store.save(refreshed) }
            config = refreshed
            isReady = true
            try configure(store: store)
            lastError = nil
        } catch { fail(error.localizedDescription) }
    }

    public enum CutoffSaveResult {
        /// The rules moved since the preview; nothing was written.
        case outdated(CutoffSaveOutcome)
        case persisted(PersistOutcome)
    }

    /// Applies a draft once, against the rules as they are at this moment.
    public func saveCutoff(_ draft: CutoffDraft, expecting shown: CutoffSaveOutcome) -> CutoffSaveResult {
        guard isReady else { return .persisted(.notSaved(lastError ?? "Rules are unavailable.")) }
        switch rules.decideSave(draft, expecting: shown, now: Date()) {
        case .nothing: return .persisted(.unchanged)
        case .outdated(let fresh): return .outdated(fresh)
        case .apply(let result): return .persisted(persist(result.config))
        }
    }

    @discardableResult
    public func commit(_ duration: TimeInterval) -> PersistOutcome {
        guard isReady else { return .notSaved(lastError ?? "Rules are unavailable.") }
        return persist(rules.commit(duration: duration, now: Date()))
    }

    @discardableResult
    public func cancelPending(_ key: String) -> PersistOutcome {
        guard isReady else { return .notSaved(lastError ?? "Rules are unavailable.") }
        return persist(rules.cancelPending(key: key, now: Date()))
    }

    /// Withdraws a day's queued change only if the saved value and queued
    /// change are still the ones the user confirmed.
    public func withdrawScheduled(_ key: String, shownSaved: String?, shownChange: PendingChange) -> CutoffSaveResult? {
        guard isReady else { return .persisted(.notSaved(lastError ?? "Rules are unavailable.")) }
        guard let updated = rules.withdrawScheduled(key: key, shownSaved: shownSaved,
                                                    shownChange: shownChange, now: Date()) else { return nil }
        return .persisted(persist(updated))
    }

    /// No polling writes or schedule registration on ordinary clock ticks.
    public func tick(now: Date) {
        guard isReady else { return }
        if config.pendingChanges.values.contains(where: { $0.effectiveAt <= now }) {
            reload()
        } else {
            reconcile(now: now)
        }
    }

    /// Saving and enforcing are reported separately. Either failure still
    /// fails open: schedules stop and shields clear until Retry succeeds.
    private func persist(_ updated: LockConfig) -> PersistOutcome {
        guard let store else { return .notSaved("Shared storage is unavailable.") }
        let outcome = ConfigPersistence.persist(
            updated, over: config,
            save: { try store.save($0); config = $0 },
            arm: { try configure(store: store) })
        switch outcome {
        case .unchanged:
            break
        case .saved:
            lastError = nil
        case .savedNotEnforced(let message):
            fail("Saved, but enforcement couldn't start, so nothing is blocked until Retry succeeds. (\(message))")
        case .notSaved(let message):
            fail("Not saved, and nothing is blocked until Retry succeeds. (\(message))")
        }
        return outcome
    }

    private func configure(store: ConfigStore) throws {
        guard AuthorizationCenter.shared.authorizationStatus == .approved else {
            ScheduleManager(store: store).stopAll()
            shields.clear()
            return
        }
        try ScheduleManager(store: store).refreshSchedules()
        reconcile(now: Date())
    }

    /// Writes to ManagedSettings only when the shield state has to change.
    private func reconcile(now: Date) {
        let locked = rules.shouldShield(authorized: AuthorizationCenter.shared.authorizationStatus == .approved, now: now)
        if locked && !shields.isShielding { shields.shieldEverything() }
        if !locked && shields.isShielding { shields.clear() }
    }

    private func fail(_ message: String) {
        isReady = false
        lastError = message
        if let store { ScheduleManager(store: store).stopAll() }
        shields.clear()
    }
}
