from __future__ import annotations

from PySide6.QtWidgets import QSystemTrayIcon

from src.config import ReminderConfig
from src.reminder.floating import FloatingReminder
from src.reminder.popup import PopupReminder
from src.reminder.toast import ToastReminder


def create_reminder(
    cfg: ReminderConfig, tray: QSystemTrayIcon | None = None
) -> PopupReminder | ToastReminder | FloatingReminder:
    if cfg.method == "toast":
        return ToastReminder(tray)
    if cfg.method == "floating":
        return FloatingReminder(cfg.floating)
    return PopupReminder()
