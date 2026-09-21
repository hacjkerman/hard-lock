import SwiftUI
import HardLockKit

struct PendingChangesView: View {
    @ObservedObject var lock: LockStore

    private let dayLabels = ["cutoff_mon": "Monday", "cutoff_tue": "Tuesday",
                             "cutoff_wed": "Wednesday", "cutoff_thu": "Thursday",
                             "cutoff_fri": "Friday", "cutoff_sat": "Saturday",
                             "cutoff_sun": "Sunday"]

    var body: some View {
        List {
            if lock.config.pendingChanges.isEmpty {
                Text("Nothing queued. Tightening changes apply immediately and never appear here.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            ForEach(lock.config.pendingChanges.keys.sorted(), id: \.self) { key in
                if let change = lock.config.pendingChanges[key] {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(dayLabels[key] ?? key) → \(change.value ?? "none")")
                        Button("Cancel queued change") { lock.cancelPending(key) }
                        Text("Activates \(change.effectiveAt, style: .relative) from now")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .navigationTitle("Pending changes")
        .disabled(!lock.isReady)
    }
}
