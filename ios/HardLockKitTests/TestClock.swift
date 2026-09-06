import Foundation

/// Fixed clock helpers. A stable UTC calendar keeps tests deterministic
/// regardless of the machine's timezone.
///
/// Amendment I: `let`, not `var` -- a global mutable is unsafe under parallel
/// test execution and an error in Swift 6 language mode.
let testCalendar: Calendar = {
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = TimeZone(identifier: "UTC")!
    return cal
}()

func at(_ y: Int, _ mo: Int, _ d: Int, _ h: Int, _ mi: Int) -> Date {
    var c = DateComponents()
    c.year = y; c.month = mo; c.day = d; c.hour = h; c.minute = mi
    return testCalendar.date(from: c)!
}

/// A calendar pinned to a zone that observes DST, for the boundary tests.
func zonedCalendar(_ identifier: String) -> Calendar {
    var cal = Calendar(identifier: .gregorian)
    cal.timeZone = TimeZone(identifier: identifier)!
    return cal
}

func at(_ y: Int, _ mo: Int, _ d: Int, _ h: Int, _ mi: Int, in cal: Calendar) -> Date {
    var c = DateComponents()
    c.year = y; c.month = mo; c.day = d; c.hour = h; c.minute = mi
    return cal.date(from: c)!
}
