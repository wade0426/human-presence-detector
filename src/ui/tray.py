from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from src.types import TimerState


class TrayIcon(QSystemTrayIcon):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(QIcon(), parent)
        menu = QMenu(parent)
        self.open_action = QAction("開啟主視窗", self)
        self.toggle_action = QAction("暫停/繼續偵測", self)
        self.settings_action = QAction("設定", self)
        self.quit_action = QAction("結束", self)
        menu.addAction(self.open_action)
        menu.addAction(self.toggle_action)
        menu.addAction(self.settings_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        self._window_to_show: QWidget | None = None
        self.setToolTip("人體辨識休息提醒系統")

    def bind_window(self, window: QWidget) -> None:
        self._window_to_show = window
        self.open_action.triggered.connect(window.showNormal)
        self.open_action.triggered.connect(window.activateWindow)

    def update_status(self, state: TimerState) -> None:
        mapping = {
            TimerState.IDLE: "待機",
            TimerState.WORKING: "工作中",
            TimerState.PAUSED: "短暫離開",
            TimerState.REMINDING: "提醒中",
        }
        self.setToolTip(f"人體辨識休息提醒系統 - {mapping[state]}")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if (
            reason == QSystemTrayIcon.ActivationReason.DoubleClick
            and self._window_to_show is not None
        ):
            self._window_to_show.showNormal()
            self._window_to_show.activateWindow()
