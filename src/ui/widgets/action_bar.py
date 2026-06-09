from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from src.ui.strings import (
    ACTION_EDIT_ROI,
    ACTION_EDIT_ROI_ACTIVE,
    ACTION_PAUSE,
    ACTION_QUIT,
    ACTION_RESUME,
    ACTION_SETTINGS,
)


class ActionBar(QWidget):
    edit_roi_toggled = Signal(bool)
    pause_toggled = Signal(bool)
    open_settings = Signal()
    request_quit = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._roi_btn = QPushButton(ACTION_EDIT_ROI)
        self._roi_btn.setCheckable(True)
        self._pause_btn = QPushButton(ACTION_PAUSE)
        self._pause_btn.setCheckable(True)
        self._settings_btn = QPushButton(ACTION_SETTINGS)
        self._quit_btn = QPushButton(ACTION_QUIT)
        self._quit_btn.setProperty("role", "danger")

        self._roi_btn.toggled.connect(self._on_roi_toggled)
        self._pause_btn.toggled.connect(self._on_pause_toggled)
        self._settings_btn.clicked.connect(self.open_settings)
        self._quit_btn.clicked.connect(self.request_quit)

        layout = QHBoxLayout(self)
        layout.addWidget(self._roi_btn)
        layout.addWidget(self._pause_btn)
        layout.addStretch()
        layout.addWidget(self._quit_btn)
        layout.addWidget(self._settings_btn)

    def _on_pause_toggled(self, checked: bool) -> None:
        self._pause_btn.setText(ACTION_RESUME if checked else ACTION_PAUSE)
        self.pause_toggled.emit(checked)

    def _on_roi_toggled(self, checked: bool) -> None:
        self.set_edit_active(checked)
        self.edit_roi_toggled.emit(checked)

    def set_edit_active(self, on: bool) -> None:
        """Switch button text/style to reflect ROI edit mode."""
        self._roi_btn.setText(ACTION_EDIT_ROI_ACTIVE if on else ACTION_EDIT_ROI)
