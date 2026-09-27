import DeviceActivity
import Foundation
import HardLockKit

final class MonitorExtension: DeviceActivityMonitor {
    private let shields = ShieldController()

    override func intervalDidStart(for activity: DeviceActivityName) {
        super.intervalDidStart(for: activity)
        reconcile(activity: activity, callback: .intervalStart, rearmPending: true)
    }

    override func intervalDidEnd(for activity: DeviceActivityName) {
        super.intervalDidEnd(for: activity)
        reconcile(activity: activity, callback: .intervalEnd)
    }

    override func intervalWillEndWarning(for activity: DeviceActivityName) {
        super.intervalWillEndWarning(for: activity)
        reconcile(activity: activity, callback: .endWarning)
    }

    /// Each callback is judged at its own edge; see `isLockedOutForMonitor`.
    private func reconcile(activity: DeviceActivityName, callback: MonitorCallback, rearmPending: Bool = false) {
        let now = Date()
        guard let store = ConfigStore.shared(), let saved = try? store.loadStrict() else {
            shields.clear()
            return
        }
        if rearmPending && activity == ScheduleManager.pendingActivity {
            // Re-arm the next maturity without writing stale app data back.
            do { try ScheduleManager(store: store).refreshSchedules(now: now) }
            catch { shields.clear(); return }
        }
        let kind = MonitorActivity(rawValue: activity.rawValue)
        if LockRules(config: saved).isLockedOutForMonitor(activity: kind, callback: callback, now: now) {
            shields.shieldEverything()
        } else {
            shields.clear()
        }
    }
}
