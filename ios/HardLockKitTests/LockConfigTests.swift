import Testing
import Foundation
@testable import HardLockKit

struct LockConfigTests {
    @Test func defaultsMatchDesktop() {
        let c = LockConfig.default
        #expect(c.dayResetHour == 4)
        #expect(c.editCooldownHours == 24)
        #expect(c.cutoffMon == "23:30")
        #expect(c.pendingChanges.isEmpty)
        #expect(c.commitUntil == nil)
    }

    @Test func cutoffByWeekdayIndex() {
        var c = LockConfig.default
        c = c.withCutoff("01:30", forWeekdayIndex: 4)   // Friday
        #expect(c.cutoff(forWeekdayIndex: 4) == "01:30")
        #expect(c.cutoff(forWeekdayIndex: 0) == "23:30")  // Monday untouched
        #expect(c.cutoffFri == "01:30")
    }

    @Test func codableRoundTripUsesDesktopKeys() throws {
        var c = LockConfig.default
        c = c.withCutoff("22:00", forWeekdayIndex: 6)   // Sunday
        let data = try JSONEncoder().encode(c)
        let json = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
        #expect(json["cutoff_sun"] as? String == "22:00")
        #expect(json["day_reset_hour"] as? Int == 4)
        let back = try JSONDecoder().decode(LockConfig.self, from: data)
        #expect(back == c)
    }

    /// Amendment G: keys the config cannot write must not report success.
    @Test func knownKeys() {
        #expect(LockConfig.isKnownKey("cutoff_fri"))
        #expect(!LockConfig.isKnownKey("edit_cooldown_hours"))
        #expect(!LockConfig.isKnownKey("hard_cutoff_time"))
    }

    @Test func settingUnknownKeyIsANoOp() {
        let c = LockConfig.default
        #expect(c.setting("99:99", forKey: "daily_cap_minutes") == c)
        #expect(c.value(forKey: "daily_cap_minutes") == nil)
    }
}
