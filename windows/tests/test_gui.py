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
from silencetrim.gui import Window
from silencetrim.engine import Engine


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

    def wait(self, window):
        deadline = time.monotonic() + 30
        while window.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertFalse(window.busy, "Worker did not finish")


if __name__ == "__main__":
    unittest.main()
