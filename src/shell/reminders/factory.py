from __future__ import annotations

from PySide6.QtWidgets import QSystemTrayIcon

from src.infra.config import ReminderConfig
from src.shell.reminders.floating import FloatingReminder
from src.shell.reminders.popup import PopupReminder
from src.shell.reminders.toast import ToastReminder


def create_reminder(
    cfg: ReminderConfig,
    tray: QSystemTrayIcon | None = None,
    *,
    rest_count_mode: str = "fixed",
) -> PopupReminder | ToastReminder | FloatingReminder:
    if cfg.method == "toast":
        return ToastReminder(tray)
    if cfg.method == "floating":
        return FloatingReminder(cfg.floating)
    return PopupReminder(presence_mode=rest_count_mode == "presence")
