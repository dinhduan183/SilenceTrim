# Build on Windows: python -m PyInstaller --noconfirm windows/SilenceTrim.spec
from pathlib import Path
import sys

root = Path(SPECPATH).parent
assets = [(str(root / "source" / "AppIcon.png"), "assets")]
icon = str(root / "source" / ("AppIcon.ico" if sys.platform == "win32" else "AppIcon.icns"))

gui = Analysis([str(root / "windows" / "main.py")], pathex=[str(root / "windows")],
               binaries=[], datas=assets, hiddenimports=[], hookspath=[], hooksconfig={},
               runtime_hooks=[], excludes=[], noarchive=False)
cli = Analysis([str(root / "windows" / "cli_main.py")], pathex=[str(root / "windows")],
               binaries=[], datas=[], hiddenimports=[], hookspath=[], hooksconfig={},
               runtime_hooks=[], excludes=["PySide6"], noarchive=False)
gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True,
              name="SilenceTrim", debug=False, bootloader_ignore_signals=False,
              strip=False, upx=False, console=False, icon=icon, version=str(root / "windows" / "version_info.txt"))
cli_exe = EXE(PYZ(cli.pure), cli.scripts, [], exclude_binaries=True,
              name="SilenceTrim-CLI", debug=False, bootloader_ignore_signals=False,
              strip=False, upx=False, console=True, icon=icon, version=str(root / "windows" / "version_info.txt"))
COLLECT(gui_exe, cli_exe, gui.binaries, gui.datas, cli.binaries, cli.datas,
        strip=False, upx=False, name="SilenceTrim")
