import Foundation
import HardLockKit

/// Presentation of stored "HH:MM" cutoffs in the user's locale and clock style.
enum CutoffFormat {
    /// 0 = Monday … 6 = Sunday, localized.
    static func dayName(_ index: Int) -> String {
        Calendar.current.standaloneWeekdaySymbols[(index + 1) % 7]
    }

    /// A fixed date with no daylight-saving transition, so every clock time exists.
    static func date(from hhmm: String) -> Date {
        let minutes = LockRules.minutes(fromHHMM: hhmm) ?? 23 * 60 + 30
        let components = DateComponents(year: 2001, month: 1, day: 1,
                                        hour: minutes / 60, minute: minutes % 60)
        return Calendar.current.date(from: components) ?? Date()
    }

    static func hhmm(from date: Date) -> String {
        let c = Calendar.current.dateComponents([.hour, .minute], from: date)
        return String(format: "%02d:%02d", c.hour ?? 23, c.minute ?? 30)
    }

    /// "11:30 PM" or "23:30", following the device setting.
    static func time(_ hhmm: String) -> String {
        date(from: hhmm).formatted(date: .omitted, time: .shortened)
    }

    static func time(_ hhmm: String?, off: String = "Off") -> String {
        hhmm.map { time($0) } ?? off
    }

    /// "Tue 6:05 PM" for an activation moment.
    static func moment(_ date: Date) -> String {
        date.formatted(.dateTime.weekday(.abbreviated).hour().minute())
    }
}
