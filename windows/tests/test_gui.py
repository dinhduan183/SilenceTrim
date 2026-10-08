"""Offscreen GUI checks, including the threaded analyze/export workflow."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from silencetrim.gui import Window
from silencetrim.engine import Engine, Track


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.engine = Engine()

    def test_analyze_select_export_and_invalidate(self):
        with tempfile.TemporaryDirectory(prefix="silencetrim-gui-") as temp:
            source = Path(temp) / "nhạc nguồn"
            source.mkdir()
            self.engine._run(self.engine.ffmpeg, ["-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                                  "-af", "adelay=1000,apad=pad_dur=1", str(source / "bài hát.wav")])
            window = Window()
            window.show()
            self.addCleanup(window.close)
            window.set_source(source)
            window.output = Path(temp) / "output"
            self.assertTrue(window.analyze_button.isEnabled())
            self.assertFalse(window.trim_button.isEnabled())
            window.start("analyze")
            self.wait(window)
            self.assertEqual(window.table.rowCount(), 1)
            self.assertEqual(window.tracks[0].relative, "bài hát.wav")
            checkbox = window.table.item(0, 0)
            checkbox.setCheckState(Qt.Unchecked)
            self.assertFalse(window.trim_button.isEnabled())
            checkbox.setCheckState(Qt.Checked)
            self.assertTrue(window.trim_button.isEnabled())
            window.start("export")
            self.wait(window)
            self.assertTrue((window.output / "bài hát.wav").is_file())
            self.assertTrue(window.reveal_button.isEnabled())
            self.assertFalse(window.trim_button.isEnabled())
            self.assertIn("1 file đã xuất", window.status.text())
            self.assertIsNotNone(window.tracks[0].verifiedLeading)
            window.padding.setText("0.7")
            self.assertEqual(window.tracks, [])
            self.assertEqual(window.table.rowCount(), 0)

    def test_long_silence_warning_and_threshold_changes(self):
        window = Window()
        self.addCleanup(window.close)
        self.assertEqual(window.warning_seconds, 5)
        tracks = [Track("", "đúng ngưỡng.wav", leading=5, trailing=5),
                  Track("", "tổng hai đầu.wav", leading=3, trailing=3),
                  Track("", "đầu dài.wav", leading=5.1, cutStart=4.6, selected=False),
                  Track("", "đuôi dài.wav", trailing=10.1),
                  Track("", "toàn bộ im lặng.wav", leading=6, trailing=6, allSilent=True)]
        for row, track in enumerate(tracks):
            window.update_track(row, track)
        red = QColor("#ff7373")
        for row in (0, 1):
            self.assertNotEqual(window.table.item(row, 1).foreground().color(), red)
        for row in (2, 3, 4):
            self.assertEqual(window.table.item(row, 1).foreground().color(), red)
            self.assertIn("Im lặng dài bất thường", window.table.item(row, 5).text())
        self.assertIn("3 BÀI CẦN KIỂM TRA", window.summary.text())
        window.table.selectRow(2)
        self.assertIn("đầu 5.10 s", window.table.item(2, 1).toolTip())
        self.assertIn("Hãy kiểm tra", window.table.item(2, 1).toolTip())
        analyzed = window.analyzed_settings
        window.warning_preset.setCurrentIndex(1)
        self.assertEqual(window.tracks, tracks)
        self.assertIs(window.analyzed_settings, analyzed)
        self.assertFalse(window.tracks[2].selected)
        self.assertNotEqual(window.table.item(2, 1).foreground().color(), red)
        self.assertEqual(window.table.item(3, 1).foreground().color(), red)
        self.assertNotIn("Hãy kiểm tra", window.table.item(2, 1).toolTip())
        self.assertIn("1 BÀI CẦN KIỂM TRA", window.summary.text())
        window.warning_preset.setCurrentIndex(2)
        window.warning_custom.setText("5,05")
        self.assertEqual(window.warning_seconds, 5.05)
        self.assertEqual(window.table.item(2, 1).foreground().color(), red)
        for invalid in ("", "abc", "0", "-1", "nan", "inf"):
            window.warning_custom.setText(invalid)
            self.assertFalse(window.warning_valid)
            self.assertFalse(window.trim_button.isEnabled())
            self.assertEqual(window.table.rowCount(), len(tracks))
        window.warning_preset.setCurrentIndex(0)
        self.assertTrue(window.warning_valid)
        tracks[2].output = "exported.wav"
        tracks[2].verifiedLeading = tracks[2].verifiedTrailing = 0.5
        tracks[2].status = "Đã cắt"
        window.update_track(2, tracks[2])
        self.assertEqual(window.table.item(2, 1).foreground().color(), red)
        self.assertIn("Đã cắt", window.table.item(2, 5).text())
        self.assertIn("Im lặng dài bất thường", window.table.item(2, 5).text())

    def test_analyzed_long_tail_warning_survives_export(self):
        with tempfile.TemporaryDirectory(prefix="silencetrim-warning-") as temp:
            source = Path(temp) / "source"
            source.mkdir()
            self.engine._run(self.engine.ffmpeg, ["-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                                  "-af", "apad=pad_dur=6", str(source / "long-tail.wav")])
            window = Window()
            self.addCleanup(window.close)
            window.set_source(source)
            window.start("analyze")
            self.wait(window)
            self.assertIn("Im lặng dài bất thường", window.table.item(0, 5).text())
            analyzed = window.analyzed_settings
            window.warning_preset.setCurrentIndex(1)
            self.assertIs(window.analyzed_settings, analyzed)
            self.assertNotIn("Im lặng dài bất thường", window.table.item(0, 5).text())
            window.warning_preset.setCurrentIndex(0)
            window.start("export")
            self.wait(window)
            self.assertIsNotNone(window.tracks[0].output)
            self.assertLessEqual(window.tracks[0].verifiedTrailing, 0.500002)
            self.assertIn("Im lặng dài bất thường", window.table.item(0, 5).text())

    def wait(self, window):
        deadline = time.monotonic() + 30
        while window.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertFalse(window.busy, "Worker did not finish")


if __name__ == "__main__":
    unittest.main()
