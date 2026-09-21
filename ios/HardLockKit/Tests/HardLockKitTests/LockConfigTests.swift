import XCTest
@testable import HardLockKit

final class LockConfigTests: XCTestCase {
    func testDefaultsMatchDesktop() {
        let c = LockConfig.default
        XCTAssertEqual(c.dayResetHour, 4)
        XCTAssertEqual(c.editCooldownHours, 24)
        XCTAssertEqual(c.cutoffMon, "23:30")
        XCTAssertTrue(c.pendingChanges.isEmpty)
        XCTAssertNil(c.commitUntil)
    }

    func testCutoffByWeekdayIndex() {
        var c = LockConfig.default
        c = c.withCutoff("01:30", forWeekdayIndex: 4)   // Friday
        XCTAssertEqual(c.cutoff(forWeekdayIndex: 4), "01:30")
        XCTAssertEqual(c.cutoff(forWeekdayIndex: 0), "23:30")  // Monday untouched
        XCTAssertEqual(c.cutoffFri, "01:30")
    }

    func testCodableRoundTripUsesDesktopKeys() throws {
        var c = LockConfig.default
        c = c.withCutoff("22:00", forWeekdayIndex: 6)   // Sunday
        let data = try JSONEncoder().encode(c)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(json["cutoff_sun"] as? String, "22:00")
        XCTAssertEqual(json["day_reset_hour"] as? Int, 4)
        let back = try JSONDecoder().decode(LockConfig.self, from: data)
        XCTAssertEqual(back, c)
    }
}
