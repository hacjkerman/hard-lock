import Foundation

/// Why `load()` returned what it did. Amendment C: "no file yet" and "the file
/// is unreadable" both yield defaults, but they are not the same event -- the
/// first is normal, the second means the user's rules could not be read and
/// must be surfaced rather than silently overwritten.
public enum ConfigLoadStatus: Equatable {
    case loaded
    case missing
    case corrupt(String)
}

/// The config lives in a shared App Group container so the app and the
/// DeviceActivityMonitor extension read exactly the same rules.
public struct ConfigStore {
    public static let appGroupID = "group.com.hardlock.ios"

    private let directory: URL
    private var fileURL: URL { directory.appendingPathComponent("config.json") }

    public init(directory: URL) { self.directory = directory }

    /// nil when the App Group container is unavailable. Callers must handle it
    /// -- Amendment D: do not force-unwrap this at a view initialiser.
    public static func shared() -> ConfigStore? {
        guard let url = FileManager.default
            .containerURL(forSecurityApplicationGroupIdentifier: appGroupID) else { return nil }
        return ConfigStore(directory: url)
    }

    // MARK: - Date handling (Amendment C)

    /// The desktop writes naive local timestamps via Python's
    /// `datetime.isoformat()` -- no offset, microseconds -- and compares them
    /// against naive `datetime.now()`. Writing an offset-bearing timestamp back
    /// would make Python raise on the comparison, so we stay bug-compatible:
    /// **tolerant on read, desktop-shaped on write.**
    private static func makeFormatter(_ format: String, naive: Bool) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = format
        if naive { f.timeZone = TimeZone.current }
        return f
    }

    /// Write format: matches Python's `datetime.isoformat()` with microseconds.
    private static let writeFormatter = makeFormatter("yyyy-MM-dd'T'HH:mm:ss.SSSSSS", naive: true)

    /// Read formats, most specific first. Naive values are read as local time,
    /// which is what the desktop means by them.
    private static let readFormatters: [DateFormatter] = [
        makeFormatter("yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXXXX", naive: false),
        makeFormatter("yyyy-MM-dd'T'HH:mm:ssXXXXX", naive: false),
        makeFormatter("yyyy-MM-dd'T'HH:mm:ss.SSSSSS", naive: true),
        makeFormatter("yyyy-MM-dd'T'HH:mm:ss", naive: true),
    ]

    static func parseDate(_ s: String) -> Date? {
        for f in readFormatters {
            if let d = f.date(from: s) { return d }
        }
        return nil
    }

    private static var encoder: JSONEncoder {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .custom { date, encoder in
            var c = encoder.singleValueContainer()
            try c.encode(writeFormatter.string(from: date))
        }
        e.outputFormatting = [.prettyPrinted, .sortedKeys]
        return e
    }

    private static var decoder: JSONDecoder {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .custom { decoder in
            let s = try decoder.singleValueContainer().decode(String.self)
            guard let date = parseDate(s) else {
                throw DecodingError.dataCorrupted(
                    .init(codingPath: decoder.codingPath,
                          debugDescription: "Unrecognised timestamp: \(s)"))
            }
            return date
        }
        return d
    }

    // MARK: - Loading

    /// Amendment C: says *why* it returned what it did, so the app can warn on
    /// corruption while the extension quietly falls open.
    public func loadWithStatus() -> (config: LockConfig, status: ConfigLoadStatus) {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            return (.default, .missing)
        }
        do {
            return (try loadStrict(), .loaded)
        } catch {
            return (.default, .corrupt(error.localizedDescription))
        }
    }

    /// Never throws: a missing or corrupt file yields defaults.
    public func load() -> LockConfig {
        loadWithStatus().config
    }

    /// Throws on missing/unreadable/corrupt config.
    public func loadStrict() throws -> LockConfig {
        let data = try Data(contentsOf: fileURL)
        return try ConfigStore.decoder.decode(LockConfig.self, from: data)
    }

    /// Atomic write -- a crash mid-save must never leave a truncated config.
    public func save(_ config: LockConfig) throws {
        let data = try ConfigStore.encoder.encode(config)
        try data.write(to: fileURL, options: .atomic)
    }
}
