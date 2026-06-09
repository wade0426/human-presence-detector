from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QSystemTrayIcon

from src.types import ReminderContext


class ToastReminder(QObject):
    dismissed = Signal()

    def __init__(self, tray: QSystemTrayIcon | None = None) -> None:
        super().__init__()
        self._tray = tray or QSystemTrayIcon()

    def show(self, ctx: ReminderContext) -> None:
        self._tray.showMessage("休息提醒", f"你已連續工作 {ctx.work_minutes} 分鐘。")
        self.dismissed.emit()

    def hide(self) -> None:
        return None
