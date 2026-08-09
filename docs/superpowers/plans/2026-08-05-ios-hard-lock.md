# Hard Lock for iOS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An iPhone app that shields every app after a per-day nightly cutoff, where loosening a rule waits out a cooldown and a fixed-term commitment blocks loosening entirely.

**Architecture:** A pure-Swift rules engine (`LockRules`) makes every decision and is exhaustively unit-tested with an injected clock. A JSON config in a shared App Group container is the single source of truth, read by both the app and a `DeviceActivityMonitor` extension. iOS will not keep the app alive, so the extension is what actually enforces: iOS wakes it at the start of each lockout window, it shields all app categories via `ManagedSettings`, and clears them when the window ends at the day reset.

**Tech Stack:** Swift 5.9+, SwiftUI, XCTest, FamilyControls, ManagedSettings, DeviceActivity. Xcode 15+ on macOS. iOS 16.0+ deployment target.

## Global Constraints

- **iOS 16.0+** deployment target (Family Controls individual authorization requires iOS 16).
- **Repo location:** all iOS code lives under `ios/` in the existing `hard-lock` repo.
- **Bundle IDs:** app `com.hardlock.ios`, monitor extension `com.hardlock.ios.monitor`.
- **App Group:** `group.com.hardlock.ios` — the only channel between app and extension.
- **Entitlement:** `com.apple.developer.family-controls` on **both** the app and the extension targets.
- **Every rules API takes an explicit `now: Date`** — no hidden `Date()` inside `LockRules`, so tests never sleep.
- **Day reset is 04:00 by default** (`day_reset_hour`); the logical day rolls then, so 02:00 Saturday still counts as Friday.
- **Shields fail OPEN:** if config cannot be read or parsed, clear shields rather than strand the phone locked.
- **Config keys mirror the desktop's `config.json`** so a later sync project can transport the document unchanged: `cutoff_mon`…`cutoff_sun`, `day_reset_hour`, `edit_cooldown_hours`, `pending_changes`, `commit_until`.
- **No network, no analytics, no accounts.** Local only.
- Run tests with `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15'` (or ⌘U in Xcode).
- Commit after every task.

## File Structure

```
ios/
  HardLock.xcodeproj
  HardLock/                       # app target
    HardLockApp.swift             # @main, root view
    Views/
      StatusView.swift            # locked-out state / time until cutoff
      CutoffEditorView.swift      # per-weekday cutoff times
      CommitmentView.swift        # lock-in with confirm step
      PendingChangesView.swift    # queued weakenings + time remaining
    Services/
      AuthorizationService.swift  # FamilyControls authorization
      ShieldController.swift      # ManagedSettings wrapper
      ScheduleManager.swift       # DeviceActivity schedules
    HardLock.entitlements
  HardLockKit/                    # shared framework: app + extension
    LockRules.swift               # pure rules engine (no Apple frameworks)
    LockConfig.swift              # Codable config model
    ConfigStore.swift             # App Group JSON persistence
  HardLockMonitor/                # DeviceActivityMonitor extension
    MonitorExtension.swift
    HardLockMonitor.entitlements
  HardLockKitTests/
    LockRulesCutoffTests.swift
    LockRulesWeakeningTests.swift
    LockRulesCommitmentTests.swift
    ConfigStoreTests.swift
```

`LockRules` and `ConfigStore` live in a framework because the extension needs them too — an extension cannot import the app target.

---

### Task 1: `LockConfig` model + defaults

**Files:**
- Create: `ios/HardLockKit/LockConfig.swift`
- Test: `ios/HardLockKitTests/ConfigStoreTests.swift`

**Interfaces:**
- Produces:
  - `struct LockConfig: Codable, Equatable` with `cutoffMon…cutoffSun: String?`, `dayResetHour: Int`, `editCooldownHours: Int`, `pendingChanges: [String: PendingChange]`, `commitUntil: Date?`
  - `struct PendingChange: Codable, Equatable { let value: String?; let effectiveAt: Date }`
  - `static let `default`: LockConfig`
  - `func cutoff(forWeekdayIndex i: Int) -> String?` where `0 = Monday … 6 = Sunday`
  - `func withCutoff(_ value: String?, forWeekdayIndex i: Int) -> LockConfig`

- [ ] **Step 1: Write the failing test**

Create `ios/HardLockKitTests/ConfigStoreTests.swift`:

```swift
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests/LockConfigTests`
Expected: FAIL — `cannot find 'LockConfig' in scope`.

- [ ] **Step 3: Implement the model**

Create `ios/HardLockKit/LockConfig.swift`:

```swift
import Foundation

/// One queued weakening: the value to apply, and when it becomes effective.
public struct PendingChange: Codable, Equatable {
    public let value: String?
    public let effectiveAt: Date

    public init(value: String?, effectiveAt: Date) {
        self.value = value
        self.effectiveAt = effectiveAt
    }

    enum CodingKeys: String, CodingKey {
        case value
        case effectiveAt = "effective_at"
    }
}

/// The rules document. Keys mirror the desktop app's config.json so a later
/// sync project can transport this unchanged.
public struct LockConfig: Codable, Equatable {
    public var cutoffMon: String?
    public var cutoffTue: String?
    public var cutoffWed: String?
    public var cutoffThu: String?
    public var cutoffFri: String?
    public var cutoffSat: String?
    public var cutoffSun: String?
    public var dayResetHour: Int
    public var editCooldownHours: Int
    public var pendingChanges: [String: PendingChange]
    public var commitUntil: Date?

    enum CodingKeys: String, CodingKey {
        case cutoffMon = "cutoff_mon"
        case cutoffTue = "cutoff_tue"
        case cutoffWed = "cutoff_wed"
        case cutoffThu = "cutoff_thu"
        case cutoffFri = "cutoff_fri"
        case cutoffSat = "cutoff_sat"
        case cutoffSun = "cutoff_sun"
        case dayResetHour = "day_reset_hour"
        case editCooldownHours = "edit_cooldown_hours"
        case pendingChanges = "pending_changes"
        case commitUntil = "commit_until"
    }

    public static let `default` = LockConfig(
        cutoffMon: "23:30", cutoffTue: "23:30", cutoffWed: "23:30",
        cutoffThu: "23:30", cutoffFri: "23:30", cutoffSat: "23:30",
        cutoffSun: "23:30",
        dayResetHour: 4, editCooldownHours: 24,
        pendingChanges: [:], commitUntil: nil
    )

    /// Config keys for each weekday, Monday-first to match Calendar arithmetic
    /// used in LockRules.
    public static let weekdayKeys = ["cutoff_mon", "cutoff_tue", "cutoff_wed",
                                     "cutoff_thu", "cutoff_fri", "cutoff_sat",
                                     "cutoff_sun"]

    /// 0 = Monday … 6 = Sunday.
    public func cutoff(forWeekdayIndex i: Int) -> String? {
        switch i {
        case 0: return cutoffMon
        case 1: return cutoffTue
        case 2: return cutoffWed
        case 3: return cutoffThu
        case 4: return cutoffFri
        case 5: return cutoffSat
        default: return cutoffSun
        }
    }

    public func withCutoff(_ value: String?, forWeekdayIndex i: Int) -> LockConfig {
        var c = self
        switch i {
        case 0: c.cutoffMon = value
        case 1: c.cutoffTue = value
        case 2: c.cutoffWed = value
        case 3: c.cutoffThu = value
        case 4: c.cutoffFri = value
        case 5: c.cutoffSat = value
        default: c.cutoffSun = value
        }
        return c
    }

    /// Value for a config key, used by the generic apply/weakening path.
    public func value(forKey key: String) -> String? {
        guard let i = LockConfig.weekdayKeys.firstIndex(of: key) else { return nil }
        return cutoff(forWeekdayIndex: i)
    }

    public func setting(_ value: String?, forKey key: String) -> LockConfig {
        guard let i = LockConfig.weekdayKeys.firstIndex(of: key) else { return self }
        return withCutoff(value, forWeekdayIndex: i)
    }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests/LockConfigTests`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add ios/HardLockKit/LockConfig.swift ios/HardLockKitTests/ConfigStoreTests.swift
git commit -m "iOS: LockConfig model with desktop-compatible JSON keys"
```

---

### Task 2: `LockRules` — logical day + cutoff resolution

**Files:**
- Create: `ios/HardLockKit/LockRules.swift`
- Test: `ios/HardLockKitTests/LockRulesCutoffTests.swift`

**Interfaces:**
- Consumes: `LockConfig` (Task 1).
- Produces:
  - `struct LockRules` with `init(config: LockConfig, calendar: Calendar = .current)`
  - `func logicalWeekdayIndex(now: Date) -> Int` (0 = Monday)
  - `func cutoffDate(now: Date) -> Date?` — the absolute cutoff instant for the current logical day, or nil if that day has no cutoff
  - `func resetDate(now: Date) -> Date` — when the current logical day ends
  - `func isLockedOut(now: Date) -> Bool`
  - `static func minutes(fromHHMM s: String) -> Int?`

- [ ] **Step 1: Write the failing test**

Create `ios/HardLockKitTests/LockRulesCutoffTests.swift`:

```swift
import XCTest
@testable import HardLockKit

/// Fixed clock helper: builds dates in a stable UTC calendar so tests are
/// deterministic regardless of the machine's timezone.
func at(_ y: Int, _ mo: Int, _ d: Int, _ h: Int, _ mi: Int) -> Date {
    var c = DateComponents()
    c.year = y; c.month = mo; c.day = d; c.hour = h; c.minute = mi
    return testCalendar.date(from: c)!
}

var testCalendar: Calendar = {
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = TimeZone(identifier: "UTC")!
    return cal
}()

final class LockRulesCutoffTests: XCTestCase {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }

    func testLogicalWeekdayRollsAtFour() {
        let r = rules(.default)
        // Sat 2026-01-10 02:00 is still logically Friday (index 4).
        XCTAssertEqual(r.logicalWeekdayIndex(now: at(2026, 1, 10, 2, 0)), 4)
        // Sat 05:00 is Saturday (index 5).
        XCTAssertEqual(r.logicalWeekdayIndex(now: at(2026, 1, 10, 5, 0)), 5)
    }

    func testEveningCutoffLocksOutAfterIt() {
        let r = rules(.default)                     // all days 23:30
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 9, 22, 0)))
        XCTAssertTrue(r.isLockedOut(now: at(2026, 1, 9, 23, 45)))
        XCTAssertTrue(r.isLockedOut(now: at(2026, 1, 10, 2, 0)))   // still Friday night
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 10, 5, 0)))  // past the 04:00 reset
    }

    func testAfterMidnightCutoffBelongsToThatNight() {
        // Friday 01:30 means 1:30am Saturday — you are NOT locked out at 23:45 Friday.
        let c = LockConfig.default.withCutoff("01:30", forWeekdayIndex: 4)
        let r = rules(c)
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 9, 23, 45)))
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 10, 1, 0)))
        XCTAssertTrue(r.isLockedOut(now: at(2026, 1, 10, 1, 45)))
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 10, 5, 0)))  // reset ended it
    }

    func testNoCutoffMeansNeverLockedOut() {
        let c = LockConfig.default.withCutoff(nil, forWeekdayIndex: 4)
        let r = rules(c)
        XCTAssertNil(r.cutoffDate(now: at(2026, 1, 9, 23, 45)))
        XCTAssertFalse(r.isLockedOut(now: at(2026, 1, 9, 23, 45)))
    }

    func testMinutesFromHHMM() {
        XCTAssertEqual(LockRules.minutes(fromHHMM: "23:30"), 1410)
        XCTAssertEqual(LockRules.minutes(fromHHMM: "01:30"), 90)
        XCTAssertNil(LockRules.minutes(fromHHMM: "nonsense"))
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests/LockRulesCutoffTests`
Expected: FAIL — `cannot find 'LockRules' in scope`.

- [ ] **Step 3: Implement the cutoff logic**

Create `ios/HardLockKit/LockRules.swift`:

```swift
import Foundation

/// The rules engine. Pure logic: no Apple frameworks, no I/O, and every API
/// takes an explicit `now`, so behaviour is fully testable without waiting.
public struct LockRules {
    public let config: LockConfig
    private let calendar: Calendar

    public init(config: LockConfig, calendar: Calendar = .current) {
        self.config = config
        self.calendar = calendar
    }

    /// "23:30" -> 1410 minutes past midnight. nil if malformed.
    public static func minutes(fromHHMM s: String) -> Int? {
        let parts = s.split(separator: ":")
        guard parts.count == 2,
              let h = Int(parts[0]), let m = Int(parts[1]),
              (0..<24).contains(h), (0..<60).contains(m) else { return nil }
        return h * 60 + m
    }

    /// Start of the logical day containing `now` — the most recent day-reset
    /// boundary at or before it.
    public func logicalDayStart(now: Date) -> Date {
        let midnight = calendar.startOfDay(for: now)
        let reset = calendar.date(byAdding: .hour, value: config.dayResetHour, to: midnight)!
        return now < reset ? calendar.date(byAdding: .day, value: -1, to: reset)! : reset
    }

    /// 0 = Monday … 6 = Sunday, for the logical day containing `now`.
    public func logicalWeekdayIndex(now: Date) -> Int {
        let start = logicalDayStart(now: now)
        // Calendar.weekday: 1 = Sunday … 7 = Saturday. Convert to Monday-first.
        let weekday = calendar.component(.weekday, from: start)
        return (weekday + 5) % 7
    }

    /// When the current logical day ends (the next day reset).
    public func resetDate(now: Date) -> Date {
        calendar.date(byAdding: .day, value: 1, to: logicalDayStart(now: now))!
    }

    /// The absolute instant of this logical day's cutoff, or nil if none is set.
    /// A cutoff earlier than the day reset (e.g. 01:30) belongs to the *end* of
    /// the window, so it lands on the following calendar date.
    public func cutoffDate(now: Date) -> Date? {
        let idx = logicalWeekdayIndex(now: now)
        guard let hhmm = config.cutoff(forWeekdayIndex: idx),
              let mins = LockRules.minutes(fromHHMM: hhmm) else { return nil }

        let start = logicalDayStart(now: now)               // e.g. Fri 04:00
        let dayMidnight = calendar.startOfDay(for: start)   // Fri 00:00
        var cutoff = calendar.date(byAdding: .minute, value: mins, to: dayMidnight)!
        if mins < config.dayResetHour * 60 {
            // 01:30 with a 04:00 reset => the small hours of the NEXT date.
            cutoff = calendar.date(byAdding: .day, value: 1, to: cutoff)!
        }
        return cutoff
    }

    /// True while inside this logical day's lockout window (cutoff -> reset).
    public func isLockedOut(now: Date) -> Bool {
        guard let cutoff = cutoffDate(now: now) else { return false }
        return now >= cutoff && now < resetDate(now: now)
    }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests/LockRulesCutoffTests`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add ios/HardLockKit/LockRules.swift ios/HardLockKitTests/LockRulesCutoffTests.swift
git commit -m "iOS: LockRules logical-day rollover and cutoff resolution"
```

---

### Task 3: `LockRules` — tighten now, weaken later

**Files:**
- Modify: `ios/HardLockKit/LockRules.swift`
- Test: `ios/HardLockKitTests/LockRulesWeakeningTests.swift`

**Interfaces:**
- Consumes: `LockRules` (Task 2), `PendingChange` (Task 1).
- Produces:
  - `struct ApplyResult: Equatable { public let applied: [String]; public let deferred: [String]; public let rejected: [String]; public let config: LockConfig }`
  - `func cutoffWeakens(oldValue: String?, newValue: String?) -> Bool`
  - `func apply(changes: [String: String?], now: Date) -> ApplyResult`
  - `func refreshPending(now: Date) -> LockConfig`

- [ ] **Step 1: Write the failing test**

Create `ios/HardLockKitTests/LockRulesWeakeningTests.swift`:

```swift
import XCTest
@testable import HardLockKit

final class LockRulesWeakeningTests: XCTestCase {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }
    let now = at(2026, 1, 9, 12, 0)

    func testEarlierCutoffIsTighteningAndAppliesNow() {
        let r = rules(.default)                      // Fri 23:30
        let res = r.apply(changes: ["cutoff_fri": "22:00"], now: now)
        XCTAssertEqual(res.applied, ["cutoff_fri"])
        XCTAssertTrue(res.deferred.isEmpty)
        XCTAssertEqual(res.config.cutoffFri, "22:00")
        XCTAssertTrue(res.config.pendingChanges.isEmpty)
    }

    func testLaterCutoffIsWeakeningAndIsQueued() {
        let r = rules(.default)
        let res = r.apply(changes: ["cutoff_fri": "23:45"], now: now)
        XCTAssertEqual(res.deferred, ["cutoff_fri"])
        XCTAssertTrue(res.applied.isEmpty)
        XCTAssertEqual(res.config.cutoffFri, "23:30")             // not yet in force
        let pending = try! XCTUnwrap(res.config.pendingChanges["cutoff_fri"])
        XCTAssertEqual(pending.value, "23:45")
        XCTAssertEqual(pending.effectiveAt, now.addingTimeInterval(24 * 3600))
    }

    /// The bug found on desktop: 01:30 is EARLIER on the clock but LATER at
    /// night, so it must count as weakening.
    func testAfterMidnightCutoffCountsAsLater() {
        let r = rules(.default)
        XCTAssertTrue(r.cutoffWeakens(oldValue: "23:30", newValue: "01:30"))
        XCTAssertFalse(r.cutoffWeakens(oldValue: "01:30", newValue: "23:30"))
    }

    func testRemovingACutoffIsWeakening() {
        let r = rules(.default)
        XCTAssertTrue(r.cutoffWeakens(oldValue: "23:30", newValue: nil))
        XCTAssertFalse(r.cutoffWeakens(oldValue: nil, newValue: "23:30"))
    }

    func testDuePendingChangeActivates() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(
            value: "23:45", effectiveAt: now.addingTimeInterval(-60))   // already due
        let updated = rules(c).refreshPending(now: now)
        XCTAssertEqual(updated.cutoffFri, "23:45")
        XCTAssertTrue(updated.pendingChanges.isEmpty)
    }

    func testNotYetDuePendingChangeStays() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(
            value: "23:45", effectiveAt: now.addingTimeInterval(3600))
        let updated = rules(c).refreshPending(now: now)
        XCTAssertEqual(updated.cutoffFri, "23:30")
        XCTAssertNotNil(updated.pendingChanges["cutoff_fri"])
    }

    func testReapplyingAQueuedValueIsIdempotent() {
        let r = rules(.default)
        let first = r.apply(changes: ["cutoff_fri": "23:45"], now: now)
        let effectiveAt = first.config.pendingChanges["cutoff_fri"]!.effectiveAt
        let again = LockRules(config: first.config, calendar: testCalendar)
            .apply(changes: ["cutoff_fri": "23:45"], now: now.addingTimeInterval(600))
        XCTAssertTrue(again.deferred.isEmpty)   // no re-queue
        XCTAssertTrue(again.applied.isEmpty)    // and not cancelled either
        XCTAssertEqual(again.config.pendingChanges["cutoff_fri"]?.effectiveAt, effectiveAt)
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests/LockRulesWeakeningTests`
Expected: FAIL — `value of type 'LockRules' has no member 'apply'`.

- [ ] **Step 3: Implement the weakening model**

Append to `ios/HardLockKit/LockRules.swift`:

```swift
public struct ApplyResult: Equatable {
    public let applied: [String]
    public let deferred: [String]
    public let rejected: [String]
    public let config: LockConfig
}

public extension LockRules {

    /// Minutes from the day reset to this cutoff, wrapping past midnight — so a
    /// later *night* sorts after an earlier one even when the clock time is
    /// smaller (01:30 is later than 23:30 with an 04:00 reset).
    func logicalCutoffMinute(_ hhmm: String) -> Int? {
        guard let m = LockRules.minutes(fromHHMM: hhmm) else { return nil }
        return ((m - config.dayResetHour * 60) % 1440 + 1440) % 1440
    }

    /// A later cutoff (or removing it entirely) relaxes the lock.
    func cutoffWeakens(oldValue: String?, newValue: String?) -> Bool {
        if newValue == nil { return oldValue != nil }   // removing a limit
        guard let oldValue else { return false }        // adding one is tightening
        guard let a = logicalCutoffMinute(oldValue),
              let b = logicalCutoffMinute(newValue!) else { return false }
        return b > a
    }

    /// Tightening applies immediately; weakening is queued for the cooldown;
    /// while committed, weakening is rejected outright rather than queued.
    func apply(changes: [String: String?], now: Date) -> ApplyResult {
        var updated = config
        var applied: [String] = [], deferred: [String] = [], rejected: [String] = []
        let committed = isCommitted(now: now)
        let effectiveAt = now.addingTimeInterval(TimeInterval(config.editCooldownHours) * 3600)

        for key in changes.keys.sorted() {
            let newValue = changes[key] ?? nil
            let oldValue = updated.value(forKey: key)
            let queued = updated.pendingChanges[key]

            if newValue == oldValue && queued == nil { continue }
            // Re-submitting a value already queued must not re-defer or cancel it.
            if let queued, queued.value == newValue { continue }

            if cutoffWeakens(oldValue: oldValue, newValue: newValue) {
                if committed { rejected.append(key); continue }
                updated.pendingChanges[key] = PendingChange(value: newValue, effectiveAt: effectiveAt)
                deferred.append(key)
            } else {
                updated = updated.setting(newValue, forKey: key)
                updated.pendingChanges.removeValue(forKey: key)
                applied.append(key)
            }
        }
        return ApplyResult(applied: applied, deferred: deferred,
                           rejected: rejected, config: updated)
    }

    /// Activate any queued change whose cooldown has elapsed.
    func refreshPending(now: Date) -> LockConfig {
        var updated = config
        for (key, change) in config.pendingChanges where change.effectiveAt <= now {
            updated = updated.setting(change.value, forKey: key)
            updated.pendingChanges.removeValue(forKey: key)
        }
        return updated
    }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests/LockRulesWeakeningTests`
Expected: FAIL — `cannot find 'isCommitted'`. That member arrives in Task 4; add this temporary stub to `LockRules.swift` to keep the suite green, and delete it in Task 4 Step 3:

```swift
public extension LockRules {
    func isCommitted(now: Date) -> Bool { false }   // replaced in Task 4
}
```

Re-run: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add ios/HardLockKit/LockRules.swift ios/HardLockKitTests/LockRulesWeakeningTests.swift
git commit -m "iOS: tighten-now / weaken-later rules with day-reset-aware cutoff comparison"
```

---

### Task 4: `LockRules` — fixed-term commitments

**Files:**
- Modify: `ios/HardLockKit/LockRules.swift`
- Test: `ios/HardLockKitTests/LockRulesCommitmentTests.swift`

**Interfaces:**
- Consumes: `LockRules.apply` (Task 3).
- Produces:
  - `func isCommitted(now: Date) -> Bool` (replaces the Task 3 stub)
  - `func commitRemaining(now: Date) -> TimeInterval?`
  - `func commit(duration: TimeInterval, now: Date) -> LockConfig`

- [ ] **Step 1: Write the failing test**

Create `ios/HardLockKitTests/LockRulesCommitmentTests.swift`:

```swift
import XCTest
@testable import HardLockKit

final class LockRulesCommitmentTests: XCTestCase {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }
    let now = at(2026, 1, 9, 12, 0)

    func testNotCommittedByDefault() {
        XCTAssertFalse(rules(.default).isCommitted(now: now))
        XCTAssertNil(rules(.default).commitRemaining(now: now))
    }

    func testCommitSetsFutureEnd() {
        let c = rules(.default).commit(duration: 3600, now: now)
        let r = rules(c)
        XCTAssertTrue(r.isCommitted(now: now))
        XCTAssertEqual(r.commitRemaining(now: now), 3600)
        XCTAssertFalse(r.isCommitted(now: now.addingTimeInterval(3601)))
    }

    func testCommitIsExtendOnly() {
        let first = rules(.default).commit(duration: 7200, now: now)
        let shorter = rules(first).commit(duration: 60, now: now)
        XCTAssertEqual(shorter.commitUntil, first.commitUntil)      // never shortens
        let longer = rules(first).commit(duration: 10_000, now: now)
        XCTAssertGreaterThan(longer.commitUntil!, first.commitUntil!)
    }

    func testCommitDropsQueuedWeakenings() {
        var c = LockConfig.default
        c.pendingChanges["cutoff_fri"] = PendingChange(
            value: "23:45", effectiveAt: now.addingTimeInterval(3600))
        let committed = rules(c).commit(duration: 3600, now: now)
        XCTAssertTrue(committed.pendingChanges.isEmpty)
    }

    func testWeakeningIsRejectedWhileCommitted() {
        let c = rules(.default).commit(duration: 3600, now: now)
        let res = rules(c).apply(changes: ["cutoff_fri": "23:45"], now: now)
        XCTAssertEqual(res.rejected, ["cutoff_fri"])
        XCTAssertTrue(res.deferred.isEmpty)
        XCTAssertEqual(res.config.cutoffFri, "23:30")
        XCTAssertTrue(res.config.pendingChanges.isEmpty)   // not even queued
    }

    func testTighteningStillWorksWhileCommitted() {
        let c = rules(.default).commit(duration: 3600, now: now)
        let res = rules(c).apply(changes: ["cutoff_fri": "22:00"], now: now)
        XCTAssertEqual(res.applied, ["cutoff_fri"])
        XCTAssertTrue(res.rejected.isEmpty)
        XCTAssertEqual(res.config.cutoffFri, "22:00")
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests/LockRulesCommitmentTests`
Expected: FAIL — `testCommitSetsFutureEnd` fails because the stub always returns `false`.

- [ ] **Step 3: Replace the stub with the real implementation**

Delete the temporary stub added in Task 3 Step 4, and append to `ios/HardLockKit/LockRules.swift`:

```swift
public extension LockRules {

    /// A commitment is active until `commitUntil` passes. While active, nothing
    /// can be weakened — only tightened.
    func isCommitted(now: Date) -> Bool {
        guard let until = config.commitUntil else { return false }
        return now < until
    }

    func commitRemaining(now: Date) -> TimeInterval? {
        guard let until = config.commitUntil else { return nil }
        return max(0, until.timeIntervalSince(now))
    }

    /// Lock in for a term. Extend-only: never shortens an existing commitment.
    /// Queued weakenings are dropped — they cannot benefit you during the term.
    func commit(duration: TimeInterval, now: Date) -> LockConfig {
        let clamped = min(max(duration, 60), 10 * 365 * 24 * 3600)   // 1 min … ~10 years
        var updated = config
        let end = now.addingTimeInterval(clamped)
        updated.commitUntil = max(end, config.commitUntil ?? end)
        updated.pendingChanges = [:]
        return updated
    }
}
```

- [ ] **Step 4: Run the whole kit test suite**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests`
Expected: PASS (all tests from Tasks 1–4).

- [ ] **Step 5: Commit**

```bash
git add ios/HardLockKit/LockRules.swift ios/HardLockKitTests/LockRulesCommitmentTests.swift
git commit -m "iOS: extend-only commitments that reject weakening"
```

---

### Task 5: `ConfigStore` — App Group persistence

**Files:**
- Create: `ios/HardLockKit/ConfigStore.swift`
- Modify: `ios/HardLockKitTests/ConfigStoreTests.swift`

**Interfaces:**
- Consumes: `LockConfig` (Task 1).
- Produces:
  - `struct ConfigStore` with `init(directory: URL)` and `static let appGroupID = "group.com.hardlock.ios"`
  - `static func shared() -> ConfigStore?` — App Group container, nil if unavailable
  - `func load() -> LockConfig` — defaults on missing/corrupt
  - `func loadStrict() throws -> LockConfig` — throws on missing/corrupt (used by the extension's fail-open path)
  - `func save(_ config: LockConfig) throws` — atomic

- [ ] **Step 1: Write the failing test**

Append to `ios/HardLockKitTests/ConfigStoreTests.swift`:

```swift
final class ConfigStoreTests: XCTestCase {
    var dir: URL!

    override func setUpWithError() throws {
        dir = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    }

    func testMissingFileReturnsDefaults() {
        XCTAssertEqual(ConfigStore(directory: dir).load(), .default)
    }

    func testSaveThenLoadRoundTrip() throws {
        let store = ConfigStore(directory: dir)
        let c = LockConfig.default.withCutoff("01:30", forWeekdayIndex: 5)
        try store.save(c)
        XCTAssertEqual(store.load(), c)
    }

    func testCorruptFileFallsBackToDefaults() throws {
        let store = ConfigStore(directory: dir)
        try "{ not json".write(to: dir.appendingPathComponent("config.json"),
                               atomically: true, encoding: .utf8)
        XCTAssertEqual(store.load(), .default)          // never crashes
        XCTAssertThrowsError(try store.loadStrict())    // but strict callers can tell
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests/ConfigStoreTests`
Expected: FAIL — `cannot find 'ConfigStore' in scope`.

- [ ] **Step 3: Implement the store**

Create `ios/HardLockKit/ConfigStore.swift`:

```swift
import Foundation

/// The config lives in a shared App Group container so the app and the
/// DeviceActivityMonitor extension read exactly the same rules.
public struct ConfigStore {
    public static let appGroupID = "group.com.hardlock.ios"

    private let directory: URL
    private var fileURL: URL { directory.appendingPathComponent("config.json") }

    public init(directory: URL) { self.directory = directory }

    public static func shared() -> ConfigStore? {
        guard let url = FileManager.default
            .containerURL(forSecurityApplicationGroupIdentifier: appGroupID) else { return nil }
        return ConfigStore(directory: url)
    }

    private static var encoder: JSONEncoder {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        e.outputFormatting = [.prettyPrinted, .sortedKeys]
        return e
    }

    private static var decoder: JSONDecoder {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }

    /// Never throws: a missing or corrupt file yields defaults, so the UI and
    /// the extension can always proceed.
    public func load() -> LockConfig {
        (try? loadStrict()) ?? .default
    }

    /// Throws on missing/unreadable/corrupt config. The monitor extension uses
    /// this to decide to fail OPEN (clear shields) rather than guess.
    public func loadStrict() throws -> LockConfig {
        let data = try Data(contentsOf: fileURL)
        return try ConfigStore.decoder.decode(LockConfig.self, from: data)
    }

    /// Atomic write — a crash mid-save must never leave a truncated config.
    public func save(_ config: LockConfig) throws {
        let data = try ConfigStore.encoder.encode(config)
        try data.write(to: fileURL, options: .atomic)
    }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests/ConfigStoreTests`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add ios/HardLockKit/ConfigStore.swift ios/HardLockKitTests/ConfigStoreTests.swift
git commit -m "iOS: ConfigStore with atomic writes and corrupt-file fallback"
```

---

### Task 6: Xcode project, entitlements, authorization

**Files:**
- Create: `ios/HardLock.xcodeproj` (via Xcode)
- Create: `ios/HardLock/HardLock.entitlements`
- Create: `ios/HardLockMonitor/HardLockMonitor.entitlements`
- Create: `ios/HardLock/Services/AuthorizationService.swift`
- Create: `ios/HardLock/HardLockApp.swift`

**Interfaces:**
- Consumes: `ConfigStore` (Task 5).
- Produces:
  - `@MainActor final class AuthorizationService: ObservableObject` with `@Published var status: AuthorizationStatus`, `func requestAuthorization() async`, `func refresh()`

This task is Xcode-driven, so its steps are project configuration rather than TDD. `AuthorizationService` is thin and verified on device in Step 6.

- [ ] **Step 1: Create the project and targets**

In Xcode: **File → New → Project → iOS → App**.
- Product Name `HardLock`, Interface **SwiftUI**, Language **Swift**, save under `ios/`.
- Set the app target's **Minimum Deployment** to **iOS 16.0**.
- Bundle identifier: `com.hardlock.ios`.

Add two more targets:
- **File → New → Target → Framework**, name `HardLockKit` (this is where Tasks 1–5's files belong; drag them in and set their Target Membership to `HardLockKit`).
- **File → New → Target → Device Activity Monitor Extension**, name `HardLockMonitor`, bundle id `com.hardlock.ios.monitor`.

Add a **Unit Testing Bundle** target named `HardLockKitTests` if the template did not create one, and give it `@testable import HardLockKit`.

- [ ] **Step 2: Add capabilities**

For **both** `HardLock` and `HardLockMonitor` targets, in **Signing & Capabilities**:
- **+ Capability → App Groups** → add `group.com.hardlock.ios`.
- **+ Capability → Family Controls**.

Confirm `ios/HardLock/HardLock.entitlements` now contains:

```xml
<key>com.apple.developer.family-controls</key>
<true/>
<key>com.apple.security.application-groups</key>
<array><string>group.com.hardlock.ios</string></array>
```

and that `ios/HardLockMonitor/HardLockMonitor.entitlements` contains the same two keys.

Also link `HardLockKit` into both targets (**General → Frameworks and Libraries**).

- [ ] **Step 3: Verify the kit tests still run inside the project**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests`
Expected: PASS — all tests from Tasks 1–5.

- [ ] **Step 4: Implement the authorization service**

Create `ios/HardLock/Services/AuthorizationService.swift`:

```swift
import Foundation
import FamilyControls

/// Wraps Screen Time authorization. Without this the shields silently do
/// nothing, so the UI surfaces the status prominently rather than hiding it.
@MainActor
public final class AuthorizationService: ObservableObject {
    @Published public private(set) var status: AuthorizationStatus = .notDetermined
    @Published public private(set) var lastError: String?

    public init() { refresh() }

    public func refresh() {
        status = AuthorizationCenter.shared.authorizationStatus
    }

    public func requestAuthorization() async {
        do {
            // .individual = this device's own user, not a parent/child pairing.
            try await AuthorizationCenter.shared.requestAuthorization(for: .individual)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
        refresh()
    }
}
```

- [ ] **Step 5: Wire up the app entry point**

Create `ios/HardLock/HardLockApp.swift`:

```swift
import SwiftUI

@main
struct HardLockApp: App {
    @StateObject private var auth = AuthorizationService()

    var body: some Scene {
        WindowGroup {
            StatusView()
                .environmentObject(auth)
                .task { await auth.requestAuthorization() }
        }
    }
}
```

`StatusView` arrives in Task 9. Until then, temporarily point this at a
placeholder so the project builds:

```swift
            Text("Hard Lock")
                .environmentObject(auth)
                .task { await auth.requestAuthorization() }
```

- [ ] **Step 6: Verify on device**

Build and run on a physical iPhone (Family Controls does not work in the Simulator). Expect the Screen Time permission prompt on first launch. Approve it, relaunch, and confirm no prompt reappears.

- [ ] **Step 7: Commit**

```bash
git add ios/
git commit -m "iOS: Xcode project, Family Controls entitlement, authorization flow"
```

---

### Task 7: `ShieldController`

**Files:**
- Create: `ios/HardLock/Services/ShieldController.swift`

**Interfaces:**
- Produces:
  - `struct ShieldController` with `init(store: ManagedSettingsStore = ManagedSettingsStore(named: .hardLock))`
  - `func shieldEverything()`, `func clear()`, `var isShielding: Bool`
  - `extension ManagedSettingsStore.Name { static let hardLock: Self }`

`ManagedSettings` cannot be exercised in the Simulator, so this is verified on device rather than by unit test.

- [ ] **Step 1: Implement the controller**

Create `ios/HardLock/Services/ShieldController.swift`:

```swift
import Foundation
import ManagedSettings

public extension ManagedSettingsStore.Name {
    /// A named store so Hard Lock's shields are independent of any other
    /// Screen Time settings the user has.
    static let hardLock = Self("hardLock")
}

/// Applies and clears the lockout. Shielding every category is the strongest
/// lockout iOS permits — emergency calling from the lock screen is unaffected.
public struct ShieldController {
    private let store: ManagedSettingsStore

    public init(store: ManagedSettingsStore = ManagedSettingsStore(named: .hardLock)) {
        self.store = store
    }

    public func shieldEverything() {
        store.shield.applicationCategories = .all()
        store.shield.webDomainCategories = .all()
    }

    public func clear() {
        store.shield.applicationCategories = nil
        store.shield.webDomainCategories = nil
    }

    public var isShielding: Bool {
        store.shield.applicationCategories != nil
    }
}
```

- [ ] **Step 2: Add a temporary debug control**

In `ios/HardLock/HardLockApp.swift`, replace the placeholder `Text("Hard Lock")` with a temporary pair of buttons so shielding can be verified before the schedule exists:

```swift
            VStack(spacing: 20) {
                Text("Hard Lock").font(.largeTitle)
                Button("Shield everything") { ShieldController().shieldEverything() }
                Button("Clear shields") { ShieldController().clear() }
            }
            .environmentObject(auth)
            .task { await auth.requestAuthorization() }
```

- [ ] **Step 3: Verify on device**

Build and run on the iPhone. Tap **Shield everything**, press Home, then open any third-party app — it must show a shield screen instead of opening. Tap **Clear shields** and confirm apps open normally again.

**If nothing is shielded:** check that authorization was granted (Task 6) and that the Family Controls capability is on the app target.

- [ ] **Step 4: Commit**

```bash
git add ios/HardLock/Services/ShieldController.swift ios/HardLock/HardLockApp.swift
git commit -m "iOS: ShieldController for shield-everything lockout"
```

---

### Task 8: `ScheduleManager` + monitor extension

**Files:**
- Create: `ios/HardLock/Services/ScheduleManager.swift`
- Create: `ios/HardLockMonitor/MonitorExtension.swift`
- Test: `ios/HardLockKitTests/ScheduleWindowTests.swift`
- Modify: `ios/HardLockKit/LockRules.swift`

**Interfaces:**
- Consumes: `LockRules` (Tasks 2–4), `ConfigStore` (Task 5), `ShieldController` (Task 7).
- Produces:
  - `func LockRules.distinctCutoffTimes() -> [String]` — sorted unique `"HH:mm"` values
  - `func LockRules.cutoffApplies(hhmm: String, now: Date) -> Bool` — does the current logical day use this cutoff time?
  - `struct ScheduleManager` with `func refreshSchedules() throws`, `func stopAll()`
  - `DeviceActivityName` per distinct time: `"cutoff_HH_mm"`

- [ ] **Step 1: Write the failing test**

Create `ios/HardLockKitTests/ScheduleWindowTests.swift`:

```swift
import XCTest
@testable import HardLockKit

final class ScheduleWindowTests: XCTestCase {
    func rules(_ c: LockConfig) -> LockRules { LockRules(config: c, calendar: testCalendar) }

    func testDistinctCutoffTimesDeduplicates() {
        var c = LockConfig.default                         // all 23:30
        c = c.withCutoff("01:30", forWeekdayIndex: 4)      // Fri
        c = c.withCutoff("01:30", forWeekdayIndex: 5)      // Sat
        XCTAssertEqual(rules(c).distinctCutoffTimes(), ["01:30", "23:30"])
    }

    func testDistinctCutoffTimesIgnoresDisabledDays() {
        var c = LockConfig.default
        for i in 0..<7 { c = c.withCutoff(nil, forWeekdayIndex: i) }
        c = c.withCutoff("22:00", forWeekdayIndex: 2)
        XCTAssertEqual(rules(c).distinctCutoffTimes(), ["22:00"])
    }

    /// The extension is woken by every registered schedule, so it must confirm
    /// the current logical day actually uses that time before shielding.
    func testCutoffAppliesOnlyOnMatchingDays() {
        var c = LockConfig.default
        c = c.withCutoff("01:30", forWeekdayIndex: 4)      // Friday only
        let r = rules(c)
        let fridayNight = at(2026, 1, 10, 1, 45)           // logically Friday
        XCTAssertTrue(r.cutoffApplies(hhmm: "01:30", now: fridayNight))
        XCTAssertFalse(r.cutoffApplies(hhmm: "23:30", now: fridayNight))

        let saturdayNight = at(2026, 1, 10, 23, 45)        // logically Saturday
        XCTAssertTrue(r.cutoffApplies(hhmm: "23:30", now: saturdayNight))
        XCTAssertFalse(r.cutoffApplies(hhmm: "01:30", now: saturdayNight))
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests/ScheduleWindowTests`
Expected: FAIL — `value of type 'LockRules' has no member 'distinctCutoffTimes'`.

- [ ] **Step 3: Add the schedule helpers to `LockRules`**

Append to `ios/HardLockKit/LockRules.swift`:

```swift
public extension LockRules {

    /// Every distinct cutoff time in the schedule. A DeviceActivitySchedule
    /// repeats daily rather than weekly, so we register one activity per
    /// distinct time (at most seven) instead of one per weekday.
    func distinctCutoffTimes() -> [String] {
        var seen = Set<String>()
        for i in 0..<7 {
            if let t = config.cutoff(forWeekdayIndex: i), LockRules.minutes(fromHHMM: t) != nil {
                seen.insert(t)
            }
        }
        return seen.sorted()
    }

    /// True when the logical day containing `now` uses this cutoff time — the
    /// check the extension makes before shielding, since it is woken by every
    /// registered schedule regardless of which day it is.
    func cutoffApplies(hhmm: String, now: Date) -> Bool {
        config.cutoff(forWeekdayIndex: logicalWeekdayIndex(now: now)) == hhmm
    }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests/ScheduleWindowTests`
Expected: PASS (3 tests).

- [ ] **Step 5: Implement `ScheduleManager`**

Create `ios/HardLock/Services/ScheduleManager.swift`:

```swift
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
```

- [ ] **Step 6: Implement the monitor extension**

Replace the template contents of `ios/HardLockMonitor/MonitorExtension.swift`:

```swift
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
```

`ShieldController.swift` must be a member of the `HardLockMonitor` target too — select the file and tick `HardLockMonitor` under **Target Membership**.

- [ ] **Step 7: Verify on device**

1. Set today's cutoff to two minutes from now in `config.json` (write it via the debug UI or a temporary button calling `ConfigStore.shared()?.save(...)`), then call `ScheduleManager(store: .shared()!).refreshSchedules()`.
2. **Force-quit the app** — this is the point of the test.
3. Wait for the cutoff. Every app must become shielded without the app running.
4. Confirm shields clear at `day_reset_hour`, or set the reset a few minutes out to check it quickly.

**If nothing happens:** confirm the extension has both the App Group and Family Controls capabilities, and that `ScheduleManager.refreshSchedules()` was actually called.

- [ ] **Step 8: Commit**

```bash
git add ios/HardLock/Services/ScheduleManager.swift ios/HardLockMonitor/MonitorExtension.swift ios/HardLockKit/LockRules.swift ios/HardLockKitTests/ScheduleWindowTests.swift
git commit -m "iOS: schedule registration and monitor extension enforcement"
```

---

### Task 9: SwiftUI screens

**Files:**
- Create: `ios/HardLock/Views/StatusView.swift`
- Create: `ios/HardLock/Views/CutoffEditorView.swift`
- Create: `ios/HardLock/Views/CommitmentView.swift`
- Create: `ios/HardLock/Views/PendingChangesView.swift`
- Create: `ios/HardLock/Services/LockStore.swift`
- Modify: `ios/HardLock/HardLockApp.swift`

**Interfaces:**
- Consumes: `LockRules`, `ConfigStore`, `ScheduleManager`, `AuthorizationService`.
- Produces: `@MainActor final class LockStore: ObservableObject` with `@Published var config: LockConfig`, `func apply(_ changes: [String: String?]) -> ApplyResult`, `func commit(_ duration: TimeInterval)`, `func reload()`

- [ ] **Step 1: Implement the view model**

Create `ios/HardLock/Services/LockStore.swift`:

```swift
import Foundation
import HardLockKit

/// Owns the config for the UI: activates due changes on load, persists edits,
/// and re-registers schedules whenever the rules change.
@MainActor
public final class LockStore: ObservableObject {
    @Published public private(set) var config: LockConfig
    @Published public private(set) var lastError: String?

    private let store: ConfigStore
    private let schedules: ScheduleManager

    public init(store: ConfigStore) {
        self.store = store
        self.schedules = ScheduleManager(store: store)
        self.config = store.load()
        reload()
    }

    public var rules: LockRules { LockRules(config: config) }

    /// Activate any queued change that has come due, then persist.
    public func reload() {
        let refreshed = LockRules(config: store.load()).refreshPending(now: Date())
        config = refreshed
        persist()
    }

    @discardableResult
    public func apply(_ changes: [String: String?]) -> ApplyResult {
        let result = rules.apply(changes: changes, now: Date())
        config = result.config
        persist()
        return result
    }

    public func commit(_ duration: TimeInterval) {
        config = rules.commit(duration: duration, now: Date())
        persist()
    }

    private func persist() {
        do {
            try store.save(config)
            try schedules.refreshSchedules()
            lastError = nil
        } catch {
            lastError = error.localizedDescription    // surfaced in StatusView
        }
    }
}
```

- [ ] **Step 2: Implement `StatusView`**

Create `ios/HardLock/Views/StatusView.swift`:

```swift
import SwiftUI
import FamilyControls
import HardLockKit

struct StatusView: View {
    @EnvironmentObject private var auth: AuthorizationService
    @StateObject private var lock = LockStore(store: ConfigStore.shared()!)
    @State private var now = Date()

    private let tick = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    var body: some View {
        NavigationStack {
            List {
                if auth.status != .approved {
                    Section {
                        Label("Screen Time access not granted — nothing will be blocked",
                              systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.red)
                        Button("Grant access") { Task { await auth.requestAuthorization() } }
                    }
                }
                if let err = lock.lastError {
                    Section { Label(err, systemImage: "xmark.octagon.fill").foregroundStyle(.red) }
                }

                Section("Tonight") {
                    if lock.rules.isLockedOut(now: now) {
                        Label("Locked out until \(lock.rules.resetDate(now: now), style: .time)",
                              systemImage: "lock.fill")
                    } else if let cutoff = lock.rules.cutoffDate(now: now) {
                        Label("Locks at \(cutoff, style: .time) · \(cutoff, style: .relative)",
                              systemImage: "clock")
                    } else {
                        Label("No cutoff today", systemImage: "clock.badge.xmark")
                    }
                }

                if let remaining = lock.rules.commitRemaining(now: now),
                   lock.rules.isCommitted(now: now) {
                    Section("Commitment") {
                        Label("Locked in — \(Int(remaining / 86400)) days left",
                              systemImage: "checkmark.seal.fill")
                    }
                }

                Section {
                    NavigationLink("Cutoff times") { CutoffEditorView(lock: lock) }
                    NavigationLink("Commitment") { CommitmentView(lock: lock) }
                    NavigationLink("Pending changes") { PendingChangesView(lock: lock) }
                }
            }
            .navigationTitle("Hard Lock")
            .onReceive(tick) { now = $0 }
            .onAppear { lock.reload() }
        }
    }
}
```

- [ ] **Step 3: Implement `CutoffEditorView`**

Create `ios/HardLock/Views/CutoffEditorView.swift`:

```swift
import SwiftUI
import HardLockKit

struct CutoffEditorView: View {
    @ObservedObject var lock: LockStore
    @State private var message: String?

    private let dayNames = ["Monday", "Tuesday", "Wednesday", "Thursday",
                            "Friday", "Saturday", "Sunday"]

    var body: some View {
        List {
            Section {
                Text("Earlier cutoffs apply immediately. Later ones wait out your \(lock.config.editCooldownHours)-hour cooldown. A time after midnight (01:30) belongs to that night.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            ForEach(0..<7, id: \.self) { i in
                DatePicker(
                    dayNames[i],
                    selection: Binding(
                        get: { date(for: lock.config.cutoff(forWeekdayIndex: i)) },
                        set: { newDate in setCutoff(hhmm(from: newDate), day: i) }
                    ),
                    displayedComponents: .hourAndMinute
                )
            }
            if let message {
                Section { Text(message).font(.footnote) }
            }
        }
        .navigationTitle("Cutoff times")
    }

    private func setCutoff(_ value: String, day: Int) {
        let result = lock.apply([LockConfig.weekdayKeys[day]: value])
        if !result.rejected.isEmpty {
            message = "Locked in — you can't push a cutoff later until the commitment ends."
        } else if !result.deferred.isEmpty {
            message = "Queued — a later cutoff activates after your cooldown."
        } else if !result.applied.isEmpty {
            message = "Applied now."
        }
    }

    private func date(for hhmm: String?) -> Date {
        let mins = hhmm.flatMap(LockRules.minutes(fromHHMM:)) ?? 23 * 60 + 30
        return Calendar.current.date(bySettingHour: mins / 60, minute: mins % 60,
                                     second: 0, of: Date())!
    }

    private func hhmm(from date: Date) -> String {
        let c = Calendar.current.dateComponents([.hour, .minute], from: date)
        return String(format: "%02d:%02d", c.hour ?? 23, c.minute ?? 30)
    }
}
```

- [ ] **Step 4: Implement `CommitmentView` and `PendingChangesView`**

Create `ios/HardLock/Views/CommitmentView.swift`:

```swift
import SwiftUI
import HardLockKit

struct CommitmentView: View {
    @ObservedObject var lock: LockStore
    @State private var confirming = false

    private let options: [(String, TimeInterval)] = [
        ("1 month", 30 * 86400), ("3 months", 90 * 86400),
        ("6 months", 180 * 86400), ("1 year", 365 * 86400),
    ]
    @State private var choice = 1

    var body: some View {
        List {
            Section {
                Text("While committed you cannot loosen any rule — only tighten. A commitment can be extended but never shortened or cancelled.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            if lock.rules.isCommitted(now: Date()) {
                Label("Locked in until \(lock.config.commitUntil!, style: .date)",
                      systemImage: "checkmark.seal.fill")
            }
            Picker("Lock in for", selection: $choice) {
                ForEach(options.indices, id: \.self) { Text(options[$0].0) }
            }
            Button(confirming ? "Confirm — this cannot be undone" : "Lock in", role: .destructive) {
                if confirming {
                    lock.commit(options[choice].1)
                    confirming = false
                } else {
                    confirming = true
                }
            }
        }
        .navigationTitle("Commitment")
    }
}
```

Create `ios/HardLock/Views/PendingChangesView.swift`:

```swift
import SwiftUI
import HardLockKit

struct PendingChangesView: View {
    @ObservedObject var lock: LockStore

    private let dayLabels = ["cutoff_mon": "Monday", "cutoff_tue": "Tuesday",
                             "cutoff_wed": "Wednesday", "cutoff_thu": "Thursday",
                             "cutoff_fri": "Friday", "cutoff_sat": "Saturday",
                             "cutoff_sun": "Sunday"]

    var body: some View {
        List {
            if lock.config.pendingChanges.isEmpty {
                Text("Nothing queued. Tightening changes apply immediately and never appear here.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            ForEach(lock.config.pendingChanges.keys.sorted(), id: \.self) { key in
                if let change = lock.config.pendingChanges[key] {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(dayLabels[key] ?? key) → \(change.value ?? "none")")
                        Text("Activates \(change.effectiveAt, style: .relative) from now")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .navigationTitle("Pending changes")
    }
}
```

- [ ] **Step 5: Point the app at `StatusView`**

In `ios/HardLock/HardLockApp.swift`, replace the temporary debug buttons from Task 7 Step 2 with the real root view:

```swift
        WindowGroup {
            StatusView()
                .environmentObject(auth)
                .task { await auth.requestAuthorization() }
        }
```

- [ ] **Step 6: Verify on device**

Build and run. Check each of these:
- Setting an **earlier** cutoff says "Applied now" and the Tonight section updates.
- Setting a **later** cutoff says "Queued" and appears under Pending changes with a countdown.
- Locking in for a term, then trying a later cutoff, says "Locked in — you can't push a cutoff later".
- Revoking Screen Time access in Settings makes the red warning banner appear on next launch.

- [ ] **Step 7: Commit**

```bash
git add ios/HardLock/Views ios/HardLock/Services/LockStore.swift ios/HardLock/HardLockApp.swift
git commit -m "iOS: status, cutoff editor, commitment and pending-changes screens"
```

---

### Task 10: Docs and on-device soak

**Files:**
- Create: `ios/README.md`
- Modify: `README.md`

- [ ] **Step 1: Write the iOS README**

Create `ios/README.md`:

```markdown
# Hard Lock for iOS

Shields every app on your iPhone after a nightly cutoff. Loosening a rule waits
out a cooldown; a commitment blocks loosening entirely.

## Why it shields instead of locking

iOS has no API that lets an app lock or power off the device — that is Android
only. Apple's Family Controls framework can *shield* apps (a block screen
instead of the app), so shielding everything is the strongest lockout iOS
permits. Emergency calls from the lock screen always work.

## Requirements

- iOS 16+, a Mac with Xcode 15+, and a physical iPhone.
- Family Controls does **not** work in the Simulator.

## Build

Open `ios/HardLock.xcodeproj`, select your device, and run. Grant Screen Time
access when prompted — without it nothing is blocked, and the app says so.

## Honest limitations

- **Deleting the app removes its shields.** To close that hole yourself: set a
  Screen Time passcode and turn on Settings → Screen Time → Content & Privacy
  Restrictions → "Don't Allow" for removing apps.
- **Revoking Screen Time access** ends enforcement; a Screen Time passcode gates it.
- If the config cannot be read, shields are **cleared**, not applied — the app
  fails open so a bug can never strand your phone locked.

This is friction, not security.
```

- [ ] **Step 2: Link it from the top-level README**

In `README.md`, immediately after the Download section, add:

```markdown
## iPhone

There's an iOS companion that enforces a nightly cutoff by shielding every app —
see [ios/README.md](ios/README.md). It's a separate app with its own settings;
iOS cannot shut a phone down, so it blocks rather than powers off.
```

- [ ] **Step 3: Run the full test suite**

Run: `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests`
Expected: PASS — every test from Tasks 1–8.

- [ ] **Step 4: Soak test on device**

Set a real cutoff a few minutes out, force-quit the app, and leave the phone alone. Confirm:
- Shields apply at the cutoff with the app not running.
- Shields clear at `day_reset_hour`.
- Rebooting the phone before the cutoff still results in shields applying (schedules survive restarts).

- [ ] **Step 5: Commit**

```bash
git add ios/README.md README.md
git commit -m "iOS: documentation and usage notes"
```

---

## Final verification

- [ ] `xcodebuild test -scheme HardLock -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:HardLockKitTests` passes.
- [ ] On device: cutoff shields everything with the app force-quit; day reset clears it.
- [ ] Later cutoff queues; earlier cutoff applies immediately; commitment rejects the later one.
- [ ] Revoked Screen Time access produces a visible warning rather than silent no-op.
- [ ] Corrupt `config.json` in the App Group container results in *cleared* shields, never a stuck lockout.

## Notes for the implementer

- **Family Controls needs a real device.** The Simulator silently does nothing, so anything touching `ManagedSettings`/`DeviceActivity` is verified on device; that is why Tasks 6–8 have manual verification steps instead of unit tests. All decision logic lives in `LockRules`, which *is* unit-tested.
- **`LockRules` must stay framework-free.** If you find yourself importing `ManagedSettings` there, the logic belongs in a service instead.
- **Fail open, always.** The desktop app fails closed (shut down if unsure) because a missed shutdown is cheap. On a phone a stuck lockout is expensive, so every uncertain path clears shields.
- If a task's test does not fail at Step 2, the test is not exercising new behaviour — fix the test before writing the implementation.
