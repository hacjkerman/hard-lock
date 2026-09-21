import SwiftUI

@main
struct HardLockApp: App {
    @StateObject private var auth = AuthorizationService()

    var body: some Scene {
        WindowGroup {
            Text("Hard Lock")
                .environmentObject(auth)
                .task { await auth.requestAuthorization() }
        }
    }
}
