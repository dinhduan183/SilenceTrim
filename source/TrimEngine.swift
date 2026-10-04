import Foundation

struct TrimSettings: Codable {
    var threshold: Double = -60
    var padding: Double = 0.5
    var recursive: Bool = false
    func validate() throws {
        guard threshold.isFinite, (-100 ... -20).contains(threshold), padding.isFinite, (0.1 ... 2).contains(padding) else {
            throw TrimError.message("Ngưỡng phải từ −100 đến −20 dB; khoảng giữ lại từ 0,1 đến 2 giây.")
        }
    }
}
enum TrimError: Error, LocalizedError {
    case message(String), cancelled
    var errorDescription: String? { switch self { case .message(let s): return s; case .cancelled: return "Đã dừng." } }
}
struct AudioInfo {
    var codec: String
    var rate: Int
    var bits: Int
    var sampleFormat: String
    var artIndices: [Int]
    var lossless: Bool { codec == "flac" || codec == "alac" || ["pcm_s", "pcm_u", "pcm_f"].contains(where: { codec.hasPrefix($0) }) }
}
struct Edges {
    var duration: Double
    var leading: Double
    var trailing: Double
    var allSilent: Bool
}
struct Track: Codable {
    var source: String
    var relative: String
    var duration: Double = 0
    var leading: Double = 0
    var trailing: Double = 0
    var cutStart: Double = 0
    var cutEnd: Double = 0
    var codec: String = ""
    var lossless: Bool = false
    var selected: Bool = true
    var allSilent: Bool = false
    var status: String = "Đang chờ"
    var error: String? = nil
    var originalSize: UInt64 = 0
    var originalModified: Double = 0
    var output: String? = nil
    var verifiedLeading: Double? = nil
    var verifiedTrailing: Double? = nil
}
struct BatchReport: Codable {
    var version = "1.0"
    var createdAt = ISO8601DateFormatter().string(from: Date())
    var settings: TrimSettings
    var tracks: [Track]
}

final class TrimEngine {
    static let extensions: Set<String> = ["mp3", "m4a", "aac", "flac", "wav", "aif", "aiff", "ogg", "opus"]
    private let lock = NSLock()
    private var stopped = false
    private var activeProcess: Process?
    let ffmpeg: URL
    let ffprobe: URL
    init() throws {
        func find(_ name: String) throws -> URL {
            let bundled = Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/\(name)").path
            let paths = [bundled, "/opt/homebrew/bin/\(name)", "/usr/local/bin/\(name)", "/usr/bin/\(name)"]
                + (ProcessInfo.processInfo.environment["PATH"] ?? "").split(separator: ":").map { "\($0)/\(name)" }
            guard let path = paths.first(where: { FileManager.default.isExecutableFile(atPath: $0) }) else {
                throw TrimError.message("Thiếu \(name). Cài FFmpeg bằng Homebrew: brew install ffmpeg, rồi mở lại app.")
            }
            return URL(fileURLWithPath: path)
        }
        ffmpeg = try find("ffmpeg"); ffprobe = try find("ffprobe")
    }
    func resetCancellation() { lock.lock(); stopped = false; lock.unlock() }
    func cancel() { lock.lock(); stopped = true; let p = activeProcess; lock.unlock(); if let p, p.isRunning { p.terminate() } }
    func checkCancellation() throws { lock.lock(); let value = stopped; lock.unlock(); if value { throw TrimError.cancelled } }
    private func run(_ tool: URL, _ arguments: [String]) throws -> String {
        try checkCancellation()
        let logURL = FileManager.default.temporaryDirectory.appendingPathComponent("silencetrim-\(UUID().uuidString).log")
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        let log = try FileHandle(forWritingTo: logURL)
        defer { try? log.close(); try? FileManager.default.removeItem(at: logURL) }
        let process = Process(); process.executableURL = tool; process.arguments = arguments
        process.standardOutput = log; process.standardError = log; process.standardInput = FileHandle.nullDevice
        lock.lock()
        if stopped { lock.unlock(); throw TrimError.cancelled }
        do { try process.run(); activeProcess = process; lock.unlock() } catch { lock.unlock(); throw error }
        process.waitUntilExit()
        lock.lock(); activeProcess = nil; lock.unlock()
        try checkCancellation()
        try log.synchronize()
        let output = String(data: try Data(contentsOf: logURL), encoding: .utf8) ?? ""
        guard process.terminationStatus == 0 else {
            throw TrimError.message(String(output.suffix(1400)).trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return output
    }
    func inventory(_ folder: URL, settings: TrimSettings, excluding output: URL? = nil) throws -> [URL] {
        try settings.validate()
        let root = folder.resolvingSymlinksInPath().standardizedFileURL
        let exclude = output?.resolvingSymlinksInPath().standardizedFileURL.path
        let keys: [URLResourceKey] = [.isRegularFileKey, .isSymbolicLinkKey, .isDirectoryKey]
        let options: FileManager.DirectoryEnumerationOptions = settings.recursive ? [.skipsHiddenFiles, .skipsPackageDescendants] : [.skipsHiddenFiles, .skipsSubdirectoryDescendants]
        guard let iterator = FileManager.default.enumerator(at: root, includingPropertiesForKeys: keys, options: options) else {
            throw TrimError.message("Không đọc được thư mục.")
        }
        var files: [URL] = []
        for case let url as URL in iterator {
            try checkCancellation()
            let values = try url.resourceValues(forKeys: Set(keys))
            if values.isSymbolicLink == true { continue }
            if let exclude, url.path == exclude || url.path.hasPrefix(exclude + "/") { if values.isDirectory == true { iterator.skipDescendants() }; continue }
            if values.isRegularFile == true, Self.extensions.contains(url.pathExtension.lowercased()) { files.append(url) }
        }
        return files.sorted { $0.path.localizedStandardCompare($1.path) == .orderedAscending }
    }
    func probe(_ url: URL) throws -> AudioInfo {
        let json = try run(ffprobe, ["-v", "error", "-show_streams", "-of", "json", url.path])
        guard let data = json.data(using: .utf8), let root = try JSONSerialization.jsonObject(with: data) as? [String: Any], let streams = root["streams"] as? [[String: Any]] else { throw TrimError.message("Không đọc được thông tin audio.") }
        let audio = streams.filter { $0["codec_type"] as? String == "audio" }
        guard audio.count == 1, let first = audio.first else { throw TrimError.message("File phải có đúng một luồng âm thanh.") }
        let videos = streams.filter { $0["codec_type"] as? String == "video" }
        guard videos.allSatisfy({ ($0["disposition"] as? [String: Any])?["attached_pic"] as? Int == 1 }) else {
            throw TrimError.message("File có video, không phải bài nhạc độc lập.")
        }
        return AudioInfo(codec: first["codec_name"] as? String ?? "", rate: Int(first["sample_rate"] as? String ?? "") ?? 44100,
                         bits: Int(first["bits_per_raw_sample"] as? String ?? "") ?? (first["bits_per_sample"] as? Int ?? 0),
                         sampleFormat: first["sample_fmt"] as? String ?? "", artIndices: videos.compactMap { $0["index"] as? Int })
    }
    func detect(_ url: URL, settings: TrimSettings, rate: Int = 44100) throws -> Edges {
        let progress = FileManager.default.temporaryDirectory.appendingPathComponent("silencetrim-\(UUID().uuidString).progress")
        defer { try? FileManager.default.removeItem(at: progress) }
        let log = try run(ffmpeg, ["-hide_banner", "-nostdin", "-nostats", "-xerror", "-i", url.path, "-map", "0:a:0", "-vn", "-af", "asetpts=PTS-STARTPTS,silencedetect=noise=\(settings.threshold)dB:d=0.05", "-progress", progress.path, "-f", "null", "-"])
        let progressText = (try? String(contentsOf: progress, encoding: .utf8)) ?? ""
        let times = progressText.split(separator: "\n").filter { $0.hasPrefix("out_time_us=") }.compactMap { Double($0.dropFirst(12)) }
        guard let last = times.last, last > 0 else { throw TrimError.message("File không có thời lượng âm thanh hợp lệ.") }
        let duration = last / 1_000_000
        let regex = try NSRegularExpression(pattern: "silence_(start|end): ([0-9.eE+\\-]+)")
        var intervals: [(Double, Double)] = []; var start: Double?
        for match in regex.matches(in: log, range: NSRange(log.startIndex..., in: log)) {
            guard let typeRange = Range(match.range(at: 1), in: log), let valueRange = Range(match.range(at: 2), in: log), let value = Double(log[valueRange]) else { continue }
            if log[typeRange] == "start" { start = max(0, value) }
            else if let s = start { intervals.append((s, min(duration, value))); start = nil }
        }
        if let start { intervals.append((start, duration)) }
        let epsilon = max(0.0001, 2 / Double(rate))
        let leading = intervals.first.flatMap { $0.0 <= epsilon ? $0.1 : nil } ?? 0
        let trailing = intervals.last.flatMap { abs($0.1 - duration) <= epsilon ? duration - $0.0 : nil } ?? 0
        return Edges(duration: duration, leading: leading, trailing: trailing, allSilent: leading >= duration - epsilon)
    }
    func analyze(_ url: URL, relative: String, settings: TrimSettings) throws -> Track {
        try settings.validate()
        var track = Track(source: url.path, relative: relative)
        let attrs = try FileManager.default.attributesOfItem(atPath: url.path)
        track.originalSize = (attrs[.size] as? NSNumber)?.uint64Value ?? 0
        track.originalModified = (attrs[.modificationDate] as? Date)?.timeIntervalSince1970 ?? 0
        let info = try probe(url); let edges = try detect(url, settings: settings, rate: info.rate)
        track.codec = info.codec; track.lossless = info.lossless; track.duration = edges.duration
        track.leading = edges.leading; track.trailing = edges.trailing; track.allSilent = edges.allSilent
        if edges.allSilent { track.status = "Toàn bộ im lặng · giữ nguyên"; return track }
        // Leave a packet margin for compressed audio, then verify the actual result.
        let retained = info.lossless ? settings.padding : max(0.05, settings.padding - 0.08)
        track.cutStart = edges.leading > settings.padding ? max(0, edges.leading - retained) : 0
        track.cutEnd = edges.trailing > settings.padding ? max(0, edges.trailing - retained) : 0
        track.status = track.cutStart + track.cutEnd > 0 ? "Sẵn sàng cắt" : "Đã đạt · giữ nguyên"
        return track
    }
    func export(_ track: Track, to destination: URL, settings: TrimSettings) throws -> Track {
        try checkCancellation()
        let fm = FileManager.default; let source = URL(fileURLWithPath: track.source)
        let attrs = try fm.attributesOfItem(atPath: source.path)
        guard (attrs[.size] as? NSNumber)?.uint64Value == track.originalSize,
              (attrs[.modificationDate] as? Date)?.timeIntervalSince1970 == track.originalModified else {
            throw TrimError.message("File gốc đã thay đổi sau khi phân tích. Hãy phân tích lại.")
        }
        guard !fm.fileExists(atPath: destination.path) else { throw TrimError.message("File đích đã tồn tại; không ghi đè.") }
        try fm.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
        let temp = destination.deletingLastPathComponent().appendingPathComponent(".silencetrim-\(UUID().uuidString).\(destination.pathExtension)")
        defer { try? fm.removeItem(at: temp) }
        var result = track
        if track.cutStart + track.cutEnd <= 0 {
            try fm.copyItem(at: source, to: temp); try checkCancellation(); try fm.moveItem(at: temp, to: destination)
            result.status = track.allSilent ? "Đã sao chép · toàn bộ im lặng" : "Đã sao chép · đã đạt"
            result.output = destination.path; result.verifiedLeading = track.leading; result.verifiedTrailing = track.trailing
            return result
        }
        let info = try probe(source)
        var start = track.cutStart; var endCut = track.cutEnd
        for attempt in 0..<4 {
            try checkCancellation()
            let end = track.duration - endCut
            var args = ["-hide_banner", "-nostdin", "-loglevel", "error", "-xerror", "-y", "-i", source.path]
            if info.lossless {
                let firstSample = Int((start * Double(info.rate)).rounded(.up))
                let lastSample = Int((end * Double(info.rate)).rounded(.down))
                args += ["-map", "0:a:0", "-af", "atrim=start_sample=\(firstSample):end_sample=\(lastSample),asetpts=PTS-STARTPTS", "-c:a", info.codec]
                if info.codec == "flac" || info.codec == "alac" {
                    let format = (info.bits > 16 ? "s32" : "s16") + (info.codec == "alac" ? "p" : "")
                    args += ["-sample_fmt", format]
                    if info.bits > 0 { args += ["-bits_per_raw_sample", "\(info.bits)"] }
                }
            } else {
                args += ["-ss", String(format: "%.9f", start), "-t", String(format: "%.9f", end - start), "-map", "0:a:0", "-c:a", "copy"]
            }
            args += ["-c:v", "copy", "-map_metadata", "0", "-map_metadata:s:a:0", "0:s:a:0", "-map_chapters", "-1", temp.path]
            _ = try run(ffmpeg, args)
            if !info.artIndices.isEmpty {
                // Attach artwork after seeking, so an image at timestamp zero is not discarded.
                let withArt = destination.deletingLastPathComponent().appendingPathComponent(".silencetrim-art-\(UUID().uuidString).\(destination.pathExtension)")
                defer { try? fm.removeItem(at: withArt) }
                var remux = ["-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", temp.path, "-i", source.path, "-map", "0:a:0"]
                for index in info.artIndices { remux += ["-map", "1:\(index)"] }
                remux += ["-c", "copy", "-disposition:v", "attached_pic", "-map_metadata", "1", "-map_metadata:s:a:0", "1:s:a:0", "-map_chapters", "-1", withArt.path]
                _ = try run(ffmpeg, remux)
                try fm.removeItem(at: temp); try fm.moveItem(at: withArt, to: temp)
            }
            let outputInfo = try probe(temp)
            guard outputInfo.codec == info.codec, outputInfo.rate == info.rate, outputInfo.artIndices.count == info.artIndices.count, (info.bits == 0 || !info.lossless || outputInfo.bits == info.bits) else { throw TrimError.message("Thông số âm thanh đầu ra thay đổi; không xuất file.") }
            let edges = try detect(temp, settings: settings, rate: info.rate)
            guard !edges.allSilent else { throw TrimError.message("Đầu ra chỉ còn im lặng; không xuất file.") }
            let headExcess = max(0, edges.leading - settings.padding)
            let tailExcess = max(0, edges.trailing - settings.padding)
            if headExcess <= 0.000002 && tailExcess <= 0.000002 {
                try checkCancellation(); try fm.moveItem(at: temp, to: destination)
                result.cutStart = start; result.cutEnd = endCut; result.output = destination.path
                result.verifiedLeading = edges.leading; result.verifiedTrailing = edges.trailing
                result.status = "Đã cắt · đã kiểm tra"; return result
            }
            guard attempt < 3 else { break }
            let nextStart = start + (headExcess > 0 ? headExcess + 0.025 : 0)
            let nextEnd = endCut + (tailExcess > 0 ? tailExcess + 0.025 : 0)
            // Never consume the detected music to work around packet boundaries.
            guard nextStart < track.leading || nextStart == 0,
                  nextEnd < track.trailing || nextEnd == 0 else { break }
            start = nextStart; endCut = nextEnd
        }
        throw TrimError.message("Không đạt giới hạn im lặng bằng cắt lossless; file gốc được giữ nguyên.")
    }
    static func validateOutput(_ output: URL, input: URL) throws {
        let out = output.resolvingSymlinksInPath().standardizedFileURL.path
        let source = input.resolvingSymlinksInPath().standardizedFileURL.path
        guard out != source, !source.hasPrefix(out + "/") else { throw TrimError.message("Chọn thư mục xuất khác thư mục gốc và không phải thư mục cha của nó.") }
    }
    static func saveReport(_ tracks: [Track], settings: TrimSettings, folder: URL) throws -> URL {
        let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        let url = folder.appendingPathComponent("SilenceTrim-report-\(UUID().uuidString.prefix(8)).json")
        try encoder.encode(BatchReport(settings: settings, tracks: tracks)).write(to: url, options: .atomic)
        return url
    }
}
