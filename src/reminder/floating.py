from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.config import FloatingConfig
from src.types import ReminderContext


class FloatingReminder(QWidget):
    dismissed = Signal()

    def __init__(self, config: FloatingConfig) -> None:
        super().__init__()
        self._config = config
        self._remaining = 0
        self._flash = False
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.label = QLabel("", self)
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def show(self, ctx: ReminderContext | None = None) -> None:
        if ctx is None:
            super().show()
            return
        self._remaining = max(ctx.work_minutes * 60, 1)
        self._flash = False
        self._update_label()
        self._timer.start(1000)
        super().show()

    def hide(self) -> None:
        self._timer.stop()
        super().hide()

    def _tick(self) -> None:
        if self._remaining > 0:
            self._remaining -= 1
        else:
            self._flash = not self._flash
        self._update_label()

    def _update_label(self) -> None:
        if self._remaining > 0:
            self.label.setText(f"休息倒數 {self._remaining}s")
            self.setStyleSheet("")
        else:
            self.label.setText("請立刻休息")
            self.setStyleSheet("background-color: red;" if self._flash else "")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.dismissed.emit()
        self.hide()
        super().mousePressEvent(event)
