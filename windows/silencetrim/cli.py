import argparse
import io
from pathlib import Path
import sys

from .engine import Engine, Settings, Track, canonical, relative_path, save_report, validate_output


def emit(message):
    if sys.stdout is not None:
        print(message)


def run(argv=None):
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="SilenceTrim-CLI", description="Cắt im lặng đầu và cuối thư mục nhạc.")
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=-60)
    parser.add_argument("--padding", type=float, default=0.5)
    parser.add_argument("--recursive", action="store_true")
    args = parser.parse_args(argv)
    try:
        settings = Settings(args.threshold, args.padding, args.recursive)
        settings.validate()
        source, output = canonical(args.input), canonical(args.output)
        validate_output(output, source)
        engine = Engine()
        files = engine.inventory(source, settings, output)
        if not files:
            raise ValueError("Không tìm thấy file âm thanh được hỗ trợ.")
        output.mkdir(parents=True, exist_ok=True)
        tracks, failures = [], 0
        for file in files:
            relative = relative_path(file, source)
            track = Track(str(file), relative)
            try:
                track = engine.analyze(file, relative, settings)
                track = engine.export(track, output / relative, settings)
            except Exception as error:
                track.error, track.status = str(error), "Lỗi"
                failures += 1
            tracks.append(track)
            emit(f"{relative}: {track.status}" + (f" — {track.error}" if track.error else ""))
        emit(f"Report: {save_report(tracks, settings, output)}")
        return 1 if failures else 0
    except Exception as error:
        emit(str(error))
        return 1
