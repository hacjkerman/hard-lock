import Foundation
import ManagedSettings

public extension ManagedSettingsStore.Name {
    /// A named store so Hard Lock's shields are independent of any other
    /// Screen Time settings the user has.
    static let hardLock = Self("hardLock")
}

/// Applies and clears the lockout. Shielding every category is the strongest
/// lockout iOS permits — emergency calling from the lock screen is unaffected.
public struct ShieldController {
    private let store: ManagedSettingsStore

    public init(store: ManagedSettingsStore = ManagedSettingsStore(named: .hardLock)) {
        self.store = store
    }

    public func shieldEverything() {
        store.shield.applicationCategories = .all()
        store.shield.webDomainCategories = .all()
    }

    public func clear() {
        store.shield.applicationCategories = nil
        store.shield.webDomainCategories = nil
    }

    public var isShielding: Bool {
        store.shield.applicationCategories != nil
    }
}
