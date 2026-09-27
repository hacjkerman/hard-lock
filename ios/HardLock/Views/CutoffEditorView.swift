import SwiftUI
import HardLockKit

/// Weekly overview. Rows only open a sheet; nothing here writes the rules.
struct CutoffEditorView: View {
    @ObservedObject var lock: LockStore
    @State private var editing: CutoffDaySummary?
    @State private var now = Date()

    private let tick = Timer.publish(every: 15, on: .main, in: .common).autoconnect()

    var body: some View {
        let rules = lock.rules
        List {
            Section {
                ForEach(rules.daySummaries(now: now)) { day in
                    Button { editing = day } label: { CutoffDayRow(day: day, rules: rules) }
                }
            } footer: {
                Text(footer(rules))
            }
            if let error = lock.lastError {
                Section {
                    Label(error, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.red)
                }
            }
        }
        .navigationTitle("Cutoff times")
        .disabled(!lock.isReady)
        .sheet(item: $editing) { day in
            CutoffDaySheet(lock: lock,
                           draft: CutoffDraft(config: rules.refreshPending(now: Date()), dayIndex: day.dayIndex))
        }
        .onReceive(tick) { now = $0 }
    }

    private func footer(_ rules: LockRules) -> String {
        if rules.isCommitted(now: now), let until = lock.config.commitUntil {
            return "Locked in until \(until.formatted(date: .abbreviated, time: .omitted)). Only earlier times can be saved."
        }
        return "Earlier times apply at once. Later times and Off wait \(lock.config.editCooldownHours) hours."
    }
}

private struct CutoffDayRow: View {
    let day: CutoffDaySummary
    let rules: LockRules
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        HStack(spacing: 12) {
            let layout = typeSize.isAccessibilitySize
                ? AnyLayout(VStackLayout(alignment: .leading, spacing: 4))
                : AnyLayout(HStackLayout(alignment: .center, spacing: 8))
            layout {
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        Text(CutoffFormat.dayName(day.dayIndex))
                            .foregroundStyle(.primary)
                        if day.isToday {
                            Text("Today")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.tint)
                        }
                    }
                    if let scheduled = day.scheduled {
                        Label(scheduledText(scheduled), systemImage: "clock.arrow.circlepath")
                            .font(.footnote)
                            .foregroundStyle(.orange)
                    }
                }
                if !typeSize.isAccessibilitySize { Spacer(minLength: 8) }
                VStack(alignment: typeSize.isAccessibilitySize ? .leading : .trailing, spacing: 1) {
                    Text(CutoffFormat.time(day.saved))
                        .font(.title3.weight(.semibold))
                        .monospacedDigit()
                        .foregroundStyle(day.saved == nil ? .secondary : .primary)
                    if let saved = day.saved, rules.isAfterMidnight(saved) {
                        Text("next morning")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            Image(systemName: "chevron.right")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityText)
        .accessibilityHint("Opens the editor for this day")
    }

    private func scheduledText(_ change: PendingChange) -> String {
        let target = change.value.map { "Changes to \(CutoffFormat.time($0))" } ?? "Turns off"
        return "\(target) \(CutoffFormat.moment(change.effectiveAt))"
    }

    private var accessibilityText: String {
        var parts = [CutoffFormat.dayName(day.dayIndex)]
        if day.isToday { parts.append("today") }
        if let saved = day.saved {
            parts.append("cutoff \(CutoffFormat.time(saved))" + (rules.isAfterMidnight(saved) ? ", next morning" : ""))
        } else {
            parts.append("no cutoff")
        }
        if let scheduled = day.scheduled { parts.append(scheduledText(scheduled)) }
        return parts.joined(separator: ", ")
    }
}
