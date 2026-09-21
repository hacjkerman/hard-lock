import SwiftUI

@main
struct HardLockApp: App {
    @StateObject private var auth = AuthorizationService()

    var body: some Scene {
        WindowGroup {
            VStack(spacing: 20) {
                Text("Hard Lock").font(.largeTitle)
                Button("Shield everything") { ShieldController().shieldEverything() }
                Button("Clear shields") { ShieldController().clear() }
            }
            .environmentObject(auth)
            .task { await auth.requestAuthorization() }
        }
    }
}
