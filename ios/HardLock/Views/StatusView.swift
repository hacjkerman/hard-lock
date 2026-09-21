import SwiftUI
import FamilyControls
import HardLockKit

struct StatusView: View {
    @EnvironmentObject private var auth: AuthorizationService
    @StateObject private var lock = LockStore(store: ConfigStore.shared()!)
    @State private var now = Date()

    private let tick = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    var body: some View {
        NavigationStack {
            List {
                if auth.status != .approved {
                    Section {
                        Label("Screen Time access not granted — nothing will be blocked",
                              systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.red)
                        Button("Grant access") { Task { await auth.requestAuthorization() } }
                    }
                }
                if let err = lock.lastError {
                    Section { Label(err, systemImage: "xmark.octagon.fill").foregroundStyle(.red) }
                }

                Section("Tonight") {
                    if lock.rules.isLockedOut(now: now) {
                        Label("Locked out until \(lock.rules.resetDate(now: now), style: .time)",
                              systemImage: "lock.fill")
                    } else if let cutoff = lock.rules.cutoffDate(now: now) {
                        Label("Locks at \(cutoff, style: .time) · \(cutoff, style: .relative)",
                              systemImage: "clock")
                    } else {
                        Label("No cutoff today", systemImage: "clock.badge.xmark")
                    }
                }

                if let remaining = lock.rules.commitRemaining(now: now),
                   lock.rules.isCommitted(now: now) {
                    Section("Commitment") {
                        Label("Locked in — \(Int(remaining / 86400)) days left",
                              systemImage: "checkmark.seal.fill")
                    }
                }

                Section {
                    NavigationLink("Cutoff times") { CutoffEditorView(lock: lock) }
                    NavigationLink("Commitment") { CommitmentView(lock: lock) }
                    NavigationLink("Pending changes") { PendingChangesView(lock: lock) }
                }
            }
            .navigationTitle("Hard Lock")
            .onReceive(tick) { now = $0 }
            .onAppear { lock.reload() }
        }
    }
}
