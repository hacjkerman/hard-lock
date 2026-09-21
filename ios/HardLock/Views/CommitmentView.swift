import SwiftUI
import HardLockKit

struct CommitmentView: View {
    @ObservedObject var lock: LockStore
    @State private var confirming = false

    private let options: [(String, TimeInterval)] = [
        ("1 month", 30 * 86400), ("3 months", 90 * 86400),
        ("6 months", 180 * 86400), ("1 year", 365 * 86400),
    ]
    @State private var choice = 1

    var body: some View {
        List {
            Section {
                Text("While committed you cannot loosen any rule — only tighten. A commitment can be extended but never shortened or cancelled.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            if lock.rules.isCommitted(now: Date()) {
                Label("Locked in until \(lock.config.commitUntil!, style: .date)",
                      systemImage: "checkmark.seal.fill")
            }
            if let error = lock.lastError { Text(error).foregroundStyle(.red) }
            Picker("Lock in for", selection: $choice) {
                ForEach(options.indices, id: \.self) { Text(options[$0].0) }
            }
            Button(confirming ? "Confirm — this cannot be undone" : "Lock in", role: .destructive) {
                if confirming {
                    lock.commit(options[choice].1)
                    confirming = false
                } else {
                    confirming = true
                }
            }
        }
        .navigationTitle("Commitment")
        .disabled(!lock.isReady)
        .onChange(of: choice) { _ in confirming = false }
    }
}
