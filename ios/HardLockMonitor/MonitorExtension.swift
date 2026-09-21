import DeviceActivity
import Foundation
import HardLockKit

final class MonitorExtension: DeviceActivityMonitor {
    private let shields = ShieldController()

    override func intervalDidStart(for activity: DeviceActivityName) {
        super.intervalDidStart(for: activity)
        reconcile(activity: activity, rearmPending: true)
    }

    override func intervalDidEnd(for activity: DeviceActivityName) {
        super.intervalDidEnd(for: activity)
        reconcile(activity: activity)
    }

    override func intervalWillEndWarning(for activity: DeviceActivityName) {
        super.intervalWillEndWarning(for: activity)
        reconcile(activity: activity)
    }

    private func reconcile(activity: DeviceActivityName, rearmPending: Bool = false) {
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
        let effective = LockRules(config: saved).refreshPending(now: now)
        if LockRules(config: effective).isLockedOut(now: now) {
            shields.shieldEverything()
        } else {
            shields.clear()
        }
    }
}
