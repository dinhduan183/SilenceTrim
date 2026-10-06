import Foundation

let fm = FileManager.default
let workspace = URL(fileURLWithPath: "/tmp/silencetrim-path-tests-\(UUID().uuidString)")
try fm.createDirectory(at: workspace, withIntermediateDirectories: true)
defer { try? fm.removeItem(at: workspace) }

func expect(_ condition: Bool, _ message: String) throws {
    guard condition else { throw TrimError.message(message) }
}
func expectRejected(_ message: String, _ operation: () throws -> Void) throws {
    do { try operation() } catch { return }
    throw TrimError.message(message)
}
func run(_ executable: URL, _ arguments: [String]) throws {
    let process = Process()
    process.executableURL = executable; process.arguments = arguments
    try process.run(); process.waitUntilExit()
    try expect(process.terminationStatus == 0, "Command failed: \(executable.lastPathComponent)")
}

let input = workspace.appendingPathComponent("nhạc nguồn")
let nested = input.appendingPathComponent("album")
let output = input.appendingPathComponent("kết quả")
try fm.createDirectory(at: nested, withIntermediateDirectories: true)
try fm.createDirectory(at: output, withIntermediateDirectories: true)
let alias = workspace.appendingPathComponent("source-alias")
try fm.createSymbolicLink(at: alias, withDestinationURL: input)
let engine = try TrimEngine()
let song = input.appendingPathComponent("bài hát.wav")
try run(engine.ffmpeg, ["-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-af", "adelay=1000,apad=pad_dur=1", song.path])
try fm.copyItem(at: song, to: nested.appendingPathComponent("bài hát.wav"))
try fm.copyItem(at: song, to: output.appendingPathComponent("old.wav"))
try fm.createSymbolicLink(at: input.appendingPathComponent("linked.wav"), withDestinationURL: song)

let files = try engine.inventory(alias, settings: TrimSettings(recursive: true), excluding: alias.appendingPathComponent("kết quả"))
let relative = try files.map { try TrimEngine.relativePath(of: $0, in: alias) }.sorted()
try expect(relative == ["album/bài hát.wav", "bài hát.wav"], "Symlink source or output exclusion changed the directory structure: \(relative)")
let shallow = try engine.inventory(alias, settings: TrimSettings(), excluding: output)
try expect(shallow.count == 1, "Nonrecursive inventory included a subdirectory")
let privateSong = URL(fileURLWithPath: "/private" + song.path)
try expect(try TrimEngine.relativePath(of: privateSong, in: input) == "bài hát.wav", "/tmp and /private/tmp aliases disagree")
try expect(try TrimEngine.relativePath(of: song, in: URL(fileURLWithPath: "/")) == String(TrimEngine.canonicalURL(song).path.dropFirst()), "Root folder has an incorrect relative path")
try expectRejected("Sibling with the same prefix was accepted") {
    _ = try TrimEngine.relativePath(of: workspace.appendingPathComponent("nhạc nguồn khác/song.wav"), in: input)
}
try expectRejected("Source folder itself was accepted as a file") { _ = try TrimEngine.relativePath(of: alias, in: input) }
try expectRejected("Source alias was accepted as output") { try TrimEngine.validateOutput(alias, input: input) }
try expectRejected("Parent folder was accepted as output") { try TrimEngine.validateOutput(workspace, input: alias) }
try expectRejected("Filesystem root was accepted as output") { try TrimEngine.validateOutput(URL(fileURLWithPath: "/"), input: input) }
try TrimEngine.validateOutput(output, input: alias)
try TrimEngine.validateOutput(workspace.appendingPathComponent("nhạc nguồn khác"), input: alias)

guard CommandLine.arguments.count == 2 else { throw TrimError.message("Pass the SilenceTrim executable path") }
try run(URL(fileURLWithPath: CommandLine.arguments[1]), ["--batch", "--input", alias.path, "--output", alias.appendingPathComponent("kết quả").path, "--recursive"])
try expect(fm.fileExists(atPath: output.appendingPathComponent("bài hát.wav").path), "Batch export misplaced the top-level file")
try expect(fm.fileExists(atPath: output.appendingPathComponent("album/bài hát.wav").path), "Batch export misplaced the nested file")
let reports = try fm.contentsOfDirectory(at: output, includingPropertiesForKeys: nil).filter { $0.pathExtension == "json" }
let report = try JSONDecoder().decode(BatchReport.self, from: Data(contentsOf: reports[0]))
try expect(report.tracks.map(\.relative).sorted() == relative, "Batch report contains incorrect relative paths")
try expect(report.tracks.allSatisfy { $0.error == nil && $0.output != nil }, "Batch export failed")
print("PASS: symlinks, system aliases, nested paths, Unicode, output exclusion, containment and batch export")
