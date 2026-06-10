from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from src.ui import strings


class ForceLockCountdownWindow(QWidget):
    expired = Signal()
    cancelled = Signal()

    def __init__(
        self, seconds: int, cancellable: bool, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )

        self._remaining = seconds
        self._label = QLabel(strings.FORCE_LOCK_COUNTDOWN.format(seconds=self._remaining))

        layout = QVBoxLayout(self)
        layout.addWidget(self._label)

        if cancellable:
            cancel_btn = QPushButton(strings.FORCE_LOCK_CANCEL)
            cancel_btn.clicked.connect(self._on_cancel)
            layout.addWidget(cancel_btn)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

    def start(self) -> None:
        self._center_on_screen()
        self.show()
        self._timer.start()

    def _on_tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self.expired.emit()
            self.hide()
            return
        self._label.setText(strings.FORCE_LOCK_COUNTDOWN.format(seconds=self._remaining))

    def _on_cancel(self) -> None:
        self._timer.stop()
        self.cancelled.emit()
        self.hide()

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.geometry()
        self.adjustSize()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )
