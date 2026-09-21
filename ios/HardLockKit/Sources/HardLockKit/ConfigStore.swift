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
        let config = try ConfigStore.decoder.decode(LockConfig.self, from: data)
        try config.validate()
        return config
    }

    /// Atomic write — a crash mid-save must never leave a truncated config.
    public func save(_ config: LockConfig) throws {
        try config.validate()
        let data = try ConfigStore.encoder.encode(config)
        try data.write(to: fileURL, options: .atomic)
    }
}
