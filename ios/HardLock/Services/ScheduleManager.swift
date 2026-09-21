import Foundation
import DeviceActivity
import HardLockKit

/// Daily cutoff windows plus one wakeup for the next queued edit. Both processes
/// derive the effective rules from disk; the extension never writes the config.
public struct ScheduleManager {
    private let center = DeviceActivityCenter()
    private let store: ConfigStore
    public static let pendingActivity = DeviceActivityName("pending_change")

    public init(store: ConfigStore) { self.store = store }

    public static func activityName(for hhmm: String) -> DeviceActivityName {
        DeviceActivityName("cutoff_" + hhmm.replacingOccurrences(of: ":", with: "_"))
    }

    public func stopAll() {
        let ours = center.activities.filter { $0.rawValue.hasPrefix("cutoff_") || $0 == Self.pendingActivity }
        center.stopMonitoring(ours)
    }

    public func refreshSchedules(now: Date = Date()) throws {
        do {
            let saved = try store.loadStrict()
            let config = LockRules(config: saved).refreshPending(now: now)
            let rules = LockRules(config: config)
            stopAll()
            for hhmm in rules.monitoringCutoffTimes(now: now) {
                guard let window = rules.monitoringWindow(hhmm: hhmm) else { continue }
                let schedule = DeviceActivitySchedule(
                    intervalStart: DateComponents(hour: window.startMinute / 60, minute: window.startMinute % 60),
                    intervalEnd: DateComponents(hour: window.endMinute / 60, minute: window.endMinute % 60),
                    repeats: true,
                    warningTime: window.warningMinutes.map { DateComponents(minute: $0) }
                )
                try center.startMonitoring(Self.activityName(for: hhmm), during: schedule)
            }
            if let next = config.pendingChanges.values.map(\.effectiveAt).filter({ $0 > now }).min() {
                let cal = Calendar.current
                let fields: Set<Calendar.Component> = [.year, .month, .day, .hour, .minute, .second]
                try center.startMonitoring(Self.pendingActivity, during: DeviceActivitySchedule(
                    intervalStart: cal.dateComponents(fields, from: next),
                    intervalEnd: cal.dateComponents(fields, from: next.addingTimeInterval(16 * 60)),
                    repeats: false
                ))
            }
        } catch {
            stopAll()
            ShieldController().clear()
            throw error
        }
    }
}
