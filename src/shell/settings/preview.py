"""路徑欄位與音檔試聽（自舊 ``src/ui/settings.py`` 抽出，FR-2.7／FR-3.1～3.7）。

- :class:`PathField`：輸入框＋瀏覽按鈕（瀏覽過濾可注入）。
- :class:`SoundPathField`：音檔欄位（瀏覽帶音訊過濾＋試聽按鈕、喇叭圖示）。
- :class:`SoundPreviewController`：共享播放器的試聽狀態機——同時僅一個試聽、
  視窗關閉自動停止、無效路徑／解碼錯誤以 signal 通知（hint 呈現由視窗負責）。
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QStyle,
    QWidget,
)

from src.shell import strings
from src.shell.reminders.sound import LoopingSoundPlayer, QtSoundPlayer

# FR-3.1：試聽按鈕的喇叭圖示資產（模組定錨到 repo 根目錄）。
_TRUMPET_ICON_PATH = Path(__file__).resolve().parents[3] / "data" / "assets" / "trumpet.png"


def _speaker_icon(widget: QWidget) -> QIcon:
    """FR-3.1：優先使用出貨資產 trumpet.png；缺檔或無法載入時退回內建喇叭圖示。"""
    if _TRUMPET_ICON_PATH.exists():
        icon = QIcon(str(_TRUMPET_ICON_PATH))
        if not icon.isNull():
            return icon
    return widget.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)


class PathField(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        file_filter: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._file_filter = file_filter or strings.FILE_DIALOG_ALL_FILES
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.line_edit = QLineEdit()
        self.browse_button = QPushButton("瀏覽")
        self.browse_button.clicked.connect(self._browse)

        layout.addWidget(self.line_edit)
        layout.addWidget(self.browse_button)

    def _browse(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self, strings.FILE_DIALOG_TITLE, "", self._file_filter
        )
        if chosen:
            self.line_edit.setText(chosen)


class SoundPathField(PathField):
    """音檔欄位：輸入框＋瀏覽＋試聽同列（FR-3.1）；瀏覽帶音訊過濾（FR-2.7）。"""

    preview_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, file_filter=strings.SOUND_FILE_FILTER)
        # FR-3.1：試聽按鈕帶喇叭圖示（非純文字）；播放中換成停止圖示。
        self._play_icon = _speaker_icon(self)
        self._stop_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        self.preview_button = QPushButton(strings.SOUND_PREVIEW_PLAY)
        self.preview_button.setIcon(self._play_icon)
        self.preview_button.clicked.connect(self.preview_requested.emit)
        inner_layout = self.layout()
        if inner_layout is not None:
            inner_layout.addWidget(self.preview_button)

    def set_previewing(self, previewing: bool) -> None:
        self.preview_button.setText(
            strings.SOUND_PREVIEW_STOP if previewing else strings.SOUND_PREVIEW_PLAY
        )
        self.preview_button.setIcon(self._stop_icon if previewing else self._play_icon)


class SoundPreviewController(QObject):
    """共享播放器的試聽控制：同時僅允許一個試聽（FR-3.2～3.7）。

    註冊欄位後接手其 ``preview_requested``；播放成功發 ``started``（清除錯誤
    hint 用）、路徑無效或解碼失敗發 ``error_occurred``，hint 呈現由視窗處理。
    """

    started = Signal(str)         # 欄位 key：成功開始試聽
    error_occurred = Signal(str)  # 欄位 key：路徑無效或播放錯誤

    def __init__(
        self,
        player: LoopingSoundPlayer | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._player: LoopingSoundPlayer = player if player is not None else QtSoundPlayer(self)
        self._fields: dict[str, SoundPathField] = {}
        self._active_key: str | None = None
        # FR-3.6：最後一次啟動試聽的欄位 key——QMediaPlayer 可能先發
        # StoppedState（清掉 active_key）再發 errorOccurred，錯誤通知
        # 需要回退到這個 key 才不會漏標。
        self._started_key: str | None = None
        self._wire_player_signals()

    @property
    def active_key(self) -> str | None:
        return self._active_key

    def register(self, key: str, field: SoundPathField) -> None:
        self._fields[key] = field
        field.preview_requested.connect(partial(self.toggle, key))

    def toggle(self, key: str) -> None:
        field = self._fields.get(key)
        if field is None:
            return

        if self._active_key == key:
            # FR-3.2：播放中再按 → 立即停止。
            self.stop()
            return

        # FR-3.4：同時僅允許一個試聽。
        self.stop()

        # FR-3.3：以欄位目前輸入值為準（未儲存）。
        path = field.line_edit.text()
        if not path or not Path(path).exists():
            # FR-3.6：不播放、不崩潰，交由視窗顯示錯誤 hint。
            self.error_occurred.emit(key)
            return

        self.started.emit(key)
        self._started_key = key
        self._player.play(path)
        self._active_key = key
        field.set_previewing(True)

    def stop(self) -> None:
        key = self._active_key
        if key is None:
            return
        self._active_key = None
        self._player.stop()
        field = self._fields.get(key)
        if field is not None:
            field.set_previewing(False)

    def _wire_player_signals(self) -> None:
        """接上共享播放器的播放結束／錯誤通知（僅 QtSoundPlayer 具備）。

        注入的 FakePlayer 等替身沒有底層 QMediaPlayer，安靜略過。
        """
        inner = getattr(self._player, "_player", None)
        if isinstance(inner, QMediaPlayer):
            inner.playbackStateChanged.connect(self._on_playback_state)
            inner.errorOccurred.connect(self._on_error)

    def _on_playback_state(self, state: QMediaPlayer.PlaybackState) -> None:
        # 單次播放自然結束 → 按鈕復原為「試聽」。
        if state != QMediaPlayer.PlaybackState.StoppedState:
            return
        key = self._active_key
        if key is None:
            return
        self._active_key = None
        field = self._fields.get(key)
        if field is not None:
            field.set_previewing(False)

    def _on_error(self, _error: QMediaPlayer.Error, _error_string: str) -> None:
        # FR-3.6：無法解碼等播放錯誤 → 按鈕復原、通知視窗標示錯誤欄位。
        key = self._active_key or self._started_key
        if key is None:
            return
        self._active_key = None
        field = self._fields.get(key)
        if field is not None:
            field.set_previewing(False)
        self.error_occurred.emit(key)
