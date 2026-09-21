import SwiftUI
import HardLockKit

struct CutoffEditorView: View {
    @ObservedObject var lock: LockStore
    @State private var message: String?

    private let dayNames = ["Monday", "Tuesday", "Wednesday", "Thursday",
                            "Friday", "Saturday", "Sunday"]

    var body: some View {
        List {
            Section {
                Text("Earlier cutoffs apply immediately. Later ones wait out your \(lock.config.editCooldownHours)-hour cooldown. A time after midnight (01:30) belongs to that night.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            ForEach(0..<7, id: \.self) { i in
                DatePicker(
                    dayNames[i],
                    selection: Binding(
                        get: { date(for: lock.config.cutoff(forWeekdayIndex: i)) },
                        set: { newDate in setCutoff(hhmm(from: newDate), day: i) }
                    ),
                    displayedComponents: .hourAndMinute
                )
            }
            if let message {
                Section { Text(message).font(.footnote) }
            }
        }
        .navigationTitle("Cutoff times")
    }

    private func setCutoff(_ value: String, day: Int) {
        let result = lock.apply([LockConfig.weekdayKeys[day]: value])
        if !result.rejected.isEmpty {
            message = "Locked in — you can't push a cutoff later until the commitment ends."
        } else if !result.deferred.isEmpty {
            message = "Queued — a later cutoff activates after your cooldown."
        } else if !result.applied.isEmpty {
            message = "Applied now."
        }
    }

    private func date(for hhmm: String?) -> Date {
        let mins = hhmm.flatMap(LockRules.minutes(fromHHMM:)) ?? 23 * 60 + 30
        return Calendar.current.date(bySettingHour: mins / 60, minute: mins % 60,
                                     second: 0, of: Date())!
    }

    private func hhmm(from date: Date) -> String {
        let c = Calendar.current.dateComponents([.hour, .minute], from: date)
        return String(format: "%02d:%02d", c.hour ?? 23, c.minute ?? 30)
    }
}
