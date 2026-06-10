from __future__ import annotations

import pytest

from src.config import ReturnSoundConfig
from src.reminder.return_prompt import ReturnPromptDialog
from src.reminder.sound import QtLoopingSoundPlayer


class FakePlayer:
    def __init__(self) -> None:
        self.play_calls: list[str] = []
        self.stop_calls: int = 0

    def play(self, sound_path: str) -> None:
        self.play_calls.append(sound_path)

    def stop(self) -> None:
        self.stop_calls += 1


@pytest.mark.qt
def test_qt_player_play_missing_path_no_crash(qtbot):
    """對不存在路徑呼叫 play() 不崩潰"""
    player = QtLoopingSoundPlayer()
    player.play("not/exist.mp3")  # 不應丟例外


@pytest.mark.qt
def test_qt_player_stop_before_play_no_crash(qtbot):
    """未呼叫 play() 即呼叫 stop() 不崩潰"""
    player = QtLoopingSoundPlayer()
    player.stop()  # 不應丟例外


# --- M1b 新增測試 ---


@pytest.mark.qt
def test_dialog_plays_when_enabled(qtbot):
    """show_prompt() 且 enabled=True 時，player.play() 應以 sound_path 被呼叫"""
    fake = FakePlayer()
    cfg = ReturnSoundConfig(enabled=True, sound_path="x.mp3")
    dialog = ReturnPromptDialog(return_sound=cfg, player=fake)
    qtbot.addWidget(dialog)
    dialog.show_prompt()
    assert fake.play_calls == ["x.mp3"]


@pytest.mark.qt
def test_dialog_silent_when_disabled(qtbot):
    """show_prompt() 且 enabled=False 時，player.play() 不應被呼叫"""
    fake = FakePlayer()
    cfg = ReturnSoundConfig(enabled=False)
    dialog = ReturnPromptDialog(return_sound=cfg, player=fake)
    qtbot.addWidget(dialog)
    dialog.show_prompt()
    assert fake.play_calls == []


@pytest.mark.qt
def test_dialog_stops_on_confirm(qtbot):
    """確認後 player.stop() 應至少被呼叫一次，且 confirmed 訊號發出"""
    fake = FakePlayer()
    cfg = ReturnSoundConfig(enabled=True, sound_path="x.mp3")
    dialog = ReturnPromptDialog(return_sound=cfg, player=fake)
    qtbot.addWidget(dialog)
    dialog.show_prompt()
    with qtbot.waitSignal(dialog.confirmed):
        dialog._on_confirmed()
    assert fake.stop_calls >= 1


@pytest.mark.qt
def test_dialog_close_does_not_stop(qtbot):
    """close() 後對話框仍可見（event.ignore()），且 player.stop() 不應被呼叫"""
    fake = FakePlayer()
    cfg = ReturnSoundConfig(enabled=True, sound_path="x.mp3")
    dialog = ReturnPromptDialog(return_sound=cfg, player=fake)
    qtbot.addWidget(dialog)
    dialog.show_prompt()
    dialog.close()
    assert dialog.isVisible() is True
    assert fake.stop_calls == 0


@pytest.mark.qt
def test_dialog_backward_compatible_no_args(qtbot):
    """ReturnPromptDialog() 無任何參數仍可建構並呼叫 show_prompt()"""
    dialog = ReturnPromptDialog()
    qtbot.addWidget(dialog)
    dialog.show_prompt()  # 不應丟例外
