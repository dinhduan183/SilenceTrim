"""Convert the existing PNG into a multi-resolution Windows icon."""
from pathlib import Path
import struct
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

root = Path(__file__).resolve().parents[1]
image = QImage(str(root / "source" / "AppIcon.png"))
if image.isNull():
    raise SystemExit("Cannot load AppIcon.png")
sizes = [16, 24, 32, 48, 64, 128, 256]
images = []
for size in sizes:
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    if not image.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).save(buffer, "PNG"):
        raise SystemExit("Cannot encode PNG")
    images.append(bytes(buffer.data()))
offset = 6 + 16 * len(sizes)
entries = []
for size, data in zip(sizes, images):
    entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
    offset += len(data)
(root / "source" / "AppIcon.ico").write_bytes(struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries + images))
print("Created source/AppIcon.ico")
