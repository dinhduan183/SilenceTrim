from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import math
import sys

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import VERSION
from .updates import API_URL, DOWNLOAD_URL, newer_tag
from .engine import (Cancelled, Engine, Settings, Track, TrimError, canonical,
                     relative_path, save_report, unique_output, validate_output)


STYLE = """
QWidget { background: #0e1724; color: #edf3f8; font-family: 'Segoe UI'; font-size: 13px; }
QLabel#eyebrow { color: #40d7be; font-size: 11px; font-weight: 600; }
QLabel#title { font-size: 30px; font-weight: 700; }
QLabel#muted { color: #9eafc2; }
QLabel#summary { color: #40d7be; font-size: 12px; font-weight: 600; }
QFrame#card { background: #162334; border: 1px solid #25384c; border-radius: 12px; }
QFrame#card QLabel { background: transparent; }
QFrame#updateBanner { background: #173936; border: 1px solid #40d7be; border-radius: 10px; }
QFrame#updateBanner QLabel { background: transparent; color: #69e4d0; }
QPushButton { background: #24374b; border: 1px solid #36506a; border-radius: 7px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #304963; }
QPushButton:disabled { background: #182533; color: #617388; border-color: #253448; }
QPushButton#primary { background: #40d7be; color: #0b2426; border: none; }
QPushButton#primary:hover { background: #69e4d0; }
QPushButton#primary:disabled { background: #234c4d; color: #759b9b; }
QComboBox, QLineEdit { background: #162334; border: 1px solid #36506a; border-radius: 5px; padding: 7px; }
QComboBox:disabled, QLineEdit:disabled { color: #617388; }
QComboBox QAbstractItemView { background: #24374b; selection-background-color: #36506a; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #59718a; border-radius: 3px; background: #162334; }
QCheckBox::indicator:checked { background: #40d7be; }
QTableWidget { background: #121f30; alternate-background-color: #172639; border: 1px solid #25384c; border-radius: 8px; gridline-color: #25384c; selection-background-color: #284b5c; }
QHeaderView::section { background: #1d3044; color: #b8c9d9; padding: 10px; border: none; font-weight: 600; }
QTableWidget::item { padding: 8px; }
QTableWidget::indicator { width: 16px; height: 16px; }
QProgressBar { border: none; background: #223448; border-radius: 4px; height: 7px; }
QProgressBar::chunk { background: #40d7be; border-radius: 4px; }
QScrollBar:vertical { width: 12px; background: #142234; }
QScrollBar::handle:vertical { background: #36506a; min-height: 20px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""


def icon_path():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / "AppIcon.png"
    return Path(__file__).resolve().parents[2] / "source" / "AppIcon.png"


class Worker(QThread):
    track_ready = Signal(int, object)
    progress = Signal(int, str)
    result = Signal(str)

    def __init__(self, engine, mode, source, output, settings, tracks, parent=None):
        super().__init__(parent)
        self.engine, self.mode = engine, mode
        self.source, self.output, self.settings = source, output, settings
        self.tracks = [replace(track) for track in tracks]

    def run(self):
        if self.mode == "analyze":
            try:
                files = self.engine.inventory(self.source, self.settings, self.output)
                if not files:
                    raise TrimError("Không tìm thấy MP3, M4A, AAC, WAV, FLAC, AIFF, OGG hoặc Opus.")
                for index, file in enumerate(files):
                    self.engine.check_cancelled()
                    relative = relative_path(file, self.source)
                    self.progress.emit(round(index / len(files) * 100), f"Phân tích {index + 1}/{len(files)}: {relative}")
                    try:
                        track = self.engine.analyze(file, relative, self.settings)
                    except Cancelled:
                        raise
                    except Exception as error:
                        track = Track(str(file), relative, selected=False, status="Lỗi phân tích", error=str(error))
                    self.track_ready.emit(index, track)
                    self.progress.emit(round((index + 1) / len(files) * 100), f"Đã phân tích {index + 1}/{len(files)} bài")
                self.result.emit("Phân tích xong · Xem mức cắt, bỏ chọn bài muốn giữ, rồi nhấn Cắt & xuất")
            except Exception as error:
                self.result.emit(str(error))
            return
        successes, failures, cancelled = 0, 0, False
        work = [(i, track) for i, track in enumerate(self.tracks) if track.selected and not track.error and not track.output]
        try:
            self.output.mkdir(parents=True, exist_ok=True)
            for position, (index, track) in enumerate(work):
                self.engine.check_cancelled()
                self.progress.emit(round(position / len(work) * 100), f"Xuất & kiểm tra {position + 1}/{len(work)}: {track.relative}")
                try:
                    track = self.engine.export(track, self.output / track.relative, self.settings)
                    successes += 1
                except Cancelled:
                    raise
                except Exception as error:
                    track = replace(track, status="Lỗi xuất · xem chi tiết", error=str(error))
                    failures += 1
                self.tracks[index] = track
                self.track_ready.emit(index, track)
                self.progress.emit(round((position + 1) / len(work) * 100), f"Đã xử lý {position + 1}/{len(work)} bài")
        except Cancelled:
            cancelled = True
        except Exception as error:
            failures += 1
            self.progress.emit(0, str(error))
        try:
            save_report(self.tracks, self.settings, self.output)
            report_note = "Có báo cáo trong thư mục kết quả"
        except Exception as error:
            report_note = f"Không ghi được báo cáo: {error}"
        self.result.emit(f"{'Đã dừng' if cancelled else 'Hoàn tất'} · {successes} file đã xuất · {failures} lỗi · {report_note}")


class Window(QMainWindow):
    def __init__(self, check_updates=True):
        super().__init__()
        self.setWindowTitle(f"SilenceTrim v{VERSION}")
        self.setWindowIcon(QIcon(str(icon_path())))
        self.resize(1100, 780)
        self.setMinimumSize(940, 690)
        self.setAcceptDrops(True)
        self.source = self.output = None
        self.tracks = []
        self.analyzed_settings = None
        self.worker = None
        self.busy = False
        self.closing = False
        self.warning_seconds = 5.0
        self.warning_valid = True
        self.engine = None
        self.update_tag = self.dismissed_update_tag = None
        self.update_reply = None
        self.update_network = QNetworkAccessManager(self)
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(3600 * 1000)
        self.update_timer.timeout.connect(self.check_for_updates)
        self.update_start_timer = QTimer(self)
        self.update_start_timer.setSingleShot(True)
        self.update_start_timer.timeout.connect(self.check_for_updates)
        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(16)
        hero = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(str(icon_path())).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        hero.addWidget(logo)
        headings = QVBoxLayout()
        headings.setSpacing(5)
        headings.addWidget(self.label("BATCH AUDIO • LOSSLESS TRIM", "eyebrow"))
        headings.addWidget(self.label("Gọn hai đầu. Giữ chất lượng.", "title"))
        headings.addWidget(self.label("Cắt khoảng im lặng đầu và cuối hàng loạt, giữ lại tối đa 0,5 giây mỗi phía.", "muted"))
        hero.addLayout(headings, 1)
        layout.addLayout(hero)
        self.update_banner = QFrame()
        self.update_banner.setObjectName("updateBanner")
        update_row = QHBoxLayout(self.update_banner)
        update_row.setContentsMargins(16, 10, 16, 10)
        self.update_label = self.label("")
        self.update_label.setWordWrap(True)
        update_row.addWidget(self.update_label, 1)
        self.update_download = self.button("Xem & tải bản mới", self.open_release)
        update_row.addWidget(self.update_download)
        self.update_dismiss = self.button("Ẩn", self.dismiss_update)
        update_row.addWidget(self.update_dismiss)
        self.update_banner.hide()
        layout.addWidget(self.update_banner)
        card = QFrame()
        card.setObjectName("card")
        paths = QVBoxLayout(card)
        paths.setContentsMargins(16, 14, 16, 14)
        self.source_label = self.label("Chọn hoặc kéo thư mục nhạc vào cửa sổ")
        self.output_label = self.label("Tự tạo thư mục xuất bên cạnh thư mục gốc", "muted")
        self.choose_source = self.button("Chọn thư mục…", self.pick_source)
        self.choose_output = self.button("Đổi nơi xuất…", self.pick_output)
        for name, text, button in [("NGUỒN", self.source_label, self.choose_source), ("XUẤT", self.output_label, self.choose_output)]:
            row = QHBoxLayout()
            heading = self.label(name, "eyebrow")
            heading.setFixedWidth(58)
            row.addWidget(heading)
            row.addWidget(text, 1)
            row.addWidget(button)
            paths.addLayout(row)
        layout.addWidget(card)
        settings = QHBoxLayout()
        self.threshold = QComboBox()
        for text, value in [("−60 dB · mặc định", -60), ("−70 dB · giữ âm rất nhỏ", -70),
                            ("−80 dB · gần im lặng tuyệt đối", -80), ("−50 dB · nhạy hơn", -50), ("−40 dB · rất nhạy", -40)]:
            self.threshold.addItem(text, value)
        self.padding = QLineEdit("0.5")
        self.padding.setFixedWidth(70)
        self.recursive = QCheckBox("Gồm thư mục con")
        settings.addWidget(self.label("Ngưỡng im lặng"))
        settings.addWidget(self.threshold)
        settings.addSpacing(14)
        settings.addWidget(self.label("Giữ tối đa"))
        settings.addWidget(self.padding)
        settings.addWidget(self.label("giây / phía"))
        settings.addStretch()
        settings.addWidget(self.recursive)
        layout.addLayout(settings)
        warning_row = QHBoxLayout()
        warning_row.addWidget(self.label("Cảnh báo im lặng dài hơn"))
        self.warning_preset = QComboBox()
        for text, value in [("5 giây · mặc định", 5.0), ("10 giây", 10.0), ("Tự nhập…", None)]:
            self.warning_preset.addItem(text, value)
        warning_row.addWidget(self.warning_preset)
        self.warning_custom = QLineEdit("5")
        self.warning_custom.setFixedWidth(80)
        self.warning_custom.setPlaceholderText("Số giây")
        self.warning_custom.hide()
        warning_row.addWidget(self.warning_custom)
        self.warning_note = self.label("Tô đỏ nếu đầu hoặc cuối vượt ngưỡng. Hãy kiểm tra trước khi cắt.", "muted")
        self.warning_note.setWordWrap(True)
        warning_row.addWidget(self.warning_note, 1)
        layout.addLayout(warning_row)
        note = self.label("MP3/AAC/OGG/Opus: sao chép gói âm thanh, không nén lại. WAV/FLAC/ALAC: giữ nguyên mẫu âm thanh. Khoảng nghỉ giữa bài được giữ nguyên.", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.summary = self.label("CHƯA CÓ BÀI NHẠC", "summary")
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 6)
        self.table.setMinimumHeight(180)
        self.table.setHorizontalHeaderLabels(["Xuất", "Bài nhạc", "Độ dài", "Cắt đầu", "Cắt cuối", "Trạng thái"])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 260)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemChanged.connect(self.selection_changed)
        layout.addWidget(self.table, 1)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        actions = QHBoxLayout()
        self.analyze_button = self.button("1. Phân tích", lambda: self.start("analyze"))
        self.trim_button = self.button("2. Cắt & xuất", lambda: self.start("export"))
        self.trim_button.setObjectName("primary")
        self.cancel_button = self.button("Dừng", self.cancel)
        self.reveal_button = self.button("Mở kết quả", self.reveal)
        actions.addWidget(self.analyze_button)
        actions.addWidget(self.trim_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.reveal_button)
        layout.addLayout(actions)
        self.status = self.label("Sẵn sàng · File gốc luôn được giữ nguyên", "muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.threshold.currentIndexChanged.connect(self.invalidate)
        self.padding.textChanged.connect(self.invalidate)
        self.recursive.toggled.connect(self.invalidate)
        self.warning_preset.currentIndexChanged.connect(self.warning_changed)
        self.warning_custom.textChanged.connect(self.warning_changed)
        about = self.menuBar().addMenu("SilenceTrim")
        about.addAction("Về SilenceTrim", self.about)
        about.addAction("Thoát", self.close)
        try:
            self.engine = Engine()
        except TrimError as error:
            self.status.setText(str(error))
        self.refresh()
        self.fit_update_layout()
        if check_updates:
            self.update_start_timer.start(0)
            self.update_timer.start()

    def check_for_updates(self):
        if self.update_reply is not None:
            return
        request = QNetworkRequest(QUrl(API_URL))
        request.setTransferTimeout(10000)
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", f"SilenceTrim/{VERSION}".encode("ascii"))
        self.update_reply = self.update_network.get(request)
        self.update_reply.finished.connect(self.update_check_finished)

    def update_check_finished(self):
        reply = self.update_reply
        self.update_reply = None
        if reply is None:
            return
        if reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 200:
            self.show_update(newer_tag(bytes(reply.readAll())))
        reply.deleteLater()

    def show_update(self, tag):
        if tag is None or tag == self.dismissed_update_tag:
            return
        self.update_tag = tag
        self.update_label.setText(f"Có phiên bản mới {tag}. Bạn đang dùng v{VERSION}.")
        self.update_banner.show()
        self.fit_update_layout()

    def fit_update_layout(self):
        minimum = self.centralWidget().layout().minimumSize().height() + self.menuBar().sizeHint().height()
        self.setMinimumHeight(max(690, minimum))

    def open_release(self):
        QDesktopServices.openUrl(QUrl(DOWNLOAD_URL))

    def dismiss_update(self):
        self.dismissed_update_tag = self.update_tag
        self.update_banner.hide()
        self.fit_update_layout()

    @staticmethod
    def label(text, name=""):
        label = QLabel(text)
        label.setObjectName(name)
        return label

    @staticmethod
    def button(text, callback):
        button = QPushButton(text)
        button.clicked.connect(callback)
        return button

    def settings(self):
        if not self.warning_valid:
            raise TrimError("Ngưỡng cảnh báo phải là số giây hữu hạn lớn hơn 0.")
        try:
            padding = float(self.padding.text().replace(",", "."))
        except ValueError as error:
            raise TrimError("Khoảng giữ lại phải là số, ví dụ 0.5.") from error
        settings = Settings(self.threshold.currentData(), padding, self.recursive.isChecked())
        settings.validate()
        return settings

    def set_source(self, path):
        if self.busy:
            return
        self.source = canonical(path)
        self.output = unique_output(self.source)
        self.source_label.setText(str(self.source))
        self.source_label.setToolTip(str(self.source))
        self.output_label.setText(str(self.output))
        self.output_label.setToolTip(str(self.output))
        self.invalidate()
        if self.engine:
            self.status.setText("Đã chọn thư mục · Nhấn Phân tích để xem trước")

    def pick_source(self):
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục nhạc")
        if path:
            self.set_source(path)

    def pick_output(self):
        path = QFileDialog.getExistingDirectory(self, "Chọn nơi xuất", str(self.output.parent))
        if path:
            try:
                output = canonical(path)
                validate_output(output, self.source)
                self.output = output
                self.output_label.setText(str(output))
                self.output_label.setToolTip(str(output))
                self.invalidate()
            except Exception as error:
                self.alert(str(error))

    def invalidate(self, *_):
        if self.busy:
            return
        self.tracks = []
        self.analyzed_settings = None
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.refresh()

    def refresh(self):
        for control in (self.choose_source, self.threshold, self.padding, self.recursive, self.warning_preset, self.warning_custom):
            control.setEnabled(not self.busy)
        self.choose_output.setEnabled(not self.busy and self.source is not None)
        self.analyze_button.setEnabled(not self.busy and self.warning_valid and self.source is not None and self.engine is not None)
        self.trim_button.setEnabled(not self.busy and self.warning_valid and any(t.selected and not t.error and not t.output for t in self.tracks))
        self.cancel_button.setEnabled(self.busy)
        self.reveal_button.setEnabled(not self.busy and self.output is not None and self.output.exists())
        self.table.setEnabled(not self.busy)
        cut = [t for t in self.tracks if not t.error and t.cutStart + t.cutEnd > 0]
        self.summary.setText(f"{len(self.tracks)} BÀI  •  {len(cut)} CẦN CẮT  •  {sum(t.cutStart + t.cutEnd for t in cut):.2f} s CÓ THỂ BỎ  •  {sum(t.output is not None for t in self.tracks)} ĐÃ XUẤT" if self.tracks else "CHƯA CÓ BÀI NHẠC")
        warnings = sum(t.has_unusual_silence(self.warning_seconds) for t in self.tracks)
        if warnings:
            self.summary.setText(f"⚠ {warnings} BÀI CẦN KIỂM TRA  •  " + self.summary.text())

    def warning_changed(self, *_):
        custom = self.warning_preset.currentData() is None
        self.warning_custom.setVisible(custom)
        try:
            value = float(self.warning_custom.text().replace(",", ".")) if custom else self.warning_preset.currentData()
            self.warning_valid = math.isfinite(value) and value > 0
        except ValueError:
            self.warning_valid = False
        if self.warning_valid:
            self.warning_seconds = value
            self.warning_note.setText("Tô đỏ nếu đầu hoặc cuối vượt ngưỡng. Hãy kiểm tra trước khi cắt.")
            self.warning_note.setStyleSheet("")
            for index, track in enumerate(self.tracks):
                self.update_track(index, track, refresh=False)
        else:
            self.warning_note.setText("Ngưỡng cảnh báo phải là số giây hữu hạn lớn hơn 0.")
            self.warning_note.setStyleSheet("color: #ff7373;")
        self.refresh()

    def warning_text(self, track):
        if not track.has_unusual_silence(self.warning_seconds):
            return ""
        return (f"Im lặng dài bất thường: đầu {track.leading:.2f} s, cuối {track.trailing:.2f} s "
                f"(ngưỡng {self.warning_seconds:g} s). Hãy kiểm tra bài này trước khi cắt.")

    def start(self, mode):
        if self.busy or self.engine is None:
            return
        try:
            settings = self.settings()
            validate_output(self.output, self.source)
            if mode == "analyze":
                self.invalidate()
                self.analyzed_settings = settings
            elif settings != self.analyzed_settings:
                self.invalidate()
                raise TrimError("Thiết lập đã thay đổi. Hãy phân tích lại trước khi xuất.")
            self.busy = True
            self.engine.reset()
            self.progress.setValue(0)
            self.worker = Worker(self.engine, mode, self.source, self.output, settings, self.tracks, self)
            self.worker.track_ready.connect(self.update_track)
            self.worker.progress.connect(self.update_progress)
            self.worker.result.connect(self.status.setText)
            self.worker.finished.connect(self.finished)
            self.refresh()
            self.worker.start()
        except Exception as error:
            self.alert(str(error))

    def update_progress(self, value, message):
        self.progress.setValue(value)
        self.status.setText(message)

    def update_track(self, index, track, refresh=True):
        if index == len(self.tracks):
            self.tracks.append(track)
            self.table.insertRow(index)
        else:
            self.tracks[index] = track
        self.table.blockSignals(True)
        checkbox = QTableWidgetItem()
        checkbox.setFlags(Qt.ItemIsEnabled | (Qt.ItemIsUserCheckable if not track.error and not track.output else Qt.NoItemFlags))
        checkbox.setCheckState(Qt.Checked if track.selected else Qt.Unchecked)
        self.table.setItem(index, 0, checkbox)
        values = [track.relative, f"{int(track.duration) // 60}:{track.duration % 60:05.2f}",
                  f"{track.cutStart:.2f} s", f"{track.cutEnd:.2f} s", track.status]
        warning = self.warning_text(track)
        if warning:
            values[-1] += " · ⚠ Im lặng dài bất thường · hãy kiểm tra"
            checkbox.setBackground(QColor("#40232e"))
        for column, value in enumerate(values, 1):
            item = QTableWidgetItem(value)
            tooltip = (track.error or value) if column == 5 else track.relative
            item.setToolTip(tooltip + (f"\n{warning}" if warning else ""))
            if warning:
                item.setForeground(QColor("#ff7373"))
                item.setBackground(QColor("#40232e"))
            self.table.setItem(index, column, item)
        self.table.blockSignals(False)
        if refresh:
            self.refresh()

    def selection_changed(self, item):
        if not self.busy and item.column() == 0:
            self.tracks[item.row()].selected = item.checkState() == Qt.Checked
            self.refresh()

    def cancel(self):
        self.engine.cancel()
        self.cancel_button.setEnabled(False)
        self.status.setText("Đang dừng… File đã xuất vẫn được giữ lại.")

    def finished(self):
        self.busy = False
        self.worker.deleteLater()
        self.worker = None
        self.refresh()
        if self.closing:
            self.close()

    def reveal(self):
        if self.output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output)))

    def alert(self, text):
        QMessageBox.information(self, "SilenceTrim", text)

    def about(self):
        self.alert(f"SilenceTrim v{VERSION}\nXử lý trực tiếp trên máy. Không tải nhạc lên mạng.\n"
                   f"FFmpeg: {self.engine.ffmpeg if self.engine else 'chưa tìm thấy'}\n"
                   "MP3/AAC/OGG/Opus: stream copy. WAV/FLAC/ALAC: lossless.\nFile hoàn toàn im lặng được sao chép nguyên trạng.")

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls() and any(Path(url.toLocalFile()).is_dir() for url in event.mimeData().urls() if url.isLocalFile()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.busy:
            for url in event.mimeData().urls():
                if url.isLocalFile() and Path(url.toLocalFile()).is_dir():
                    self.set_source(url.toLocalFile())
                    event.acceptProposedAction()
                    break

    def closeEvent(self, event):
        if self.busy:
            self.closing = True
            self.cancel()
            event.ignore()
        else:
            self.update_timer.stop()
            self.update_start_timer.stop()
            if self.update_reply is not None:
                self.update_reply.abort()
            event.accept()


def run():
    application = QApplication(sys.argv)
    application.setApplicationName("SilenceTrim")
    application.setApplicationVersion(VERSION)
    application.setStyle("Fusion")
    application.setStyleSheet(STYLE)
    window = Window(check_updates="--smoke-test" not in sys.argv)
    if "--folder" in sys.argv:
        index = sys.argv.index("--folder")
        if index + 1 < len(sys.argv) and Path(sys.argv[index + 1]).is_dir():
            window.set_source(sys.argv[index + 1])
    window.show()
    if "--smoke-test" in sys.argv:
        if window.windowIcon().isNull() or window.engine is None:
            raise RuntimeError("Packaged app is missing its icon or cannot find FFmpeg")
        QTimer.singleShot(100, application.quit)
    return application.exec()
