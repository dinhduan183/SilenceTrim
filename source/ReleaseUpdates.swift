import Foundation

enum AppVersion {
    static let current = "2.2"
}

enum ReleaseUpdates {
    static let apiURL = URL(string: "https://api.github.com/repos/dinhduan183/SilenceTrim/releases/latest")!
    static let downloadURL = URL(string: "https://github.com/dinhduan183/SilenceTrim/releases/latest")!

    private struct Release: Decodable {
        let tag_name: String
        let draft: Bool
        let prerelease: Bool
    }

    private static func versionParts(_ version: String) -> [Int]? {
        let text = version.hasPrefix("v") ? String(version.dropFirst()) : version
        let parts = text.split(separator: ".", omittingEmptySubsequences: false)
        guard !parts.isEmpty else { return nil }
        var numbers: [Int] = []
        for part in parts {
            guard !part.isEmpty, part.utf8.allSatisfy({ (48...57).contains($0) }), let number = Int(part) else { return nil }
            numbers.append(number)
        }
        return numbers
    }

    static func newerTag(in data: Data, current: String = AppVersion.current) -> String? {
        guard let release = try? JSONDecoder().decode(Release.self, from: data),
              !release.draft, !release.prerelease,
              let latest = versionParts(release.tag_name), let installed = versionParts(current) else { return nil }
        for index in 0..<max(latest.count, installed.count) {
            let remote = index < latest.count ? latest[index] : 0
            let local = index < installed.count ? installed[index] : 0
            if remote != local { return remote > local ? "v" + latest.map(String.init).joined(separator: ".") : nil }
        }
        return nil
    }

    static func check(completion: @escaping (String?) -> Void) -> URLSessionDataTask {
        var request = URLRequest(url: apiURL, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 10)
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        request.setValue("SilenceTrim/\(AppVersion.current)", forHTTPHeaderField: "User-Agent")
        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            let tag = error == nil && (response as? HTTPURLResponse)?.statusCode == 200
                ? data.flatMap { newerTag(in: $0) } : nil
            DispatchQueue.main.async { completion(tag) }
        }
        task.resume()
        return task
    }
}
