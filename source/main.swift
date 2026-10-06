import Cocoa

private func seconds(_ n: Double) -> String { String(format: "%.2f s", n) }
private func timeText(_ n: Double) -> String { String(format: "%d:%05.2f", Int(n) / 60, n.truncatingRemainder(dividingBy: 60)) }

final class DropView: NSView {
    var onDrop: ((URL) -> Void)?
    override init(frame: NSRect) { super.init(frame: frame); registerForDraggedTypes([.fileURL]) }
    required init?(coder: NSCoder) { fatalError() }
    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation { .copy }
    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        guard let urls = sender.draggingPasteboard.readObjects(forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL], let first = urls.first else { return false }
        var directory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: first.path, isDirectory: &directory), directory.boolValue else { return false }
        onDrop?(first); return true
    }
}
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, NSTableViewDataSource, NSTableViewDelegate {
    var window: NSWindow!
    var table = NSTableView()
    var inputURL: URL?; var outputURL: URL?
    var tracks: [Track] = []; var analyzedSettings = TrimSettings()
    var engine: TrimEngine?
    var busy = false
    var chooseInput: NSButton!; var chooseOutput: NSButton!; var analyzeButton: NSButton!; var trimButton: NSButton!; var cancelButton: NSButton!
    var revealButton: NSButton!
    var threshold = NSPopUpButton(); var padding = NSTextField(string: "0.5"); var recursive = NSButton(checkboxWithTitle: "Gồm thư mục con", target: nil, action: nil)
    var inputLabel = NSTextField(labelWithString: "Chọn hoặc kéo thư mục nhạc vào cửa sổ")
    var outputLabel = NSTextField(labelWithString: "Tự tạo thư mục xuất bên cạnh thư mục gốc")
    var statusLabel = NSTextField(labelWithString: "Sẵn sàng · File gốc luôn được giữ nguyên")
    var detailLabel = NSTextField(wrappingLabelWithString: "Chọn một bài để xem chi tiết. Chỉ cắt im lặng ở hai đầu; khoảng nghỉ giữa bài được giữ nguyên.")
    var summary = NSTextField(labelWithString: "CHƯA CÓ BÀI NHẠC")
    var progress = NSProgressIndicator()
    let accent = NSColor(calibratedRed: 0.24, green: 0.84, blue: 0.70, alpha: 1)
    func applicationDidFinishLaunching(_ notification: Notification) {
        makeMenu()
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1040, height: 760), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "SilenceTrim"; window.minSize = NSSize(width: 920, height: 690); window.delegate = self
        window.appearance = NSAppearance(named: .darkAqua)
        let root = DropView(); root.wantsLayer = true; root.layer?.backgroundColor = NSColor(calibratedRed: 0.055, green: 0.075, blue: 0.11, alpha: 1).cgColor
        root.onDrop = { [weak self] url in if self?.busy == false { self?.setInput(url) } }
        window.contentView = root
        let content = NSStackView(); content.orientation = .vertical; content.alignment = .leading; content.spacing = 18
        content.translatesAutoresizingMaskIntoConstraints = false; root.addSubview(content)
        NSLayoutConstraint.activate([content.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 28), content.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -28), content.topAnchor.constraint(equalTo: root.topAnchor, constant: 24), content.bottomAnchor.constraint(equalTo: root.bottomAnchor, constant: -22)])
        let eyebrow = label("BATCH AUDIO • LOSSLESS TRIM", size: 11, weight: .semibold); eyebrow.textColor = accent
        let title = label("Gọn hai đầu. Giữ chất lượng.", size: 30, weight: .bold)
        let subtitle = label("Cắt khoảng im lặng đầu và cuối hàng loạt, giữ lại tối đa 0,5 giây mỗi phía.", size: 13)
        subtitle.textColor = .secondaryLabelColor
        let hero = vertical([eyebrow, title, subtitle], spacing: 6); full(hero, content)
        chooseInput = button("Chọn thư mục…", #selector(pickInput)); chooseOutput = button("Đổi nơi xuất…", #selector(pickOutput))
        inputLabel.font = .systemFont(ofSize: 13, weight: .medium); outputLabel.font = .systemFont(ofSize: 12)
        for field in [inputLabel, outputLabel] { field.lineBreakMode = .byTruncatingMiddle; field.setContentCompressionResistancePriority(.defaultLow, for: .horizontal) }
        let sourceRow = horizontal([label("NGUỒN", size: 10, weight: .bold), inputLabel, chooseInput]); sourceRow.spacing = 16
        let outputRow = horizontal([label("XUẤT", size: 10, weight: .bold), outputLabel, chooseOutput]); outputRow.spacing = 16
        inputLabel.setContentHuggingPriority(.defaultLow, for: .horizontal); outputLabel.setContentHuggingPriority(.defaultLow, for: .horizontal)
        full(card(vertical([sourceRow, outputRow], spacing: 12)), content)
        threshold.addItems(withTitles: ["−60 dB · mặc định", "−70 dB · giữ âm rất nhỏ", "−80 dB · gần im lặng tuyệt đối", "−50 dB · nhạy hơn", "−40 dB · rất nhạy"])
        threshold.target = self; threshold.action = #selector(settingsChanged)
        padding.widthAnchor.constraint(equalToConstant: 58).isActive = true; padding.alignment = .center
        padding.target = self; padding.action = #selector(settingsChanged)
        recursive.target = self; recursive.action = #selector(settingsChanged)
        let settingsRow = horizontal([label("Ngưỡng im lặng", size: 12), threshold, label("Giữ tối đa", size: 12), padding, label("giây / phía", size: 12), spacer(), recursive]); settingsRow.spacing = 10
        full(settingsRow, content)
        let note = NSTextField(wrappingLabelWithString: "Âm dưới ngưỡng được xem là im lặng. MP3/AAC/Opus cắt theo gói âm thanh, không nén lại; WAV/FLAC/ALAC giữ nguyên mẫu âm thanh. Có thể giữ ít hơn 0,5 giây để bù biên gói.")
        note.font = .systemFont(ofSize: 11); note.textColor = .secondaryLabelColor; full(note, content)
        summary.font = .systemFont(ofSize: 11, weight: .semibold); summary.textColor = accent; full(summary, content)
        table.headerView = NSTableHeaderView(); table.rowHeight = 38; table.intercellSpacing = NSSize(width: 12, height: 0)
        table.backgroundColor = NSColor(calibratedRed: 0.075, green: 0.095, blue: 0.135, alpha: 1)
        table.usesAlternatingRowBackgroundColors = false; table.style = .plain
        table.dataSource = self; table.delegate = self
        let columns: [(String, String, CGFloat)] = [("selected", "Xuất", 44), ("file", "Bài nhạc", 280), ("duration", "Độ dài", 85), ("head", "Cắt đầu", 85), ("tail", "Cắt cuối", 85), ("status", "Trạng thái", 250)]
        for (id, name, width) in columns {
            let c = NSTableColumn(identifier: NSUserInterfaceItemIdentifier(id)); c.title = name; c.width = width; c.minWidth = id == "file" ? 150 : width
            if id == "selected" { c.maxWidth = width }
            table.addTableColumn(c)
        }
        table.columnAutoresizingStyle = .lastColumnOnlyAutoresizingStyle
        let scroll = NSScrollView(); scroll.documentView = table; scroll.hasVerticalScroller = true; scroll.hasHorizontalScroller = true; scroll.borderType = .noBorder
        scroll.wantsLayer = true; scroll.layer?.cornerRadius = 10
        full(scroll, content); scroll.heightAnchor.constraint(greaterThanOrEqualToConstant: 180).isActive = true
        scroll.setContentHuggingPriority(.defaultLow, for: .vertical)
        detailLabel.font = .systemFont(ofSize: 11); detailLabel.textColor = .secondaryLabelColor
        full(detailLabel, content); detailLabel.heightAnchor.constraint(equalToConstant: 43).isActive = true
        progress.style = .bar; progress.isIndeterminate = false; progress.minValue = 0; progress.maxValue = 100; full(progress, content)
        analyzeButton = button("1. Phân tích", #selector(analyze)); analyzeButton.keyEquivalent = "r"
        trimButton = button("2. Cắt & xuất", #selector(trim)); trimButton.bezelColor = accent; trimButton.keyEquivalent = "\r"
        cancelButton = button("Dừng", #selector(cancel)); cancelButton.isEnabled = false
        revealButton = button("Mở kết quả", #selector(reveal)); revealButton.isEnabled = false
        full(horizontal([analyzeButton, trimButton, cancelButton, spacer(), revealButton]), content)
        statusLabel.font = .systemFont(ofSize: 12); statusLabel.lineBreakMode = .byTruncatingMiddle; full(statusLabel, content)
        do { engine = try TrimEngine() } catch { statusLabel.stringValue = error.localizedDescription }
        refreshControls(); window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
        if let index = CommandLine.arguments.firstIndex(of: "--folder"), index + 1 < CommandLine.arguments.count {
            setInput(URL(fileURLWithPath: CommandLine.arguments[index + 1]))
        }
    }
    func makeMenu() {
        let menu = NSMenu(); let item = NSMenuItem(); menu.addItem(item); let appMenu = NSMenu(); item.submenu = appMenu
        appMenu.addItem(withTitle: "Về SilenceTrim", action: #selector(about), keyEquivalent: "")
        appMenu.addItem(.separator()); appMenu.addItem(withTitle: "Thoát SilenceTrim", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let edit = NSMenuItem(); menu.addItem(edit); let editMenu = NSMenu(title: "Sửa"); edit.submenu = editMenu
        editMenu.addItem(withTitle: "Sao chép", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Dán", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Chọn tất cả", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        NSApp.mainMenu = menu
    }
    func label(_ text: String, size: CGFloat, weight: NSFont.Weight = .regular) -> NSTextField { let f = NSTextField(labelWithString: text); f.font = .systemFont(ofSize: size, weight: weight); return f }
    func button(_ text: String, _ action: Selector) -> NSButton { let b = NSButton(title: text, target: self, action: action); b.bezelStyle = .rounded; b.controlSize = .large; return b }
    func spacer() -> NSView { let v = NSView(); v.setContentHuggingPriority(.defaultLow, for: .horizontal); return v }
    func horizontal(_ views: [NSView]) -> NSStackView { let s = NSStackView(views: views); s.orientation = .horizontal; s.alignment = .centerY; s.spacing = 10; return s }
    func vertical(_ views: [NSView], spacing: CGFloat) -> NSStackView { let s = NSStackView(views: views); s.orientation = .vertical; s.alignment = .leading; s.spacing = spacing; for view in views { view.widthAnchor.constraint(equalTo: s.widthAnchor).isActive = true }; return s }
    func full(_ view: NSView, _ parent: NSStackView) { parent.addArrangedSubview(view); view.widthAnchor.constraint(equalTo: parent.widthAnchor).isActive = true }
    func card(_ view: NSView) -> NSView {
        let wrapper = NSView(); wrapper.wantsLayer = true; wrapper.layer?.cornerRadius = 12
        wrapper.layer?.backgroundColor = NSColor(calibratedRed: 0.095, green: 0.12, blue: 0.17, alpha: 1).cgColor
        view.translatesAutoresizingMaskIntoConstraints = false; wrapper.addSubview(view)
        NSLayoutConstraint.activate([view.leadingAnchor.constraint(equalTo: wrapper.leadingAnchor, constant: 16), view.trailingAnchor.constraint(equalTo: wrapper.trailingAnchor, constant: -16), view.topAnchor.constraint(equalTo: wrapper.topAnchor, constant: 14), view.bottomAnchor.constraint(equalTo: wrapper.bottomAnchor, constant: -14)])
        return wrapper
    }
    func readSettings() throws -> TrimSettings {
        let thresholds: [Double] = [-60, -70, -80, -50, -40]
        guard let value = Double(padding.stringValue.replacingOccurrences(of: ",", with: ".")) else { throw TrimError.message("Khoảng giữ lại phải là số, ví dụ 0.5.") }
        let settings = TrimSettings(threshold: thresholds[max(0, threshold.indexOfSelectedItem)], padding: value, recursive: recursive.state == .on)
        try settings.validate(); return settings
    }
    func setInput(_ url: URL) {
        inputURL = TrimEngine.canonicalURL(url)
        inputLabel.stringValue = inputURL!.path; inputLabel.toolTip = inputURL!.path
        outputURL = uniqueOutput(for: inputURL!)
        outputLabel.stringValue = outputURL!.path; outputLabel.toolTip = outputURL!.path
        invalidate(); statusLabel.stringValue = "Đã chọn thư mục · Nhấn Phân tích để xem trước"
    }
    func uniqueOutput(for source: URL) -> URL {
        let parent = source.deletingLastPathComponent(); let name = source.lastPathComponent + " — Trimmed"
        var candidate = parent.appendingPathComponent(name); var n = 2
        while FileManager.default.fileExists(atPath: candidate.path) { candidate = parent.appendingPathComponent("\(name) \(n)"); n += 1 }
        return candidate
    }
    @objc func pickInput() { let panel = NSOpenPanel(); panel.canChooseDirectories = true; panel.canChooseFiles = false; panel.allowsMultipleSelection = false; panel.prompt = "Chọn thư mục nhạc"; if panel.runModal() == .OK, let url = panel.url { setInput(url) } }
    @objc func pickOutput() {
        let panel = NSOpenPanel(); panel.canChooseDirectories = true; panel.canChooseFiles = false; panel.canCreateDirectories = true; panel.prompt = "Chọn nơi xuất"
        if panel.runModal() == .OK, let url = panel.url {
            do { if let inputURL { try TrimEngine.validateOutput(url, input: inputURL) }; outputURL = url; outputLabel.stringValue = url.path; outputLabel.toolTip = url.path; invalidate() } catch { alert(error.localizedDescription) }
        }
    }
    @objc func settingsChanged() { if !busy { invalidate() } }
    func invalidate() { tracks = []; table.reloadData(); progress.doubleValue = 0; updateSummary(); refreshControls(); detailLabel.stringValue = "Thiết lập thay đổi sẽ cần phân tích lại. Chỉ cắt khoảng im lặng ở hai đầu." }
    func refreshControls() {
        chooseInput.isEnabled = !busy; chooseOutput.isEnabled = !busy && inputURL != nil
        threshold.isEnabled = !busy; padding.isEnabled = !busy; recursive.isEnabled = !busy
        analyzeButton.isEnabled = !busy && inputURL != nil && engine != nil
        trimButton.isEnabled = !busy && tracks.contains { $0.selected && $0.error == nil && $0.output == nil }
        cancelButton.isEnabled = busy
        revealButton.isEnabled = !busy && outputURL.map { FileManager.default.fileExists(atPath: $0.path) } == true
    }
    func updateSummary() {
        let good = tracks.filter { $0.error == nil }; let trim = good.filter { $0.cutStart + $0.cutEnd > 0 }
        summary.stringValue = tracks.isEmpty ? "CHƯA CÓ BÀI NHẠC" : "\(tracks.count) BÀI  •  \(trim.count) CẦN CẮT  •  \(seconds(trim.reduce(0) { $0 + $1.cutStart + $1.cutEnd })) CÓ THỂ BỎ  •  \(tracks.filter { $0.output != nil }.count) ĐÃ XUẤT"
    }
    @objc func analyze() {
        guard !busy, let engine, let inputURL, let outputURL else { return }
        do {
            let settings = try readSettings(); try TrimEngine.validateOutput(outputURL, input: inputURL)
            busy = true; engine.resetCancellation(); analyzedSettings = settings; tracks = []; table.reloadData(); refreshControls()
            progress.doubleValue = 0; statusLabel.stringValue = "Đang tìm bài nhạc…"
            DispatchQueue.global(qos: .userInitiated).async { [self] in
                do {
                    let files = try engine.inventory(inputURL, settings: settings, excluding: outputURL)
                    guard !files.isEmpty else { throw TrimError.message("Không tìm thấy file MP3, M4A, AAC, WAV, FLAC, AIFF, OGG hoặc Opus.") }
                    for (index, url) in files.enumerated() {
                        try engine.checkCancellation()
                        let relative = try TrimEngine.relativePath(of: url, in: inputURL)
                        DispatchQueue.main.async { self.statusLabel.stringValue = "Phân tích \(index + 1)/\(files.count): \(relative)" }
                        var track: Track
                        do { track = try engine.analyze(url, relative: relative, settings: settings) }
                        catch TrimError.cancelled { throw TrimError.cancelled }
                        catch { track = Track(source: url.path, relative: relative, selected: false, status: "Lỗi phân tích", error: error.localizedDescription) }
                        let completedTrack = track
                        DispatchQueue.main.sync { self.tracks.append(completedTrack); self.table.reloadData(); self.progress.doubleValue = Double(index + 1) / Double(files.count) * 100; self.updateSummary() }
                    }
                    DispatchQueue.main.async { self.finish("Phân tích xong · Xem mức cắt, bỏ chọn bài muốn giữ, rồi nhấn Cắt & xuất") }
                } catch { DispatchQueue.main.async { self.finish(error.localizedDescription) } }
            }
        } catch { alert(error.localizedDescription) }
    }
    @objc func trim() {
        guard !busy, let engine, let inputURL, let outputURL else { return }
        do {
            let current = try readSettings()
            guard current.threshold == analyzedSettings.threshold, current.padding == analyzedSettings.padding, current.recursive == analyzedSettings.recursive else { invalidate(); throw TrimError.message("Thiết lập đã thay đổi. Hãy phân tích lại trước khi xuất.") }
            try TrimEngine.validateOutput(outputURL, input: inputURL)
            let work = tracks.enumerated().filter { $0.element.selected && $0.element.error == nil && $0.element.output == nil }
            guard !work.isEmpty else { return }
            busy = true; engine.resetCancellation(); refreshControls(); progress.doubleValue = 0
            let settings = analyzedSettings
            DispatchQueue.global(qos: .userInitiated).async { [self] in
                var successes = 0; var failures = 0; var cancelled = false
                do {
                    try FileManager.default.createDirectory(at: outputURL, withIntermediateDirectories: true)
                    for (position, item) in work.enumerated() {
                        try engine.checkCancellation()
                        DispatchQueue.main.async { self.statusLabel.stringValue = "Xuất & kiểm tra \(position + 1)/\(work.count): \(item.element.relative)" }
                        var result = item.element
                        do { result = try engine.export(item.element, to: outputURL.appendingPathComponent(item.element.relative), settings: settings); successes += 1 }
                        catch TrimError.cancelled { throw TrimError.cancelled }
                        catch { result.status = "Lỗi xuất · xem chi tiết"; result.error = error.localizedDescription; failures += 1 }
                        let completed = result
                        DispatchQueue.main.sync { self.tracks[item.offset] = completed; self.table.reloadData(); self.updateSummary(); self.progress.doubleValue = Double(position + 1) / Double(work.count) * 100 }
                    }
                } catch TrimError.cancelled { cancelled = true }
                catch { DispatchQueue.main.async { self.alert(error.localizedDescription) }; failures += 1 }
                var snapshot: [Track] = []; DispatchQueue.main.sync { snapshot = self.tracks }
                var reportError: String?
                do { _ = try TrimEngine.saveReport(snapshot, settings: settings, folder: outputURL) } catch { reportError = error.localizedDescription }
                let message = "\(cancelled ? "Đã dừng" : "Hoàn tất") · \(successes) file đã xuất · \(failures) lỗi" + (reportError.map { " · Không ghi được báo cáo: \($0)" } ?? " · Có báo cáo kiểm tra trong thư mục kết quả")
                DispatchQueue.main.async { self.finish(message) }
            }
        } catch { alert(error.localizedDescription) }
    }
    @objc func cancel() { engine?.cancel(); cancelButton.isEnabled = false; statusLabel.stringValue = "Đang dừng… File đã xuất vẫn được giữ lại." }
    @objc func reveal() { if let outputURL { NSWorkspace.shared.open(outputURL) } }
    @objc func about() { alert("SilenceTrim 2.0\nỨng dụng macOS xử lý nhạc trong máy.\nKhông tải nhạc lên mạng.\nFFmpeg: \(engine?.ffmpeg.path ?? "chưa tìm thấy")\n\nMP3/AAC/Opus: stream copy.\nWAV/FLAC/ALAC: cắt lossless, giữ mẫu âm thanh.\nFile hoàn toàn im lặng được sao chép nguyên trạng.") }
    func alert(_ text: String) { let alert = NSAlert(); alert.messageText = "SilenceTrim"; alert.informativeText = text; alert.addButton(withTitle: "OK"); alert.runModal() }
    func finish(_ message: String) { busy = false; statusLabel.stringValue = message; updateSummary(); refreshControls() }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply { engine?.cancel(); return .terminateNow }
    func windowShouldClose(_ sender: NSWindow) -> Bool { engine?.cancel(); return true }
    func numberOfRows(in tableView: NSTableView) -> Int { tracks.count }
    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
        guard row < tracks.count, let id = tableColumn?.identifier.rawValue else { return nil }; let track = tracks[row]
        if id == "selected" {
            let b = NSButton(checkboxWithTitle: "", target: self, action: #selector(toggleTrack(_:))); b.tag = row; b.state = track.selected ? .on : .off; b.isEnabled = !busy && track.error == nil && track.output == nil; return b
        }
        let text: String
        switch id { case "file": text = track.relative; case "duration": text = timeText(track.duration); case "head": text = seconds(track.cutStart); case "tail": text = seconds(track.cutEnd); default: text = track.status }
        let field = NSTextField(labelWithString: text); field.font = id == "file" ? .systemFont(ofSize: 12, weight: .medium) : .monospacedDigitSystemFont(ofSize: 11, weight: .regular)
        field.lineBreakMode = .byTruncatingMiddle; field.toolTip = id == "status" ? (track.error ?? track.status) : track.relative
        if id == "status" { field.textColor = track.error != nil ? .systemOrange : track.output != nil ? accent : .secondaryLabelColor }
        return field
    }
    @objc func toggleTrack(_ sender: NSButton) { guard !busy, tracks.indices.contains(sender.tag) else { return }; tracks[sender.tag].selected = sender.state == .on; refreshControls() }
    func tableViewSelectionDidChange(_ notification: Notification) {
        let row = table.selectedRow; guard tracks.indices.contains(row) else { return }; let t = tracks[row]
        if let error = t.error { detailLabel.stringValue = "\(t.relative) · \(error)" }
        else if t.allSilent { detailLabel.stringValue = "\(t.relative) · Toàn bộ bài dưới ngưỡng im lặng: sao chép nguyên trạng để tránh xoá nội dung. Thử hạ ngưỡng nếu bài rất nhỏ." }
        else {
            let check = t.verifiedLeading.map { " · Sau xuất: đầu \(seconds($0)), cuối \(seconds(t.verifiedTrailing ?? 0))" } ?? ""
            detailLabel.stringValue = "\(t.relative) · \(t.codec.uppercased()) · Im lặng gốc: đầu \(seconds(t.leading)), cuối \(seconds(t.trailing)) · \(t.lossless ? "Cắt chính xác lossless" : "Sao chép gói, không nén lại")\(check)"
        }
    }
}

func runCLI() -> Int32 {
    let args = CommandLine.arguments
    func value(_ flag: String) -> String? { guard let i = args.firstIndex(of: flag), i + 1 < args.count else { return nil }; return args[i + 1] }
    guard let input = value("--input"), let output = value("--output") else {
        print("Usage: SilenceTrim --batch --input FOLDER --output FOLDER [--threshold -60] [--padding 0.5] [--recursive]"); return 2
    }
    do {
        let engine = try TrimEngine(); var settings = TrimSettings()
        if let v = value("--threshold") { guard let n = Double(v) else { throw TrimError.message("Invalid threshold") }; settings.threshold = n }
        if let v = value("--padding") { guard let n = Double(v) else { throw TrimError.message("Invalid padding") }; settings.padding = n }
        settings.recursive = args.contains("--recursive"); try settings.validate()
        let source = TrimEngine.canonicalURL(URL(fileURLWithPath: input)); let destination = TrimEngine.canonicalURL(URL(fileURLWithPath: output))
        try TrimEngine.validateOutput(destination, input: source)
        let files = try engine.inventory(source, settings: settings, excluding: destination)
        guard !files.isEmpty else { throw TrimError.message("No supported audio files found.") }
        try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
        var tracks: [Track] = []; var failed = 0
        for file in files {
            let relative = try TrimEngine.relativePath(of: file, in: source); var track = Track(source: file.path, relative: relative)
            do { track = try engine.analyze(file, relative: relative, settings: settings); track = try engine.export(track, to: destination.appendingPathComponent(relative), settings: settings) }
            catch { track.error = error.localizedDescription; track.status = "Lỗi"; failed += 1 }
            tracks.append(track); print("\(relative): \(track.status)\(track.error.map { " — \($0)" } ?? "")")
        }
        print("Report: \(try TrimEngine.saveReport(tracks, settings: settings, folder: destination).path)")
        return failed == 0 ? 0 : 1
    } catch { print(error.localizedDescription); return 1 }
}
if CommandLine.arguments.contains("--batch") { exit(runCLI()) }
let application = NSApplication.shared
let delegate = AppDelegate(); application.delegate = delegate; application.setActivationPolicy(.regular); application.run()
