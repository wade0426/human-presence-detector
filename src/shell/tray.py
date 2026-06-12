"""系統匣圖示（自 src/ui/tray.py 移植，改 v2 core 型別）。"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from src.core.events import TimerSnapshot, TimerState
from src.shell import strings
from src.shell.icons import load_app_icon
from src.shell.widgets.connection_state import ConnectionState, from_status


class TrayIcon(QSystemTrayIcon):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(load_app_icon(), parent)
        menu = QMenu(parent)
        self.open_action = QAction(strings.TRAY_OPEN, self)
        self.toggle_action = QAction(strings.TRAY_PAUSE, self)
        self.settings_action = QAction(strings.TRAY_SETTINGS, self)
        self.quit_action = QAction(strings.TRAY_QUIT, self)
        menu.addAction(self.open_action)
        menu.addAction(self.toggle_action)
        menu.addAction(self.settings_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        self._window_to_show: QWidget | None = None
        self._paused = False
        self._timer_state = TimerState.IDLE
        self._conn_state = ConnectionState.IDLE
        self._update_tooltip()

    def bind_window(self, window: QWidget) -> None:
        self._window_to_show = window
        self.open_action.triggered.connect(window.showNormal)
        self.open_action.triggered.connect(window.activateWindow)

    # §4.6: thin QObject slots — worker signals connect to these bound methods so
    # PySide6 auto-queues the call back to the GUI thread (lambdas would run the
    # QSystemTrayIcon UI updates on the detection thread).
    @Slot(object)
    def on_timer_updated(self, snapshot: TimerSnapshot) -> None:
        self.set_timer_state(snapshot.state)

    @Slot(str)
    def on_connection_status(self, status: str) -> None:
        self.set_connection(from_status(status))

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self.toggle_action.setText(strings.TRAY_RESUME if paused else strings.TRAY_PAUSE)

    def set_timer_state(self, state: TimerState) -> None:
        self._timer_state = state
        self._update_tooltip()

    def set_connection(self, state: ConnectionState) -> None:
        self._conn_state = state
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        timer_text = strings.STATE_TEXT.get(self._timer_state.value, "")
        conn_text = strings.CONN_TEXT.get(self._conn_state.value, "")
        self.setToolTip(f"人體辨識提醒 — {conn_text} / {timer_text}")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if (
            reason == QSystemTrayIcon.ActivationReason.DoubleClick
            and self._window_to_show is not None
        ):
            self._window_to_show.showNormal()
            self._window_to_show.activateWindow()
