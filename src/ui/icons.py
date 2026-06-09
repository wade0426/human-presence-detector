from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap


def make_app_icon(size: int = 64) -> QIcon:
    """Create a simple in-memory fallback icon."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor("#007AFF"))

    painter = QPainter(pixmap)
    painter.setPen(QColor("#FFFFFF"))
    font = painter.font()
    font.setPixelSize(int(size * 0.5))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "H")
    painter.end()

    return QIcon(pixmap)


def load_app_icon(asset_path: str = "data/assets/icon_1024.png", size: int = 64) -> QIcon:
    """Load an icon from disk and fall back to an in-memory icon when needed."""
    asset = Path(asset_path)
    if asset.exists():
        icon = QIcon(str(asset))
        if not icon.isNull():
            return icon
    return make_app_icon(size)
