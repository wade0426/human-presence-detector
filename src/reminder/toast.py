from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QSystemTrayIcon

from src.types import ReminderContext
from src.ui import strings


class ToastReminder(QObject):
    dismissed = Signal()

    def __init__(self, tray: QSystemTrayIcon | None = None) -> None:
        super().__init__()
        self._tray = tray or QSystemTrayIcon()

    def show(self, ctx: ReminderContext) -> None:
        self._tray.showMessage(
            strings.REMIND_TITLE,
            strings.REMIND_BODY.format(minutes=ctx.work_minutes),
        )
        self.dismissed.emit()

    def hide(self) -> None:
        return None
