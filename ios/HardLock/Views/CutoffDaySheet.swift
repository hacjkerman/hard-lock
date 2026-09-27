import SwiftUI
import HardLockKit

/// Edits one day as a local draft. Only Save reaches `LockStore`; Cancel and
/// swipe-to-dismiss simply drop the draft.
struct CutoffDaySheet: View {
    @ObservedObject var lock: LockStore
    @State private var draft: CutoffDraft
    @State private var now = Date()
    @State private var notice: String?
    @State private var confirmingWithdraw = false
    @Environment(\.dismiss) private var dismiss

    private let tick = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    init(lock: LockStore, draft: CutoffDraft) {
        _lock = ObservedObject(wrappedValue: lock)
        _draft = State(initialValue: draft)
    }

    var body: some View {
        let rules = lock.rules
        let outcome = rules.preview(draft, now: now)
        let current = rules.daySummaries(now: now)[draft.dayIndex]

        NavigationStack {
            Form {
                Section {
                    LabeledContent("Now") {
                        Text(CutoffFormat.time(current.saved)).monospacedDigit()
                    }
                    if let scheduled = current.scheduled {
                        LabeledContent("Scheduled") {
                            VStack(alignment: .trailing, spacing: 2) {
                                Text(CutoffFormat.time(scheduled.value)).monospacedDigit()
                                Text("from \(CutoffFormat.moment(scheduled.effectiveAt))")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        Button("Keep \(CutoffFormat.time(current.saved)) and cancel this change") {
                            confirmingWithdraw = true
                        }
                    }
                }

                Section {
                    Toggle("Cutoff", isOn: $draft.isEnabled)
                    if draft.isEnabled {
                        DatePicker("Time", selection: timeBinding, displayedComponents: .hourAndMinute)
                            .datePickerStyle(.wheel)
                            .labelsHidden()
                            .frame(maxWidth: .infinity)
                        if rules.isAfterMidnight(draft.time) {
                            Text("\(dayName) night, early \(CutoffFormat.dayName((draft.dayIndex + 1) % 7)) morning")
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                }

                Section {
                    OutcomeLabel(outcome: outcome, draft: draft, lock: lock, now: now)
                    if let notice {
                        Label(notice, systemImage: "info.circle").foregroundStyle(.orange)
                    }
                }
            }
            .navigationTitle(dayName)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(outcome == .appliesNow(locksNow: true) ? "Save & Lock" : "Save") { save(shown: outcome) }
                        .fontWeight(.semibold)
                        .disabled(!outcome.canSave || !lock.isReady)
                }
            }
            .confirmationDialog("Cancel the scheduled change?", isPresented: $confirmingWithdraw,
                                titleVisibility: .visible) {
                Button("Keep \(CutoffFormat.time(current.saved))") { withdrawScheduled() }
            } message: {
                Text("Changing it again later means waiting the full \(lock.config.editCooldownHours) hours.")
            }
        }
        .onReceive(tick) { now = $0 }
        .onChange(of: draft) { _ in notice = nil }
    }

    private var dayName: String { CutoffFormat.dayName(draft.dayIndex) }

    private var timeBinding: Binding<Date> {
        Binding(get: { CutoffFormat.date(from: draft.time) },
                set: { draft.time = CutoffFormat.hhmm(from: $0) })
    }

    private func save(shown: CutoffSaveOutcome) {
        switch lock.saveCutoff(draft, expecting: shown) {
        case .outdated:
            now = Date()
            notice = "This changed while you were editing. Check the result, then save again."
        case .persisted(.notSaved(let message)):
            notice = message
        case .persisted:
            dismiss()
        }
    }

    private func withdrawScheduled() {
        if case .notSaved(let message) = lock.cancelPending(draft.key) {
            notice = message
            return
        }
        draft = CutoffDraft(config: lock.rules.refreshPending(now: Date()), dayIndex: draft.dayIndex)
    }
}

private struct OutcomeLabel: View {
    let outcome: CutoffSaveOutcome
    let draft: CutoffDraft
    @ObservedObject var lock: LockStore
    let now: Date

    var body: some View {
        switch outcome {
        case .noChange:
            Label("No changes", systemImage: "equal.circle").foregroundStyle(.secondary)
        case .invalidResetHour:
            Label("\(resetHourRange) is kept free for the daily reset. Choose another time.",
                  systemImage: "exclamationmark.circle").foregroundStyle(.red)
        case .appliesNow(locksNow: false):
            Label("Applies as soon as you save.", systemImage: "checkmark.circle").foregroundStyle(.green)
        case .appliesNow(locksNow: true):
            Label("Saving locks your phone now, until \(lock.rules.resetDate(now: now).formatted(date: .omitted, time: .shortened)).",
                  systemImage: "lock.fill").foregroundStyle(.red)
        case .cancelsScheduled:
            Label("Keeps \(CutoffFormat.time(draft.saved)) and cancels the scheduled change.",
                  systemImage: "arrow.uturn.backward.circle")
        case .waits(let until, let replaces):
            VStack(alignment: .leading, spacing: 4) {
                Label("Takes effect \(CutoffFormat.moment(until)), after the \(lock.config.editCooldownHours)-hour wait. \(CutoffFormat.time(draft.saved)) stays until then.",
                      systemImage: "hourglass").foregroundStyle(.orange)
                if replaces {
                    Text("Replaces the scheduled change and restarts the wait.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
        case .blockedByCommitment(let until):
            Label("Locked in until \(until.formatted(date: .abbreviated, time: .omitted)). Only earlier times can be saved.",
                  systemImage: "lock.shield").foregroundStyle(.red)
        }
    }

    private var resetHourRange: String {
        let hour = String(format: "%02d", lock.config.dayResetHour)
        return "\(CutoffFormat.time("\(hour):00"))–\(CutoffFormat.time("\(hour):59"))"
    }
}
