from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QPainter, QPixmap


def load_pixmap(path: str, *, fallback_text: str = "該休息一下了") -> QPixmap:
    if path and Path(path).exists():
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            return pixmap
    return _make_placeholder(fallback_text)


def _make_placeholder(text: str) -> QPixmap:
    pixmap = QPixmap(320, 200)
    pixmap.fill(QColor("#1C1C1E"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("#F2F2F7"))
    font = painter.font()
    font.setPixelSize(20)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return pixmap


def is_playable_video(path: str) -> bool:
    if not path:
        return False
    suffix = Path(path).suffix.lower()
    return suffix in {".mp4", ".avi", ".mkv", ".mov", ".webm"} and Path(path).exists()


def safe_sound_url(path: str) -> QUrl | None:
    if not path or not Path(path).exists():
        return None
    return QUrl.fromLocalFile(path)
