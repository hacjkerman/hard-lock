import Foundation
import DeviceActivity
import HardLockKit

/// Registers one repeating lockout window per distinct cutoff time. The window
/// runs cutoff -> day reset, so the schedule interval *is* the lockout.
public struct ScheduleManager {
    private let center = DeviceActivityCenter()
    private let store: ConfigStore

    public init(store: ConfigStore) { self.store = store }

    public static func activityName(for hhmm: String) -> DeviceActivityName {
        DeviceActivityName("cutoff_" + hhmm.replacingOccurrences(of: ":", with: "_"))
    }

    public func stopAll() {
        center.stopMonitoring(center.activities)
    }

    public func refreshSchedules() throws {
        stopAll()
        let config = store.load()
        let rules = LockRules(config: config)

        for hhmm in rules.distinctCutoffTimes() {
            guard let mins = LockRules.minutes(fromHHMM: hhmm) else { continue }
            let schedule = DeviceActivitySchedule(
                intervalStart: DateComponents(hour: mins / 60, minute: mins % 60),
                intervalEnd: DateComponents(hour: config.dayResetHour, minute: 0),
                repeats: true
            )
            try center.startMonitoring(ScheduleManager.activityName(for: hhmm), during: schedule)
        }
    }
}
