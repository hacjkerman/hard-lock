import DeviceActivity
import Foundation
import HardLockKit

/// iOS will not keep the app running, but it does wake this extension at the
/// start and end of each registered window. This is what actually enforces.
final class MonitorExtension: DeviceActivityMonitor {

    private let shields = ShieldController()

    override func intervalDidStart(for activity: DeviceActivityName) {
        super.intervalDidStart(for: activity)

        // Fail OPEN: unreadable config must never strand the phone shielded.
        guard let store = ConfigStore.shared(),
              let config = try? store.loadStrict() else {
            shields.clear()
            return
        }

        let rules = LockRules(config: config)
        // We are woken by every registered schedule, so confirm this activity's
        // time is the one today's logical day actually uses.
        let hhmm = activity.rawValue
            .replacingOccurrences(of: "cutoff_", with: "")
            .replacingOccurrences(of: "_", with: ":")
        guard rules.cutoffApplies(hhmm: hhmm, now: Date()) else { return }

        shields.shieldEverything()
    }

    override func intervalDidEnd(for activity: DeviceActivityName) {
        super.intervalDidEnd(for: activity)
        shields.clear()          // day reset — always release
    }
}
