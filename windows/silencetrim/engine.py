"""FFmpeg engine. No GUI dependencies; also testable on macOS and Linux."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import uuid

from . import VERSION


class TrimError(Exception):
    pass


class Cancelled(TrimError):
    pass


@dataclass(frozen=True)
class Settings:
    threshold: float = -60
    padding: float = 0.5
    recursive: bool = False

    def validate(self):
        if not (math.isfinite(self.threshold) and -100 <= self.threshold <= -20
                and math.isfinite(self.padding) and 0.1 <= self.padding <= 2):
            raise TrimError("Ngưỡng phải từ −100 đến −20 dB; khoảng giữ lại từ 0,1 đến 2 giây.")


@dataclass
class AudioInfo:
    codec: str
    rate: int
    bits: int
    art_indices: list[int]

    @property
    def lossless(self):
        return self.codec in {"flac", "alac"} or self.codec.startswith(("pcm_s", "pcm_u", "pcm_f"))


@dataclass
class Edges:
    duration: float
    leading: float
    trailing: float
    all_silent: bool


@dataclass
class Track:
    source: str
    relative: str
    duration: float = 0
    leading: float = 0
    trailing: float = 0
    cutStart: float = 0
    cutEnd: float = 0
    codec: str = ""
    lossless: bool = False
    selected: bool = True
    allSilent: bool = False
    status: str = "Đang chờ"
    error: str | None = None
    originalSize: int = 0
    originalModified: int = 0  # nanoseconds, to detect source changes
    output: str | None = None
    verifiedLeading: float | None = None
    verifiedTrailing: float | None = None


def canonical(path: str | Path) -> Path:
    return Path(path).resolve()


def relative_path(file: Path, folder: Path) -> str:
    try:
        relative = canonical(file).relative_to(canonical(folder))
    except ValueError as exc:
        raise TrimError("File không nằm trong thư mục nguồn.") from exc
    if relative == Path("."):
        raise TrimError("File không nằm trong thư mục nguồn.")
    return relative.as_posix()


def validate_output(output: Path, source: Path):
    if canonical(source).is_relative_to(canonical(output)):
        raise TrimError("Chọn thư mục xuất khác thư mục gốc và không phải thư mục cha của nó.")


def unique_output(source: Path) -> Path:
    base = source.with_name(source.name + " — Trimmed")
    output, number = base, 2
    while output.exists():
        output = base.with_name(f"{base.name} {number}")
        number += 1
    return output


def save_report(tracks: list[Track], settings: Settings, folder: Path) -> Path:
    report = {"version": VERSION, "createdAt": datetime.now(timezone.utc).isoformat(),
              "settings": asdict(settings), "tracks": [asdict(track) for track in tracks]}
    path = folder / f"SilenceTrim-report-{uuid.uuid4().hex[:8]}.json"
    # Exclusive creation avoids overwriting even in the unlikely event of a collision.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return path


class Engine:
    extensions = {".mp3", ".m4a", ".aac", ".flac", ".wav", ".aif", ".aiff", ".ogg", ".opus"}

    def __init__(self):
        self.ffmpeg = self._find("ffmpeg")
        self.ffprobe = self._find("ffprobe")
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None

    @staticmethod
    def _find(name):
        path = shutil.which(name)
        if not path:
            raise TrimError(f"Thiếu {name} trong PATH. Hãy thêm FFmpeg/FFprobe vào PATH rồi mở lại app.")
        return path

    def reset(self):
        self._stopped.clear()

    def cancel(self):
        with self._lock:
            self._stopped.set()
            if self._process is not None and self._process.poll() is None:
                try:
                    self._process.terminate()
                except OSError:
                    pass

    def check_cancelled(self):
        if self._stopped.is_set():
            raise Cancelled("Đã dừng.")

    def _run(self, tool: str, arguments: list[str]) -> str:
        self.check_cancelled()
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with tempfile.TemporaryFile() as log:
            with self._lock:
                self.check_cancelled()
                process = subprocess.Popen([tool, *arguments], stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=log, creationflags=flags)
                self._process = process
            try:
                process.wait()
            finally:
                with self._lock:
                    self._process = None
            self.check_cancelled()
            log.seek(0)
            output = log.read().decode("utf-8", errors="replace")
        if process.returncode:
            raise TrimError(output[-1400:].strip() or f"{Path(tool).name}: exit {process.returncode}")
        return output

    def inventory(self, folder: Path, settings: Settings, excluding: Path | None = None) -> list[Path]:
        settings.validate()
        root = canonical(folder)
        if not root.is_dir():
            raise TrimError("Không đọc được thư mục nguồn.")
        excluded = canonical(excluding) if excluding is not None else None
        files = []
        def skip(path):
            return (path.name.startswith(".") or path.is_symlink()
                    or getattr(path, "is_junction", lambda: False)()
                    or (excluded is not None and canonical(path).is_relative_to(excluded)))
        def on_error(error):
            raise TrimError(f"Không đọc được thư mục: {error}") from error
        for current, dirs, names in os.walk(root, followlinks=False, onerror=on_error):
            self.check_cancelled()
            dirs[:] = [name for name in dirs if settings.recursive and not skip(Path(current) / name)]
            for name in names:
                self.check_cancelled()
                file = Path(current) / name
                if file.suffix.lower() in self.extensions and not skip(file) and file.is_file():
                    files.append(canonical(file))
        return sorted(files, key=lambda file: str(file).casefold())

    def probe(self, file: Path) -> AudioInfo:
        streams = json.loads(self._run(self.ffprobe, ["-v", "error", "-show_streams", "-of", "json", str(file)])).get("streams", [])
        audio = [s for s in streams if s.get("codec_type") == "audio"]
        videos = [s for s in streams if s.get("codec_type") == "video"]
        if len(audio) != 1:
            raise TrimError("File phải có đúng một luồng âm thanh.")
        if any(s.get("disposition", {}).get("attached_pic") != 1 for s in videos):
            raise TrimError("File có video, không phải bài nhạc độc lập.")
        first = audio[0]
        bits = int(first.get("bits_per_raw_sample") or first.get("bits_per_sample") or 0)
        return AudioInfo(first.get("codec_name", ""), int(first.get("sample_rate") or 44100), bits,
                         [s["index"] for s in videos])

    def detect(self, file: Path, settings: Settings, rate=44100) -> Edges:
        with tempfile.TemporaryDirectory(prefix="silencetrim-") as temp:
            progress = Path(temp) / "progress.txt"
            log = self._run(self.ffmpeg, ["-hide_banner", "-nostdin", "-nostats", "-xerror", "-i", str(file),
                "-map", "0:a:0", "-vn", "-af", f"asetpts=PTS-STARTPTS,silencedetect=noise={settings.threshold}dB:d=0.05",
                "-progress", str(progress), "-f", "null", "-"])
            times = re.findall(r"^out_time_us=(\d+)$", progress.read_text(encoding="utf-8"), re.MULTILINE)
        if not times or int(times[-1]) <= 0:
            raise TrimError("File không có thời lượng âm thanh hợp lệ.")
        duration = int(times[-1]) / 1_000_000
        intervals, start = [], None
        for kind, number in re.findall(r"silence_(start|end): ([0-9.eE+\-]+)", log):
            value = float(number)
            if kind == "start":
                start = max(0, value)
            elif start is not None:
                intervals.append((start, min(duration, value)))
                start = None
        if start is not None:
            intervals.append((start, duration))
        epsilon = max(0.0001, 2 / rate)
        leading = intervals[0][1] if intervals and intervals[0][0] <= epsilon else 0
        trailing = duration - intervals[-1][0] if intervals and abs(intervals[-1][1] - duration) <= epsilon else 0
        return Edges(duration, leading, trailing, leading >= duration - epsilon)

    def analyze(self, file: Path, relative: str, settings: Settings) -> Track:
        settings.validate()
        stat = file.stat()
        info = self.probe(file)
        edges = self.detect(file, settings, info.rate)
        track = Track(str(file), relative, duration=edges.duration, leading=edges.leading, trailing=edges.trailing,
                      codec=info.codec, lossless=info.lossless, allSilent=edges.all_silent,
                      originalSize=stat.st_size, originalModified=stat.st_mtime_ns)
        if edges.all_silent:
            track.status = "Toàn bộ im lặng · giữ nguyên"
            return track
        retained = settings.padding if info.lossless else max(0.05, settings.padding - 0.08)
        track.cutStart = max(0, edges.leading - retained) if edges.leading > settings.padding else 0
        track.cutEnd = max(0, edges.trailing - retained) if edges.trailing > settings.padding else 0
        track.status = "Sẵn sàng cắt" if track.cutStart + track.cutEnd > 0 else "Đã đạt · giữ nguyên"
        return track

    @staticmethod
    def _publish(temp: Path, destination: Path):
        # Windows rename refuses an existing destination. On POSIX, link is atomic
        # and exclusive, unlike rename, which could overwrite a concurrently created file.
        if os.name == "nt":
            temp.rename(destination)
        else:
            os.link(temp, destination)
            temp.unlink()

    def export(self, track: Track, destination: Path, settings: Settings) -> Track:
        settings.validate()
        self.check_cancelled()
        source = Path(track.source)
        stat = source.stat()
        if stat.st_size != track.originalSize or stat.st_mtime_ns != track.originalModified:
            raise TrimError("File gốc đã thay đổi sau khi phân tích. Hãy phân tích lại.")
        if destination.exists():
            raise TrimError("File đích đã tồn tại; không ghi đè.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = replace(track)
        # Temp files share the destination filesystem for atomic publication.
        with tempfile.TemporaryDirectory(prefix=".silencetrim-", dir=destination.parent) as work:
            temp = Path(work) / ("audio" + destination.suffix)
            if track.cutStart + track.cutEnd <= 0:
                shutil.copy2(source, temp)
                self.check_cancelled()
                self._publish(temp, destination)
                result.status = "Đã sao chép · toàn bộ im lặng" if track.allSilent else "Đã sao chép · đã đạt"
                result.output = str(destination)
                result.verifiedLeading, result.verifiedTrailing = track.leading, track.trailing
                return result
            info = self.probe(source)
            start, end_cut = track.cutStart, track.cutEnd
            for attempt in range(4):
                self.check_cancelled()
                end = track.duration - end_cut
                args = ["-hide_banner", "-nostdin", "-loglevel", "error", "-xerror", "-y", "-i", str(source)]
                if info.lossless:
                    first, last = math.ceil(start * info.rate), math.floor(end * info.rate)
                    args += ["-map", "0:a:0", "-af", f"atrim=start_sample={first}:end_sample={last},asetpts=PTS-STARTPTS", "-c:a", info.codec]
                    if info.codec in {"flac", "alac"}:
                        fmt = ("s32" if info.bits > 16 else "s16") + ("p" if info.codec == "alac" else "")
                        args += ["-sample_fmt", fmt]
                        if info.bits > 0:
                            args += ["-bits_per_raw_sample", str(info.bits)]
                else:
                    args += ["-ss", f"{start:.9f}", "-t", f"{end - start:.9f}", "-map", "0:a:0", "-c:a", "copy"]
                args += ["-c:v", "copy", "-map_metadata", "0", "-map_metadata:s:a:0", "0:s:a:0", "-map_chapters", "-1", str(temp)]
                self._run(self.ffmpeg, args)
                if info.art_indices:
                    art = Path(work) / ("art" + destination.suffix)
                    remux = ["-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", str(temp), "-i", str(source), "-map", "0:a:0"]
                    for index in info.art_indices:
                        remux += ["-map", f"1:{index}"]
                    remux += ["-c", "copy", "-disposition:v", "attached_pic", "-map_metadata", "1", "-map_metadata:s:a:0", "1:s:a:0", "-map_chapters", "-1", str(art)]
                    self._run(self.ffmpeg, remux)
                    art.replace(temp)
                check = self.probe(temp)
                if (check.codec != info.codec or check.rate != info.rate or len(check.art_indices) != len(info.art_indices)
                        or (info.bits and info.lossless and check.bits != info.bits)):
                    raise TrimError("Thông số âm thanh đầu ra thay đổi; không xuất file.")
                edges = self.detect(temp, settings, info.rate)
                if edges.all_silent:
                    raise TrimError("Đầu ra chỉ còn im lặng; không xuất file.")
                head_excess, tail_excess = max(0, edges.leading - settings.padding), max(0, edges.trailing - settings.padding)
                if head_excess <= 0.000002 and tail_excess <= 0.000002:
                    self.check_cancelled()
                    self._publish(temp, destination)
                    result.cutStart, result.cutEnd, result.output = start, end_cut, str(destination)
                    result.verifiedLeading, result.verifiedTrailing = edges.leading, edges.trailing
                    result.status = "Đã cắt · đã kiểm tra"
                    return result
                if attempt == 3:
                    break
                next_start = start + (head_excess + 0.025 if head_excess else 0)
                next_end = end_cut + (tail_excess + 0.025 if tail_excess else 0)
                if not ((next_start < track.leading or next_start == 0) and (next_end < track.trailing or next_end == 0)):
                    break
                start, end_cut = next_start, next_end
        raise TrimError("Không đạt giới hạn im lặng bằng cắt lossless; file gốc được giữ nguyên.")
