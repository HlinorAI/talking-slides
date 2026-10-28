// Transcriber.app — нативная обёртка пайплайна audio-transcriber.
// Современный macOS-интерфейс: вибранс-фон, скругления, SF Symbols,
// переключатели. Drag&drop аудио/видео, ссылка на видео → PDF/PPTX.

import AppKit

/// Локализация: ключи — английские тексты (регион разработки en),
/// переводы в en.lproj / ru.lproj. Язык берётся из настроек macOS.
func L(_ key: String) -> String { NSLocalizedString(key, comment: "") }
func LF(_ key: String, _ args: CVarArg...) -> String {
    String(format: L(key), locale: Locale.current, arguments: args)
}

let UI_LANG = (Locale.preferredLanguages.first ?? "en").hasPrefix("ru") ? "ru" : "en"

let envProjectDir = ProcessInfo.processInfo.environment["AUDIO_TRANSCRIBER_DIR"]
let PROJECT_DIR: String = {
    if let env = envProjectDir { return env }
    // рядом с бандлом (например, /Applications/../audio-transcriber) или в домашней папке
    let bundleParent = (Bundle.main.bundleURL.deletingLastPathComponent().path as NSString)
        .appendingPathComponent("audio-transcriber")
    let home = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("audio-transcriber").path
    for candidate in [bundleParent, home] {
        var isDir: ObjCBool = false
        if FileManager.default.fileExists(atPath: candidate + "/pipeline.py", isDirectory: &isDir) {
            return candidate
        }
    }
    return home
}()
let PYTHON = PROJECT_DIR + "/.venv/bin/python"
let PIPELINE = PROJECT_DIR + "/pipeline.py"

// Всё, что потенциально декодирует ffmpeg (точный ответ даёт probe в пайплайне):
// аудиоформаты + звуковые дорожки видео-контейнеров.
let AUDIO_EXTENSIONS: Set<String> = [
    "mp3", "m4a", "m4b", "m4r", "aac", "wav", "aiff", "aif", "aifc", "flac",
    "ogg", "oga", "opus", "wma", "asf", "amr", "caf", "ape", "wv", "tta",
    "ac3", "dts", "spx", "gsm", "au", "snd", "voc", "ra", "dsf", "dff", "mka",
    "mp4", "m4v", "mov", "mkv", "avi", "webm", "3gp", "3g2", "mpg", "mpeg",
    "m2ts", "ts", "wmv", "flv", "ogv",
]

// Языки ограничены латиницей и кириллицей — их покрывает Arial,
// которым рендерятся PDF/PPTX (арабский/иероглифы выпали бы квадратами).
enum Languages {
    static let options: [(code: String, name: String)] = [
        ("auto", "Авто (определить)"),
        ("ru", "Русский"),
        ("en", "English"),
        ("uk", "Українська"),
        ("kk", "Қазақша"),
        ("es", "Español"),
        ("de", "Deutsch"),
        ("fr", "Français"),
        ("it", "Italiano"),
        ("pt", "Português"),
        ("tr", "Türkçe"),
    ]

    static func name(_ code: String) -> String {
        guard let option = options.first(where: { $0.code == code }) else { return code }
        return displayName(option)
    }

    /// Названия языков — самоназвания (universal), но «авто» переводится.
    static func displayName(_ option: (code: String, name: String)) -> String {
        option.code == "auto" ? L("Auto (detect)") : option.name
    }
}

final class PipelineRunner {
    var onEvent: (([String: Any]) -> Void)?
    var onFinish: ((Bool) -> Void)?
    private(set) var process: Process?

    /// Синтетическая ошибка без запуска процесса: событие error + onFinish,
    /// чтобы интерфейс разблокировался.
    private func fail(_ message: String) {
        DispatchQueue.main.async { [weak self] in
            self?.onEvent?(["error": true, "message": message])
            self?.onFinish?(false)
        }
    }

    func run(input: String, formats: [String], lang: String) {
        guard FileManager.default.fileExists(atPath: PYTHON) else {
            fail(LF("Project python not found:\n%@\nRun ./install.sh in the project folder or set AUDIO_TRANSCRIBER_DIR.", PYTHON))
            return
        }
        guard FileManager.default.fileExists(atPath: PIPELINE) else {
            fail(LF("pipeline.py not found:\n%@\nSet AUDIO_TRANSCRIBER_DIR to the audio-transcriber project folder.", PIPELINE))
            return
        }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: PYTHON)
        p.arguments = [PIPELINE, input, "--formats", formats.joined(separator: ","),
                       "--lang", lang, "--ui-lang", UI_LANG]
        p.currentDirectoryURL = URL(fileURLWithPath: PROJECT_DIR)

        let errPipe = Pipe()
        p.standardError = errPipe

        let outPipe = Pipe()
        outPipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil }
        }
        p.standardOutput = outPipe

        // Финиш — только когда и процесс завершился, и stderr дочитан:
        // иначе последнее событие (done/outputs) может прийти после onFinish.
        var stderrEOF = false
        var exitCode: Int32?
        var finishSent = false
        let lock = NSLock()
        func maybeFinish() {
            lock.lock()
            defer { lock.unlock() }
            guard !finishSent, stderrEOF, let code = exitCode else { return }
            finishSent = true
            DispatchQueue.main.async { [weak self] in
                self?.onFinish?(code == 0)
            }
        }

        var buffer = Data()
        errPipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if data.isEmpty {
                handle.readabilityHandler = nil
                lock.lock(); stderrEOF = true; lock.unlock()
                maybeFinish()
                return
            }
            buffer.append(data)
            while let nl = buffer.firstIndex(of: 0x0A) {
                let lineData = buffer.subdata(in: buffer.startIndex..<nl)
                buffer.removeSubrange(buffer.startIndex...nl)
                guard !lineData.isEmpty,
                      let obj = try? JSONSerialization.jsonObject(with: lineData),
                      let dict = obj as? [String: Any] else { continue }
                DispatchQueue.main.async { [weak self] in
                    self?.onEvent?(dict)
                }
            }
        }

        p.terminationHandler = { process in
            lock.lock(); exitCode = process.terminationStatus; lock.unlock()
            maybeFinish()
        }

        process = p
        do {
            try p.run()
        } catch {
            fail(LF("Failed to launch python: %@", error.localizedDescription))
        }
    }

    func cancel() {
        process?.terminate()
    }
}

final class DropView: NSView {
    var onFile: ((URL) -> Void)?
    private let symbolView: NSImageView
    private let titleLabel: NSTextField
    private let captionLabel: NSTextField

    override init(frame frameRect: NSRect) {
        symbolView = NSImageView()
        titleLabel = NSTextField(labelWithString: L("Drop audio or video here"))
        captionLabel = NSTextField(labelWithString: L("any format · or paste a video link below"))
        super.init(frame: frameRect)
        wantsLayer = true
        layer?.cornerRadius = 16
        layer?.borderWidth = 1.5
        layer?.borderColor = NSColor.separatorColor.cgColor
        layer?.backgroundColor = NSColor.labelColor.withAlphaComponent(0.04).cgColor

        if let symbol = NSImage(systemSymbolName: "waveform", accessibilityDescription: nil)?
            .withSymbolConfiguration(.init(pointSize: 42, weight: .medium)) {
            symbolView.image = symbol
        }
        symbolView.contentTintColor = .secondaryLabelColor
        symbolView.translatesAutoresizingMaskIntoConstraints = false
        addSubview(symbolView)

        titleLabel.font = .systemFont(ofSize: 15, weight: .medium)
        titleLabel.textColor = .labelColor
        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        addSubview(titleLabel)

        captionLabel.font = .systemFont(ofSize: 12)
        captionLabel.textColor = .secondaryLabelColor
        captionLabel.translatesAutoresizingMaskIntoConstraints = false
        addSubview(captionLabel)

        NSLayoutConstraint.activate([
            symbolView.centerXAnchor.constraint(equalTo: centerXAnchor),
            symbolView.centerYAnchor.constraint(equalTo: centerYAnchor, constant: -30),
            titleLabel.centerXAnchor.constraint(equalTo: centerXAnchor),
            titleLabel.topAnchor.constraint(equalTo: symbolView.bottomAnchor, constant: 12),
            captionLabel.centerXAnchor.constraint(equalTo: centerXAnchor),
            captionLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 4),
        ])
        registerForDraggedTypes([.fileURL])
        setAccessibilityElement(true)
        setAccessibilityLabel(L("Drag & drop zone for audio or video"))
    }

    required init?(coder: NSCoder) { fatalError("unsupported") }

    private func firstAudioURL(_ draggingInfo: NSDraggingInfo) -> URL? {
        guard let urls = draggingInfo.draggingPasteboard.readObjects(
            forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]
        ) as? [URL] else { return nil }
        return urls.first { AUDIO_EXTENSIONS.contains($0.pathExtension.lowercased()) }
    }

    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation {
        let ok = firstAudioURL(sender) != nil
        layer?.backgroundColor = NSColor.controlAccentColor.withAlphaComponent(ok ? 0.14 : 0.0).cgColor
        layer?.borderColor = NSColor.controlAccentColor.withAlphaComponent(ok ? 0.8 : 0.3).cgColor
        return ok ? .copy : []
    }

    override func draggingExited(_ sender: NSDraggingInfo?) {
        layer?.backgroundColor = NSColor.labelColor.withAlphaComponent(0.04).cgColor
        layer?.borderColor = NSColor.separatorColor.cgColor
    }

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        draggingExited(nil)
        guard let url = firstAudioURL(sender) else { return false }
        onFile?(url)
        return true
    }
}

/// Плоская кнопка в современном стиле: скруглённая плашка без рамки.
final class FlatButton: NSButton {
    private let isAccent: Bool

    init(title: String, symbol: String? = nil, accent: Bool, action: Selector? = nil) {
        self.isAccent = accent
        super.init(frame: .zero)
        isBordered = false
        wantsLayer = true
        layer?.cornerRadius = 10

        // только attributedTitle: задание ещё и plain title даёт двоение текста
        attributedTitle = NSAttributedString(
            string: title,
            attributes: [
                .font: NSFont.systemFont(ofSize: 13, weight: .semibold),
                .foregroundColor: accent ? NSColor.white : NSColor.labelColor,
            ]
        )

        setAccessibilityLabel(title)
        if let action { self.action = action }
    }

    required init?(coder: NSCoder) { fatalError("unsupported") }

    override func draw(_ dirtyRect: NSRect) {
        layer?.backgroundColor = (isEnabled
            ? (isAccent ? NSColor.controlAccentColor
                        : NSColor.labelColor.withAlphaComponent(0.08))
            : NSColor.labelColor.withAlphaComponent(0.04)).cgColor
        super.draw(dirtyRect)
    }
}

final class ViewController: NSViewController {
    private static let stageNames = [
        "download": "stage.download",
        "transcribe": "stage.transcribe",
        "slides": "stage.slides",
        "render": "stage.render",
        "theme": "stage.theme",
        "fragments": "stage.fragments",
    ]

    private let runner = PipelineRunner()
    private var dropView: DropView!
    private var statusLabel: NSTextField!
    private var progress: NSProgressIndicator!
    private var pdfSwitch: NSSwitch!
    private var pptxSwitch: NSSwitch!
    private var htmlSwitch: NSSwitch!
    private var cancelButton: FlatButton!
    private var chooseButton: FlatButton!
    private var urlField: NSTextField!
    private var downloadButton: FlatButton!
    private var langPopup: NSPopUpButton!
    private var openButtons: [NSButton] = []
    private var outputURLs: [URL] = []

    private var isRunning = false
    private var sawDone = false
    private var sawError = false
    private var cancelled = false

    override func loadView() {
        let view = NSView(frame: NSRect(x: 0, y: 0, width: 620, height: 500))
        view.wantsLayer = true

        let effect = NSVisualEffectView(frame: view.bounds)
        effect.material = .windowBackground
        effect.blendingMode = .behindWindow
        effect.state = .active
        effect.autoresizingMask = [.width, .height]
        view.addSubview(effect)

        dropView = DropView(frame: NSRect(x: 24, y: 246, width: 572, height: 212))
        dropView.autoresizingMask = [.width]
        dropView.onFile = { [weak self] url in self?.start(input: url.path) }
        view.addSubview(dropView)

        chooseButton = FlatButton(title: L("Choose File"), accent: false,
                                  action: #selector(chooseFile))
        chooseButton.target = self
        chooseButton.frame = NSRect(x: 24, y: 202, width: 572, height: 34)
        view.addSubview(chooseButton)

        urlField = NSTextField(string: "")
        urlField.placeholderString = L("Video link (YouTube, VK, …)")
        urlField.frame = NSRect(x: 24, y: 160, width: 400, height: 34)
        urlField.focusRingType = .none
        urlField.target = self
        urlField.action = #selector(startFromUrl)
        urlField.setAccessibilityLabel(L("Video link"))
        view.addSubview(urlField)

        downloadButton = FlatButton(title: L("Download and Process"), accent: true,
                                    action: #selector(startFromUrl))
        downloadButton.target = self
        downloadButton.frame = NSRect(x: 436, y: 160, width: 160, height: 34)
        view.addSubview(downloadButton)

        @discardableResult
        func rowLabel(_ text: String, x: CGFloat) -> NSTextField {
            let l = NSTextField(labelWithString: text)
            l.font = .systemFont(ofSize: 13)
            l.textColor = .secondaryLabelColor
            l.frame = NSRect(x: x, y: 126, width: 44, height: 18)
            view.addSubview(l)
            return l
        }
        rowLabel("PDF", x: 24).frame.size.width = 34
        pdfSwitch = NSSwitch()
        pdfSwitch.state = .on
        pdfSwitch.controlSize = .small
        pdfSwitch.frame = NSRect(x: 58, y: 122, width: 40, height: 22)
        pdfSwitch.setAccessibilityLabel(L("Export to PDF"))
        view.addSubview(pdfSwitch)

        rowLabel("PPTX", x: 106)
        pptxSwitch = NSSwitch()
        pptxSwitch.state = .on
        pptxSwitch.controlSize = .small
        pptxSwitch.frame = NSRect(x: 156, y: 122, width: 40, height: 22)
        pptxSwitch.setAccessibilityLabel(L("Export to PPTX"))
        view.addSubview(pptxSwitch)

        rowLabel("HTML", x: 204)
        htmlSwitch = NSSwitch()
        htmlSwitch.state = .off
        htmlSwitch.controlSize = .small
        htmlSwitch.frame = NSRect(x: 254, y: 122, width: 40, height: 22)
        htmlSwitch.setAccessibilityLabel(L("HTML player"))
        view.addSubview(htmlSwitch)

        rowLabel(L("Language"), x: 298).frame.size.width = 64
        langPopup = NSPopUpButton(frame: NSRect(x: 366, y: 118, width: 230, height: 28))
        for option in Languages.options {
            langPopup.addItem(withTitle: Languages.displayName(option))
        }
        langPopup.selectItem(at: 0)
        langPopup.setAccessibilityLabel(L("Presentation language"))
        view.addSubview(langPopup)

        progress = NSProgressIndicator(frame: NSRect(x: 24, y: 82, width: 416, height: 18))
        progress.isIndeterminate = false
        progress.minValue = 0
        progress.maxValue = 1
        progress.isHidden = true
        view.addSubview(progress)

        cancelButton = FlatButton(title: L("Cancel"), accent: false,
                                  action: #selector(cancelRun))
        cancelButton.target = self
        cancelButton.frame = NSRect(x: 452, y: 80, width: 144, height: 28)
        cancelButton.isHidden = true
        view.addSubview(cancelButton)

        statusLabel = NSTextField(wrappingLabelWithString: L("Ready"))
        statusLabel.frame = NSRect(x: 24, y: 20, width: 572, height: 52)
        statusLabel.font = .systemFont(ofSize: 12)
        statusLabel.textColor = .secondaryLabelColor
        view.addSubview(statusLabel)

        runner.onEvent = { [weak self] event in self?.handleEvent(event) }
        runner.onFinish = { [weak self] ok in self?.handleFinish(ok: ok) }

        self.view = view
    }

    @objc private func startFromUrl() {
        let raw = urlField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        let low = raw.lowercased()
        guard !low.isEmpty else {
            setStatus(L("Enter a video link"), color: .systemOrange)
            return
        }
        guard low.hasPrefix("http://") || low.hasPrefix("https://") else {
            setStatus(L("Link must start with http:// or https://"), color: .systemOrange)
            return
        }
        start(input: raw)
    }

    @objc private func chooseFile() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.beginSheetModal(for: view.window!) { [weak self] response in
            guard response == .OK, let url = panel.url, let self else { return }
            if AUDIO_EXTENSIONS.contains(url.pathExtension.lowercased()) {
                self.start(input: url.path)
            } else {
                self.setStatus(LF("Unsupported file: %@", url.lastPathComponent), color: .systemOrange)
            }
        }
    }

    private func start(input: String) {
        guard !isRunning else { return }
        var formats: [String] = []
        if pdfSwitch.state == .on { formats.append("pdf") }
        if pptxSwitch.state == .on { formats.append("pptx") }
        if htmlSwitch.state == .on { formats.append("html") }
        if formats.isEmpty {
            setStatus(L("Turn on at least one output format"), color: .systemOrange)
            return
        }
        isRunning = true
        sawDone = false
        sawError = false
        cancelled = false
        outputURLs = []
        openButtons.forEach { $0.removeFromSuperview() }
        openButtons = []
        let isUrl = input.lowercased().hasPrefix("http")
        setStatus(isUrl ? L("Downloading video…")
                        : LF("Transcribing: %@", (input as NSString).lastPathComponent),
                  color: .secondaryLabelColor)
        progress.doubleValue = 0
        progress.isIndeterminate = false
        progress.isHidden = false
        cancelButton.isHidden = false
        chooseButton.isEnabled = false
        downloadButton.isEnabled = false
        let lang = Languages.options[langPopup.indexOfSelectedItem].code
        runner.run(input: input, formats: formats, lang: lang)
    }

    private func handleEvent(_ event: [String: Any]) {
        if event["error"] != nil {
            sawError = true
            finishUI()
            let message = event["message"] as? String ?? L("unknown error")
            setStatus(LF("Error: %@", message), color: .systemRed)
            return
        }
        if let detected = event["detected_lang"] as? String {
            let p = event["p_lang"] as? Double ?? 0
            let pct = Int(p * 100)
            let conf = pct > 0 ? LF(" (%ld%%)", pct) : ""
            setStatus(LF("Detected language: %@", Languages.name(detected) + conf),
                      color: .secondaryLabelColor)
            return
        }
        if let pct = event["pct"] as? Double {
            progress.isIndeterminate = false
            progress.doubleValue = pct
            let stage = event["stage"] as? String
            let label = stage.flatMap { L(Self.stageNames[$0] ?? $0) } ?? L("Processing")
            setStatus(LF("Progress: %@ of %ld%%", label, Int(pct * 100)),
                      color: .secondaryLabelColor)
            return
        }
        if let stage = event["stage"] as? String {
            if stage != "transcribe" && stage != "download" {
                progress.isIndeterminate = true
                progress.startAnimation(nil)
            }
            setStatus(L(Self.stageNames[stage] ?? stage) + "…", color: .secondaryLabelColor)
            return
        }
        if event["done"] != nil {
            sawDone = true
            let slides = event["slides"] as? Int ?? 0
            let paths = event["outputs"] as? [String] ?? []
            outputURLs = paths.map { URL(fileURLWithPath: $0) }
            finishUI()
            let dir = outputURLs.first?.deletingLastPathComponent().path ?? ""
            let key: String
            if UI_LANG == "ru" {
                if slides % 10 == 1 && slides % 100 != 11 { key = "Done: %ld slide → %@" }
                else if (2...4).contains(slides % 10)
                        && !(12...14).contains(slides % 100) { key = "Done: %ld few slides → %@" }
                else { key = "Done: %ld slides → %@" }
            } else {
                key = slides == 1 ? "Done: %ld slide → %@" : "Done: %ld slides → %@"
            }
            setStatus(LF(key, slides, dir), color: .systemGreen)
            addOpenButtons()
        }
    }

    private func handleFinish(ok: Bool) {
        finishUI()
        if ok && !sawDone {
            setStatus(L("Error: process exited without a result"), color: .systemRed)
        } else if !ok && !sawDone && !sawError {
            setStatus(cancelled ? L("Cancelled") : L("Error: process exited with an error"),
                      color: cancelled ? .secondaryLabelColor : .systemRed)
        }
        isRunning = false
    }

    private func addOpenButtons() {
        // Максимум 4 кнопки (PDF/PPTX/HTML + папка) по 140pt — гарантированно
        // влезают в окно 620pt. TXT и chapters.txt открываются через папку.
        let dir = outputURLs.first?.deletingLastPathComponent().path ?? ""
        var items: [(title: String, path: String)] = []
        for url in outputURLs {
            switch url.pathExtension.lowercased() {
            case "pdf": items.append((L("Open PDF"), url.path))
            case "pptx": items.append((L("Open PPTX"), url.path))
            case "html": items.append((L("Open in Browser"), url.path))
            default: break
            }
        }
        items.append((L("Open Folder"), dir))
        var x: CGFloat = 24
        for item in items.prefix(4) {
            let b = FlatButton(title: item.title, accent: false,
                               action: #selector(openOutput(_:)))
            b.target = self
            b.frame = NSRect(x: x, y: 80, width: 140, height: 30)
            b.identifier = NSUserInterfaceItemIdentifier(item.path)
            b.setAccessibilityLabel(item.title)
            view.addSubview(b)
            openButtons.append(b)
            x += 150
        }
    }

    @objc private func openOutput(_ sender: NSButton) {
        guard let path = sender.identifier?.rawValue else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }

    @objc private func cancelRun() {
        cancelled = true
        runner.cancel()
    }

    private func finishUI() {
        progress.stopAnimation(nil)
        progress.isHidden = true
        cancelButton.isHidden = true
        chooseButton.isEnabled = true
        downloadButton.isEnabled = true
    }

    private func setStatus(_ text: String, color: NSColor) {
        statusLabel.stringValue = text
        statusLabel.textColor = color
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 620, height: 500),
            styleMask: [.titled, .closable, .miniaturizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "Audio Transcriber"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.isMovableByWindowBackground = true
        window.isOpaque = false
        window.backgroundColor = .clear
        window.contentViewController = ViewController()
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        self.window = window
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)

let mainMenu = NSMenu()
let appMenuItem = NSMenuItem()
mainMenu.addItem(appMenuItem)
let appMenu = NSMenu()
appMenu.addItem(NSMenuItem(title: L("About Audio Transcriber"), action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: ""))
appMenu.addItem(.separator())
appMenu.addItem(NSMenuItem(title: L("Quit Audio Transcriber"), action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
appMenuItem.submenu = appMenu
app.mainMenu = mainMenu

app.run()
