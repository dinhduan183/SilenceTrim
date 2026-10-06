# Third-party components

The Windows distribution includes Python, PySide6/Qt, Shiboken and the PyInstaller bootloader. FFmpeg and FFprobe are external executables provided by the user through PATH; neither is bundled.

- Python: Python Software Foundation license, https://docs.python.org/3/license.html
- Qt for Python / PySide6 / Shiboken: LGPLv3 (or other upstream licensing options), https://doc.qt.io/qtforpython-6/licenses.html
- Qt: applicable Qt open-source licenses, https://www.qt.io/licensing/open-source-lgpl-obligations
- PyInstaller bootloader: GPL with the PyInstaller exception, https://pyinstaller.org/en/stable/license.html

Qt is distributed as dynamically linked libraries in the `_internal` directory, allowing replacement with compatible modified libraries. The Windows build copies upstream license files into `licenses/`; license texts and component sources are also available from the links above and https://code.qt.io/cgit/pyside/pyside-setup.git/ and https://code.qt.io/cgit/qt/.
