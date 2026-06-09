from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from src.ui.strings import ACTION_EDIT_ROI, ACTION_PAUSE, ACTION_RESUME, ACTION_SETTINGS


class ActionBar(QWidget):
    edit_roi_toggled = Signal(bool)
    pause_toggled = Signal(bool)
    open_settings = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._roi_btn = QPushButton(ACTION_EDIT_ROI)
        self._roi_btn.setCheckable(True)
        self._pause_btn = QPushButton(ACTION_PAUSE)
        self._pause_btn.setCheckable(True)
        self._settings_btn = QPushButton(ACTION_SETTINGS)

        self._roi_btn.toggled.connect(self.edit_roi_toggled)
        self._pause_btn.toggled.connect(self._on_pause_toggled)
        self._settings_btn.clicked.connect(self.open_settings)

        layout = QHBoxLayout(self)
        layout.addWidget(self._roi_btn)
        layout.addWidget(self._pause_btn)
        layout.addStretch()
        layout.addWidget(self._settings_btn)

    def _on_pause_toggled(self, checked: bool) -> None:
        self._pause_btn.setText(ACTION_RESUME if checked else ACTION_PAUSE)
        self.pause_toggled.emit(checked)
