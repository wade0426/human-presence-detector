from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSystemTrayIcon

from src.config import FloatingConfig, ReminderConfig
from src.types import ReminderContext


def _image_context() -> ReminderContext:
    return ReminderContext(
        work_minutes=45,
        media_path=str(Path("data/assets/rest_placeholder.png")),
        media_type="image",
        sound_path="",
    )


def test_create_reminder_returns_popup(qtbot: pytest.QtBot) -> None:
    from src.reminder.factory import create_reminder
    from src.reminder.popup import PopupReminder

    reminder = create_reminder(ReminderConfig(method="popup"))
    qtbot.addWidget(reminder)

    assert isinstance(reminder, PopupReminder)


def test_create_reminder_returns_toast(qtbot: pytest.QtBot) -> None:
    from src.reminder.factory import create_reminder
    from src.reminder.toast import ToastReminder

    tray = QSystemTrayIcon()
    reminder = create_reminder(ReminderConfig(method="toast"), tray=tray)

    assert isinstance(reminder, ToastReminder)


def test_create_reminder_returns_floating(qtbot: pytest.QtBot) -> None:
    from src.reminder.factory import create_reminder
    from src.reminder.floating import FloatingReminder

    reminder = create_reminder(
        ReminderConfig(method="floating", floating=FloatingConfig(position="top-right"))
    )
    qtbot.addWidget(reminder)

    assert isinstance(reminder, FloatingReminder)


def test_popup_reminder_show_image_does_not_crash(qtbot: pytest.QtBot) -> None:
    from src.reminder.popup import PopupReminder

    reminder = PopupReminder()
    qtbot.addWidget(reminder)

    reminder.show(_image_context())

    assert reminder.isVisible()
    reminder.hide()


def test_popup_reminder_emits_dismissed_when_button_clicked(qtbot: pytest.QtBot) -> None:
    from src.reminder.popup import PopupReminder

    reminder = PopupReminder()
    qtbot.addWidget(reminder)
    reminder.show(_image_context())

    with qtbot.waitSignal(reminder.dismissed, timeout=3000):
        qtbot.mouseClick(reminder.dismiss_button, Qt.MouseButton.LeftButton)
