from __future__ import annotations

import logging
from typing import Protocol

from PySide6.QtCore import QObject
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from src.shell.reminders.media import safe_sound_url

logger = logging.getLogger(__name__)


class LoopingSoundPlayer(Protocol):
    def play(self, sound_path: str) -> None: ...   # 啟動循環播放；路徑無效則安靜略過
    def stop(self) -> None: ...                     # 停止播放（可重複呼叫）


class QtSoundPlayer:
    """QMediaPlayer + QAudioOutput 音效播放器，預設單次播放。

    - 可解碼 mp3 / wav 等常見格式（FR-2.1、FR-2.2）。
    - 播放錯誤（檔案損壞、格式不支援等）以 logging 記錄、靜默不播、不崩潰（FR-2.6）。
    - 空路徑 / 檔案不存在沿用 ``safe_sound_url`` 的容錯：安靜略過。
    """

    def __init__(self, parent: QObject | None = None, *, loops: int = 1) -> None:
        self._audio_output = QAudioOutput(parent)
        self._player = QMediaPlayer(parent)
        self._player.setAudioOutput(self._audio_output)
        self._player.setLoops(loops)
        self._player.errorOccurred.connect(self._on_error)

    def play(self, sound_path: str) -> None:
        url = safe_sound_url(sound_path)
        if url is None:
            return
        self._player.stop()
        self._player.setSource(url)
        self._player.play()

    def stop(self) -> None:
        self._player.stop()

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def _on_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        logger.warning(
            "Sound playback error (%s): %s - source=%s",
            error.name,
            error_string,
            self._player.source().toLocalFile(),
        )


class QtLoopingSoundPlayer(QtSoundPlayer):
    """循環播放版本：歡迎回來提示音用，播放至 stop() 為止（FR-2.3）。"""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent, loops=int(QMediaPlayer.Loops.Infinite.value))
