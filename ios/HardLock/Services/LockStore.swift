import Combine
import FamilyControls
import Foundation
import HardLockKit

/// The app is the only config writer. A failed read never silently replaces a
/// commitment with defaults; a failed write never publishes an unsaved edit.
@MainActor
public final class LockStore: ObservableObject {
    @Published public private(set) var config = LockConfig.default
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
            let saved: LockConfig
            do { saved = try store.loadStrict() }
            catch let error as CocoaError where error.code == .fileReadNoSuchFile {
                saved = .default
                try store.save(saved)
            }
            let refreshed = LockRules(config: saved).refreshPending(now: Date())
            if refreshed != saved { try store.save(refreshed) }
            config = refreshed
            isReady = true
            try configure(store: store)
            lastError = nil
        } catch { fail(error.localizedDescription) }
    }

    @discardableResult
    public func apply(_ changes: [String: String?]) -> ApplyResult {
        guard isReady else { return rules.apply(changes: [:], now: Date()) }
        let result = rules.apply(changes: changes, now: Date())
        persist(result.config)
        return result
    }

    public func commit(_ duration: TimeInterval) {
        guard isReady else { return }
        persist(rules.commit(duration: duration, now: Date()))
    }

    public func cancelPending(_ key: String) {
        guard isReady else { return }
        var updated = config
        updated.pendingChanges.removeValue(forKey: key)
        persist(updated)
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

    private func persist(_ updated: LockConfig) {
        guard let store else { return }
        do {
            try store.save(updated)
            config = updated
            try configure(store: store)
            lastError = nil
        } catch { fail(error.localizedDescription) }
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

    private func reconcile(now: Date) {
        let locked = AuthorizationCenter.shared.authorizationStatus == .approved && rules.isLockedOut(now: now)
        if locked && !shields.isShielding { shields.shieldEverything() }
        if !locked { shields.clear() }
    }

    private func fail(_ message: String) {
        isReady = false
        lastError = message
        if let store { ScheduleManager(store: store).stopAll() }
        shields.clear()
    }
}
