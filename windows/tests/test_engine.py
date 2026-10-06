import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from silencetrim.engine import (Cancelled, Engine, Settings, Track, TrimError, canonical,
                               relative_path, save_report, validate_output)
from silencetrim.cli import run as run_cli


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="silencetrim-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "nhạc nguồn"
        self.source.mkdir()
        self.output = self.source / "kết quả"
        self.engine.reset()

    def fixture(self, name="bài hát.wav", silent=False, already_ok=False):
        file = self.source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        rate = 48000
        with wave.open(str(file), "wb") as stream:
            stream.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            stream.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / rate))
                if not silent and (already_ok or 1 <= i / rate < 2 or 3 <= i / rate < 4) else 0)
                for i in range(5 * rate)))
        return file

    def ffmpeg(self, *args):
        subprocess.run([self.engine.ffmpeg, "-v", "error", "-y", *map(str, args)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_lossless_samples_and_interior_silence(self):
        file = self.fixture()
        settings = Settings()
        original = file.read_bytes()
        track = self.engine.analyze(file, file.name, settings)
        result = self.engine.export(track, self.root / "trimmed.wav", settings)
        self.assertLessEqual(result.verifiedLeading, 0.500002)
        self.assertLessEqual(result.verifiedTrailing, 0.500002)
        with wave.open(str(file)) as stream:
            samples = stream.readframes(stream.getnframes())
        with wave.open(result.output) as stream:
            kept = stream.readframes(stream.getnframes())
        start = math.ceil(result.cutStart * 48000) * 2
        self.assertEqual(kept, samples[start:start + len(kept)])
        self.assertEqual(file.read_bytes(), original)

    def test_supported_codecs_metadata_and_artwork(self):
        original = self.fixture()
        # A small PPM creates artwork without requiring an image library.
        ppm = self.root / "cover.ppm"
        ppm.write_bytes(b"P6\n16 16\n255\n" + bytes([64, 215, 190]) * 256)
        cover = self.root / "cover.png"
        self.ffmpeg("-i", ppm, "-frames:v", "1", cover)
        formats = [("mp3", "libmp3lame"), ("m4a", "aac"), ("aac", "aac"),
                   ("flac", "flac"), ("aiff", "pcm_s16be"), ("opus", "libopus"),
                   ("alac.m4a", "alac"), ("24bit.wav", "pcm_s24le"), ("24bit.flac", "flac")]
        for suffix, codec in formats:
            with self.subTest(codec=codec, suffix=suffix):
                file = self.source / ("test." + suffix)
                args = ["-i", original]
                art = suffix in {"mp3", "m4a", "flac", "alac.m4a"}
                if art:
                    args += ["-i", cover, "-map", "0:a:0", "-map", "1:v:0", "-c:v", "png", "-disposition:v", "attached_pic"]
                args += ["-c:a", codec, "-metadata", "title=Kiểm thử SilenceTrim"]
                if suffix == "24bit.flac":
                    args += ["-sample_fmt", "s32", "-bits_per_raw_sample", "24"]
                self.ffmpeg(*args, file)
                digest = hashlib.sha256(file.read_bytes()).digest()
                track = self.engine.analyze(file, file.name, Settings())
                result = self.engine.export(track, self.root / file.name, Settings())
                self.assertIsNotNone(result.output)
                self.assertEqual(hashlib.sha256(file.read_bytes()).digest(), digest)
                self.assertEqual(self.engine.probe(Path(result.output)).codec, codec if codec != "libmp3lame" and codec != "libopus" else {"libmp3lame": "mp3", "libopus": "opus"}[codec])
                self.assertEqual(len(self.engine.probe(Path(result.output)).art_indices), int(art))
                if suffix != "aac":
                    info = json.loads(subprocess.check_output([self.engine.ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", result.output]))
                    tags = dict(info["format"].get("tags", {}))
                    for stream in info["streams"]:
                        tags.update(stream.get("tags", {}))
                    self.assertEqual(tags["title"], "Kiểm thử SilenceTrim")
        # Use the native encoder to avoid relying on libvorbis in every FFmpeg installation.
        vorbis = self.source / "test.ogg"
        self.ffmpeg("-i", original, "-c:a", "vorbis", "-strict", "experimental", "-ac", "2", vorbis)
        result = self.engine.export(self.engine.analyze(vorbis, vorbis.name, Settings()), self.root / "out.ogg", Settings())
        self.assertIsNotNone(result.output)

    def test_unchanged_silent_and_already_ok(self):
        for name, flags in [("silent.wav", {"silent": True}), ("ok.wav", {"already_ok": True})]:
            file = self.fixture(name, **flags)
            result = self.engine.export(self.engine.analyze(file, name, Settings()), self.root / name, Settings())
            self.assertEqual(file.read_bytes(), Path(result.output).read_bytes())

    def test_inventory_paths_and_nested_output(self):
        self.fixture()
        self.fixture("album/bài hát.wav")
        self.fixture("kết quả/old.wav")
        files = self.engine.inventory(self.source, Settings(recursive=True), self.output)
        self.assertEqual(sorted(relative_path(file, self.source) for file in files), ["album/bài hát.wav", "bài hát.wav"])
        self.assertEqual(len(self.engine.inventory(self.source, Settings(), self.output)), 1)
        alias = self.root / "alias"
        try:
            alias.symlink_to(self.source, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
        else:
            self.assertEqual(self.engine.inventory(alias, Settings(recursive=True), alias / "kết quả"), files)
            self.assertEqual(relative_path(files[0], alias), relative_path(files[0], self.source))
        with self.assertRaises(TrimError):
            relative_path(self.root / "nhạc nguồn khác" / "song.wav", self.source)
        for output in [self.source, self.root, Path(self.source.anchor)]:
            with self.assertRaises(TrimError):
                validate_output(output, self.source)
        validate_output(self.output, self.source)

    def test_source_changed_and_existing_destination(self):
        file = self.fixture()
        track = self.engine.analyze(file, file.name, Settings())
        destination = self.root / "existing.wav"
        destination.write_bytes(b"keep me")
        with self.assertRaises(TrimError):
            self.engine.export(track, destination, Settings())
        self.assertEqual(destination.read_bytes(), b"keep me")
        file.write_bytes(file.read_bytes() + b"changed")
        with self.assertRaises(TrimError):
            self.engine.export(track, self.root / "changed.wav", Settings())

    def test_cancellation_terminates_process_and_allows_restart(self):
        caught = []
        def work():
            try:
                self.engine._run(sys.executable, ["-c", "import time; time.sleep(30)"])
            except Cancelled:
                caught.append(True)
        thread = threading.Thread(target=work)
        thread.start()
        deadline = time.monotonic() + 5
        while self.engine._process is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.engine.cancel()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(caught, [True])
        self.engine.reset()
        self.assertEqual(self.engine._run(sys.executable, ["-c", "print('ok')"]).strip(), "ok")

    def test_missing_tools_and_invalid_settings(self):
        with patch.dict(os.environ, {"PATH": ""}):
            with self.assertRaises(TrimError):
                Engine()
        for settings in [Settings(padding=0), Settings(threshold=float("nan")), Settings(padding=float("inf"))]:
            with self.assertRaises(TrimError):
                settings.validate()

    def test_cli_batch_and_report(self):
        self.fixture("album/bài hát.wav")
        self.assertEqual(run_cli(["--input", str(self.source), "--output", str(self.output), "--recursive"]), 0)
        reports = list(self.output.glob("*.json"))
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertEqual(report["version"], "2.0")
        self.assertEqual(report["tracks"][0]["relative"], "album/bài hát.wav")
        self.assertTrue((self.output / "album" / "bài hát.wav").is_file())
        self.assertEqual(run_cli(["--input", str(self.source), "--output", str(self.output), "--recursive"]), 1)
        bad = self.source / "bad.mp3"
        bad.write_bytes(b"corrupt")
        with self.assertRaises(TrimError):
            self.engine.analyze(bad, bad.name, Settings())


if __name__ == "__main__":
    unittest.main()
