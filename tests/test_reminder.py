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


def test_popup_reminder_emits_start_rest_when_button_clicked(qtbot: pytest.QtBot) -> None:
    from src.reminder.popup import PopupReminder

    reminder = PopupReminder()
    qtbot.addWidget(reminder)
    reminder.show(_image_context())

    with qtbot.waitSignal(reminder.start_rest, timeout=3000):
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



def test_floating_reminder_emits_dismissed_on_click(qtbot: pytest.QtBot) -> None:
    from src.reminder.floating import FloatingReminder

    reminder = FloatingReminder(FloatingConfig(position="top-right"))
    qtbot.addWidget(reminder)
    reminder.show(_image_context())

    with qtbot.waitSignal(reminder.dismissed, timeout=3000):
        qtbot.mouseClick(reminder, Qt.MouseButton.LeftButton)


# ---------------------------------------------------------------------------
# T8 Tests — §4.14 work_minutes float：FloatingReminder 倒數秒數
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_floating_reminder_countdown_fractional_minutes(qtbot: pytest.QtBot) -> None:
    """§4.14：work_minutes=0.1 → 倒數 6 秒（round 而非截斷或浮點殘差）。"""
    from src.reminder.floating import FloatingReminder

    reminder = FloatingReminder(FloatingConfig(position="top-right"))
    qtbot.addWidget(reminder)
    ctx = ReminderContext(work_minutes=0.1, media_path="", media_type="image", sound_path="")

    reminder.show(ctx)

    assert reminder._remaining == 6
    assert isinstance(reminder._remaining, int)
    reminder.hide()


@pytest.mark.qt
def test_floating_reminder_countdown_float_minutes(qtbot: pytest.QtBot) -> None:
    """§4.14：work_minutes=25.5 → 倒數 1530 秒。"""
    from src.reminder.floating import FloatingReminder

    reminder = FloatingReminder(FloatingConfig(position="top-right"))
    qtbot.addWidget(reminder)
    ctx = ReminderContext(work_minutes=25.5, media_path="", media_type="image", sound_path="")

    reminder.show(ctx)

    assert reminder._remaining == 1530
    reminder.hide()


# ---------------------------------------------------------------------------
# M7 Tests — PopupReminder single button, ReturnPromptDialog
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_popup_reminder_has_single_action_button(qtbot: pytest.QtBot) -> None:
    """PopupReminder must have exactly one action button with text '\u958b\u59cb\u4f11\u606f'."""
    from src.reminder.popup import PopupReminder
    from src.ui.strings import REMIND_START_REST

    reminder = PopupReminder()
    qtbot.addWidget(reminder)

    assert reminder.dismiss_button.text() == REMIND_START_REST
    # Must NOT have a close_button attribute
    assert not hasattr(reminder, "close_button")


@pytest.mark.qt
def test_popup_reminder_start_rest_signal_and_hide_on_button_click(qtbot: pytest.QtBot) -> None:
    """Click '\u958b\u59cb\u4f11\u606f' → emits start_rest signal and hides window."""
    from src.reminder.popup import PopupReminder

    reminder = PopupReminder()
    qtbot.addWidget(reminder)
    reminder.show(_image_context())
    assert reminder.isVisible()

    with qtbot.waitSignal(reminder.start_rest, timeout=3000):
        qtbot.mouseClick(reminder.dismiss_button, Qt.MouseButton.LeftButton)

    assert not reminder.isVisible()


@pytest.mark.qt
def test_return_prompt_dialog_confirmed_signal(qtbot: pytest.QtBot) -> None:
    """Click '\u958b\u59cb\u65b0\u4e00\u8f2a' → emits confirmed signal."""
    from src.reminder.return_prompt import ReturnPromptDialog

    dialog = ReturnPromptDialog()
    qtbot.addWidget(dialog)
    dialog.show_prompt()

    with qtbot.waitSignal(dialog.confirmed, timeout=3000):
        qtbot.mouseClick(dialog._confirm_btn, Qt.MouseButton.LeftButton)


@pytest.mark.qt
def test_return_prompt_dialog_cannot_be_closed(qtbot: pytest.QtBot) -> None:
    """ReturnPromptDialog.close() must keep the dialog visible (closeEvent ignored)."""
    from src.reminder.return_prompt import ReturnPromptDialog

    dialog = ReturnPromptDialog()
    qtbot.addWidget(dialog)
    dialog.show_prompt()
    assert dialog.isVisible()

    dialog.close()

    assert dialog.isVisible()


@pytest.mark.qt
def test_return_prompt_dialog_show_prompt_keeps_plain_body_text(qtbot: pytest.QtBot) -> None:
    from src.reminder.return_prompt import ReturnPromptDialog
    from src.ui.strings import RETURN_BODY

    dialog = ReturnPromptDialog()
    qtbot.addWidget(dialog)

    dialog.show_prompt()

    assert dialog._message_label.text() == RETURN_BODY


@pytest.mark.qt
def test_return_prompt_dialog_does_not_render_reminder_context_repr(
    qtbot: pytest.QtBot,
) -> None:
    from src.reminder.return_prompt import ReturnPromptDialog

    dialog = ReturnPromptDialog()
    qtbot.addWidget(dialog)

    dialog.show_prompt(
        ReminderContext(
            work_minutes=0,
            media_path="data/assets/rest_placeholder.png",
            media_type="image",
            sound_path="",
        )
    )

    assert "ReminderContext(" not in dialog._message_label.text()
    assert "work_minutes=" not in dialog._message_label.text()


# ---------------------------------------------------------------------------
# 需求二 FR-2.2/2.4/2.5 — PopupReminder 提醒音改用獨立 QMediaPlayer、hide 停音
# ---------------------------------------------------------------------------


class _FakeSoundPlayer:
    def __init__(self) -> None:
        self.play_calls: list[str] = []
        self.stop_calls: int = 0

    def play(self, sound_path: str) -> None:
        self.play_calls.append(sound_path)

    def stop(self) -> None:
        self.stop_calls += 1


@pytest.mark.qt
def test_popup_sound_player_separate_from_video_player(qtbot: pytest.QtBot) -> None:
    """FR-2.2/2.4：popup 提醒音改用第二組 QMediaPlayer，與影片播放器分離且單次播放"""
    from src.reminder.popup import PopupReminder
    from src.reminder.sound import QtSoundPlayer

    reminder = PopupReminder()
    qtbot.addWidget(reminder)

    assert not hasattr(reminder, "_sound_effect")
    assert isinstance(reminder._sound_player, QtSoundPlayer)
    assert reminder._sound_player._player is not reminder._media_player
    assert reminder._sound_player._player.loops() == 1


@pytest.mark.qt
def test_popup_show_plays_sound_via_player(qtbot: pytest.QtBot) -> None:
    """show() 時提醒音路徑透過 sound player 播放（容錯由 player 處理）"""
    from src.reminder.popup import PopupReminder

    reminder = PopupReminder()
    qtbot.addWidget(reminder)
    fake = _FakeSoundPlayer()
    reminder._sound_player = fake  # type: ignore[assignment]

    ctx = ReminderContext(work_minutes=30, media_path="", media_type="image", sound_path="x.mp3")
    reminder.show(ctx)

    assert fake.play_calls == ["x.mp3"]
    reminder.hide()


@pytest.mark.qt
def test_popup_hide_stops_sound_player(qtbot: pytest.QtBot) -> None:
    """FR-2.5：hide() 一併停止提醒音（不只停影片）"""
    from src.reminder.popup import PopupReminder

    reminder = PopupReminder()
    qtbot.addWidget(reminder)
    fake = _FakeSoundPlayer()
    reminder._sound_player = fake  # type: ignore[assignment]

    reminder.show(_image_context())
    reminder.hide()

    assert fake.stop_calls >= 1


@pytest.mark.qt
def test_popup_hide_leaves_real_sound_player_stopped(qtbot: pytest.QtBot) -> None:
    """FR-2.5：hide() 後實際音效播放器處於停止狀態"""
    from PySide6.QtMultimedia import QMediaPlayer

    from src.reminder.popup import PopupReminder

    reminder = PopupReminder()
    qtbot.addWidget(reminder)

    reminder.show(_image_context())
    reminder.hide()

    state = reminder._sound_player._player.playbackState()
    assert state == QMediaPlayer.PlaybackState.StoppedState
    assert reminder._sound_player.is_playing() is False


@pytest.mark.qt
def test_popup_reminder_show_with_no_reset_mode_context(qtbot: pytest.QtBot) -> None:
    """ReminderContext without reset_mode/snooze_minutes can call show() without error."""
    from src.reminder.popup import PopupReminder

    reminder = PopupReminder()
    qtbot.addWidget(reminder)

    ctx = ReminderContext(work_minutes=30, media_path="", media_type="image", sound_path="")
    # Should not raise
    reminder.show(ctx)
    reminder.hide()
