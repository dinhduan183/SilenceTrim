"""Runs the actual bundled launchers, not the development Python source."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

package = Path(sys.argv[1]).resolve()
suffix = ".exe" if os.name == "nt" else ""
with tempfile.TemporaryDirectory(prefix="silencetrim-package-") as temp:
    root = Path(temp)
    source, output = root / "nhạc nguồn", root / "kết quả"
    source.mkdir()
    with wave.open(str(source / "bài hát.wav"), "wb") as audio:
        audio.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 48000)
    command = [str(package / ("SilenceTrim-CLI" + suffix)), "--batch", "--input", str(source), "--output", str(output), "--recursive"]
    subprocess.run(command, check=True, timeout=30)
    assert (output / "bài hát.wav").read_bytes() == (source / "bài hát.wav").read_bytes()
    report = json.loads(next(output.glob("*.json")).read_text(encoding="utf-8"))
    assert report["version"] == "2.2" and report["tracks"][0]["relative"] == "bài hát.wav"
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    subprocess.run([str(package / ("SilenceTrim" + suffix)), "--smoke-test"], env=environment, check=True, timeout=30)
print("PASS: bundled CLI and GUI")
