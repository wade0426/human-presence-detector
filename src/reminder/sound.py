from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QObject
from PySide6.QtMultimedia import QSoundEffect

from src.reminder.media import safe_sound_url


class LoopingSoundPlayer(Protocol):
    def play(self, sound_path: str) -> None: ...   # 啟動循環播放；路徑無效則安靜略過
    def stop(self) -> None: ...                     # 停止播放（可重複呼叫）


class QtLoopingSoundPlayer:
    def __init__(self, parent: QObject | None = None) -> None:
        self._effect = QSoundEffect(parent)
        self._effect.setLoopCount(QSoundEffect.Loop.Infinite.value)

    def play(self, sound_path: str) -> None:
        url = safe_sound_url(sound_path)
        if url is None:
            return
        self._effect.setSource(url)
        self._effect.play()

    def stop(self) -> None:
        self._effect.stop()
