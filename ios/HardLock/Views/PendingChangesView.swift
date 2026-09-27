import SwiftUI
import HardLockKit

struct PendingChangesView: View {
    @ObservedObject var lock: LockStore

    var body: some View {
        List {
            if let error = lock.lastError {
                Section {
                    Label(error, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.red)
                }
            }
            if lock.config.pendingChanges.isEmpty {
                Text("Nothing queued. Tightening changes apply immediately and never appear here.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            ForEach(lock.config.pendingChanges.keys.sorted(), id: \.self) { key in
                if let change = lock.config.pendingChanges[key],
                   let day = LockConfig.weekdayKeys.firstIndex(of: key) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(CutoffFormat.dayName(day)): \(CutoffFormat.time(lock.config.value(forKey: key))) → \(CutoffFormat.time(change.value))")
                        Text("Activates \(CutoffFormat.moment(change.effectiveAt)) · \(change.effectiveAt, style: .relative)")
                            .font(.caption).foregroundStyle(.secondary)
                        Button("Cancel queued change") { lock.cancelPending(key) }
                    }
                }
            }
        }
        .navigationTitle("Pending changes")
        .disabled(!lock.isReady)
    }
}
