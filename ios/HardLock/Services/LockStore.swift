import Foundation
import HardLockKit

/// Owns the config for the UI: activates due changes on load, persists edits,
/// and re-registers schedules whenever the rules change.
@MainActor
public final class LockStore: ObservableObject {
    @Published public private(set) var config: LockConfig
    @Published public private(set) var lastError: String?

    private let store: ConfigStore
    private let schedules: ScheduleManager

    public init(store: ConfigStore) {
        self.store = store
        self.schedules = ScheduleManager(store: store)
        self.config = store.load()
        reload()
    }

    public var rules: LockRules { LockRules(config: config) }

    /// Activate any queued change that has come due, then persist.
    public func reload() {
        let refreshed = LockRules(config: store.load()).refreshPending(now: Date())
        config = refreshed
        persist()
    }

    @discardableResult
    public func apply(_ changes: [String: String?]) -> ApplyResult {
        let result = rules.apply(changes: changes, now: Date())
        config = result.config
        persist()
        return result
    }

    public func commit(_ duration: TimeInterval) {
        config = rules.commit(duration: duration, now: Date())
        persist()
    }

    private func persist() {
        do {
            try store.save(config)
            try schedules.refreshSchedules()
            lastError = nil
        } catch {
            lastError = error.localizedDescription    // surfaced in StatusView
        }
    }
}
