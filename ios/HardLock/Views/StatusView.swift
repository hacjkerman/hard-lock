import SwiftUI
import FamilyControls
import HardLockKit

struct StatusView: View {
    @EnvironmentObject private var auth: AuthorizationService
    @StateObject private var lock = LockStore(store: ConfigStore.shared())
    @Environment(\.scenePhase) private var scenePhase
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
                        Button("Grant access") { Task { await auth.requestAuthorization(); lock.reload() } }
                    }
                }
                if let error = auth.lastError {
                    Section { Text(error).foregroundStyle(.red) }
                }
                if let err = lock.lastError {
                    Section {
                        Label(err, systemImage: "xmark.octagon.fill").foregroundStyle(.red)
                        Button("Retry") { lock.reload() }
                    }
                }

                Section("Tonight") {
                    if !lock.isReady {
                        Text("Rules unavailable — shielding is off.")
                    } else {
                        switch lock.rules.tonightStatus(authorized: auth.status == .approved, now: now) {
                        case .lockedOut(let until):
                            Label("Locked out until \(until, style: .time)", systemImage: "lock.fill")
                        case .lockoutNotEnforced(let until):
                            Label("Cutoff passed, but nothing is blocked without Screen Time access. The lockout would last until \(until, style: .time).",
                                  systemImage: "lock.slash")
                        case .locksAt(let cutoff, enforced: true):
                            Label("Locks at \(cutoff, style: .time) · \(cutoff, style: .relative)", systemImage: "clock")
                        case .locksAt(let cutoff, enforced: false):
                            Label("Cutoff at \(cutoff, style: .time) won't be enforced without Screen Time access.",
                                  systemImage: "clock.badge.exclamationmark")
                        case .noCutoff:
                            Label("No cutoff today", systemImage: "clock.badge.xmark")
                        }
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
                }.disabled(!lock.isReady)
            }
            .navigationTitle("Hard Lock")
            .onReceive(tick) { now = $0; lock.tick(now: $0) }
            .task {
                await auth.requestAuthorization()
                lock.reload()
            }
            .onChange(of: scenePhase) { phase in
                if phase == .active { auth.refresh(); lock.reload() }
            }
        }
    }
}
