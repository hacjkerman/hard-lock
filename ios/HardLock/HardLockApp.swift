import SwiftUI

@main
struct HardLockApp: App {
    @StateObject private var auth = AuthorizationService()

    var body: some Scene {
        WindowGroup {
            StatusView()
                .environmentObject(auth)
                .task { await auth.requestAuthorization() }
        }
    }
}
