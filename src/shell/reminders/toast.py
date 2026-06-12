from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QSystemTrayIcon

from src.duration_format import format_duration_zh
from src.shell import strings
from src.shell.reminders.context import ReminderContext


class ToastReminder(QObject):
    dismissed = Signal()

    def __init__(self, tray: QSystemTrayIcon | None = None) -> None:
        super().__init__()
        self._tray = tray or QSystemTrayIcon()

    def show(self, ctx: ReminderContext) -> None:
        self._tray.showMessage(
            strings.REMIND_TITLE,
            strings.REMIND_BODY.format(duration=format_duration_zh(ctx.work_elapsed_sec)),
        )
        self.dismissed.emit()

    def hide(self) -> None:
        return None
