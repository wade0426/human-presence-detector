from __future__ import annotations

import logging
from pathlib import Path

import pytest
from PySide6.QtMultimedia import QMediaPlayer

from src.config import ReturnSoundConfig
from src.reminder.return_prompt import ReturnPromptDialog
from src.reminder.sound import QtLoopingSoundPlayer, QtSoundPlayer


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


# --- 需求二 FR-2.1～2.6：QMediaPlayer 替換 ---


@pytest.mark.qt
def test_qt_looping_player_uses_qmediaplayer_with_infinite_loops(qtbot):
    """FR-2.2/2.3：底層為 QMediaPlayer 且設定無限循環"""
    player = QtLoopingSoundPlayer()
    assert isinstance(player._player, QMediaPlayer)
    assert player._player.loops() == QMediaPlayer.Loops.Infinite.value


@pytest.mark.qt
def test_qt_sound_player_defaults_to_single_shot(qtbot):
    """QtSoundPlayer 預設單次播放（popup 提醒音與設定頁試聽重用）"""
    player = QtSoundPlayer()
    assert isinstance(player._player, QMediaPlayer)
    assert player._player.loops() == 1


@pytest.mark.qt
def test_qt_player_logs_error_for_undecodable_file(qtbot, tmp_path: Path, caplog):
    """FR-2.6：存在但無法解碼的檔案 → play() 不拋例外，且 log 記錄含來源路徑"""
    bad = tmp_path / "garbage.mp3"
    bad.write_bytes(b"this is definitely not valid mp3 audio data" * 64)
    player = QtLoopingSoundPlayer()
    with caplog.at_level(logging.WARNING, logger="src.reminder.sound"):
        player.play(str(bad))  # 不應丟例外
        qtbot.waitUntil(
            lambda: any("garbage.mp3" in record.getMessage() for record in caplog.records),
            timeout=5000,
        )


@pytest.mark.qt
def test_qt_player_is_playing_false_when_stopped(qtbot):
    """is_playing() 在未播放/停止時回傳 False"""
    player = QtSoundPlayer()
    assert player.is_playing() is False
    player.stop()
    assert player.is_playing() is False


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
