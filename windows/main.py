"""Windowed launcher; --batch also works without importing Qt."""
import sys

if __name__ == "__main__":
    if "--batch" in sys.argv:
        from silencetrim.cli import run
        sys.exit(run())
    from silencetrim.gui import run
    sys.exit(run())
