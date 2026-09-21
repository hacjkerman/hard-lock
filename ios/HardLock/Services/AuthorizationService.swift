import Combine

import Foundation
import FamilyControls

/// Wraps Screen Time authorization. Without this the shields silently do
/// nothing, so the UI surfaces the status prominently rather than hiding it.
@MainActor
public final class AuthorizationService: ObservableObject {
    @Published public private(set) var status: AuthorizationStatus = .notDetermined
    @Published public private(set) var lastError: String?

    public init() { refresh() }

    public func refresh() {
        status = AuthorizationCenter.shared.authorizationStatus
    }

    public func requestAuthorization() async {
        refresh()
        guard status != .approved else { return }
        do {
            // .individual = this device's own user, not a parent/child pairing.
            try await AuthorizationCenter.shared.requestAuthorization(for: .individual)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
        refresh()
    }
}
