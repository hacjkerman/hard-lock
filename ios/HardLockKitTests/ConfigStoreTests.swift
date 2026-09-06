import Testing
import Foundation
@testable import HardLockKit

final class ConfigStoreTests {
    let dir: URL
    var store: ConfigStore { ConfigStore(directory: dir) }

    init() throws {
        dir = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    }

    deinit { try? FileManager.default.removeItem(at: dir) }

    private func write(_ json: String) throws {
        try json.write(to: dir.appendingPathComponent("config.json"),
                       atomically: true, encoding: .utf8)
    }

    @Test func missingFileReturnsDefaults() {
        #expect(store.load() == .default)
    }

    @Test func saveThenLoadRoundTrip() throws {
        let c = LockConfig.default.withCutoff("01:30", forWeekdayIndex: 5)
        try store.save(c)
        #expect(store.load() == c)
    }

    @Test func corruptFileFallsBackToDefaults() throws {
        try write("{ not json")
        #expect(store.load() == .default)                 // never crashes
        #expect(throws: (any Error).self) { try store.loadStrict() }
    }

    // MARK: - Amendment C

    /// Missing and corrupt both yield defaults, but they are different events.
    /// The app must warn on the second; only the extension treats it as routine.
    @Test func missingAndCorruptAreDistinguishable() throws {
        #expect(store.loadWithStatus().status == .missing)

        try write("{ not json")
        guard case .corrupt = store.loadWithStatus().status else {
            Issue.record("expected .corrupt, got \(store.loadWithStatus().status)")
            return
        }
    }

    /// A malformed pending entry must drop only itself. Codable's default
    /// all-or-nothing behaviour would reset every rule the user has; the
    /// desktop drops the bad row and keeps going.
    @Test func malformedPendingEntryDropsOnlyItself() throws {
        try write("""
        {
          "cutoff_mon": "22:00", "cutoff_tue": "23:30", "cutoff_wed": "23:30",
          "cutoff_thu": "23:30", "cutoff_fri": "23:30", "cutoff_sat": "23:30",
          "cutoff_sun": "23:30",
          "day_reset_hour": 4, "edit_cooldown_hours": 24,
          "pending_changes": {
            "cutoff_fri": {"value": "23:45", "effective_at": "2026-08-09T12:34:56.789012"},
            "cutoff_sat": {"value": "23:45"},
            "daily_cap_minutes": {"value": 480, "effective_at": "2026-08-09T12:34:56.789012"}
          },
          "commit_until": null
        }
        """)
        let c = store.load()
        #expect(c.cutoffMon == "22:00")                        // rules survived
        #expect(c.pendingChanges.count == 1)                   // only the good row
        #expect(c.pendingChanges["cutoff_fri"]?.value == "23:45")
        #expect(c.pendingChanges["cutoff_sat"] == nil)         // missing effective_at
        #expect(c.pendingChanges["daily_cap_minutes"] == nil)  // desktop Int value
    }

    /// The desktop writes naive local timestamps with microseconds. `.iso8601`
    /// rejects them outright, which is what made the compat claim false.
    @Test func desktopNaiveTimestampsParse() throws {
        try write("""
        {
          "cutoff_mon": "23:30", "cutoff_tue": "23:30", "cutoff_wed": "23:30",
          "cutoff_thu": "23:30", "cutoff_fri": "23:30", "cutoff_sat": "23:30",
          "cutoff_sun": "23:30",
          "day_reset_hour": 4, "edit_cooldown_hours": 24,
          "pending_changes": {},
          "commit_until": "2026-09-01T23:30:00.123456"
        }
        """)
        let c = store.load()
        let parsed = try #require(c.commitUntil)

        var comps = DateComponents()
        comps.year = 2026; comps.month = 9; comps.day = 1
        comps.hour = 23; comps.minute = 30
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = .current
        let expected = try #require(cal.date(from: comps))
        #expect(abs(parsed.timeIntervalSince(expected) - 0.123456) < 0.001)
    }

    @Test func offsetBearingAndSecondsOnlyTimestampsAlsoParse() {
        #expect(ConfigStore.parseDate("2026-09-01T23:30:00") != nil)
        #expect(ConfigStore.parseDate("2026-09-01T23:30:00.123456") != nil)
        #expect(ConfigStore.parseDate("2026-09-01T23:30:00+10:00") != nil)
        #expect(ConfigStore.parseDate("2026-09-01T23:30:00.123456+10:00") != nil)
        #expect(ConfigStore.parseDate("not a date") == nil)
    }

    /// We write what the desktop can read back: naive local, microseconds, no
    /// offset. An offset-bearing value makes Python raise when it compares
    /// against a naive datetime.now().
    @Test func weWriteDesktopShapedTimestamps() throws {
        var c = LockConfig.default
        c.commitUntil = Date(timeIntervalSince1970: 1_800_000_000)
        try store.save(c)

        let text = try String(contentsOf: dir.appendingPathComponent("config.json"),
                              encoding: .utf8)
        let line = try #require(text.split(separator: "\n").first { $0.contains("commit_until") })
        #expect(line.contains("T"), "expected ISO-ish shape: \(line)")
        #expect(!line.contains("Z"), "must not write a UTC designator: \(line)")
        #expect(!line.contains("+"), "must not write an offset: \(line)")

        let back = try #require(store.load().commitUntil)
        #expect(abs(back.timeIntervalSince1970 - 1_800_000_000) < 0.001)
    }

    @Test func missingScalarsFallBackRatherThanThrowing() throws {
        try write(#"{"cutoff_mon": "22:00", "pending_changes": {}}"#)
        let c = store.load()
        #expect(c.cutoffMon == "22:00")
        #expect(c.dayResetHour == 4)
        #expect(c.editCooldownHours == 24)
        #expect(c.cutoffFri == nil)
    }
}
