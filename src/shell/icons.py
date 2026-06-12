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


# Anchored to this module's location so the asset resolves regardless of CWD
# (icons.py lives in src/shell/, so parents[2] is the project root).
_DEFAULT_ICON_PATH = Path(__file__).resolve().parents[2] / "data" / "assets" / "icon.png"


def load_app_icon(asset_path: str | Path | None = None, size: int = 64) -> QIcon:
    """Load an icon from disk and fall back to an in-memory icon when needed."""
    asset = Path(asset_path) if asset_path is not None else _DEFAULT_ICON_PATH
    if asset.exists():
        icon = QIcon(str(asset))
        if not icon.isNull():
            return icon
    return make_app_icon(size)
