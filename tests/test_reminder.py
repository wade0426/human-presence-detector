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


def test_load_pixmap_missing_path_returns_placeholder() -> None:
    from src.reminder.media import load_pixmap

    pixmap = load_pixmap("nonexistent_file.png")

    assert not pixmap.isNull()


def test_load_pixmap_empty_path_returns_placeholder() -> None:
    from src.reminder.media import load_pixmap

    pixmap = load_pixmap("")

    assert not pixmap.isNull()


def test_safe_sound_url_empty_returns_none() -> None:
    from src.reminder.media import safe_sound_url

    assert safe_sound_url("") is None
    assert safe_sound_url("nonexistent.wav") is None


def test_popup_snooze_mode_shows_snooze_button(qtbot: pytest.QtBot) -> None:
    from PySide6.QtWidgets import QPushButton

    from src.reminder.popup import PopupReminder

    context = ReminderContext(
        work_minutes=30,
        media_path="",
        media_type="image",
        sound_path="",
        reset_mode="snooze",
        snooze_minutes=5,
    )
    reminder = PopupReminder()
    qtbot.addWidget(reminder)

    reminder.show(context)

    texts = [button.text() for button in reminder.findChildren(QPushButton)]
    assert any("5" in text for text in texts)


def test_floating_reminder_emits_dismissed_on_click(qtbot: pytest.QtBot) -> None:
    from src.reminder.floating import FloatingReminder

    reminder = FloatingReminder(FloatingConfig(position="top-right"))
    qtbot.addWidget(reminder)
    reminder.show(_image_context())

    with qtbot.waitSignal(reminder.dismissed, timeout=3000):
        qtbot.mouseClick(reminder, Qt.MouseButton.LeftButton)
