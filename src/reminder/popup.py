from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from src.types import ReminderContext


class PopupReminder(QDialog):
    dismissed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("休息提醒")
        self.message_label = QLabel("該休息一下了")
        self.media_label = QLabel()
        self.media_label.setScaledContents(True)
        self.video_widget = QVideoWidget()
        self.video_widget.hide()
        self.dismiss_button = QPushButton("我要休息")
        self.dismiss_button.clicked.connect(self._dismiss)

        layout = QVBoxLayout()
        layout.addWidget(self.message_label)
        layout.addWidget(self.media_label)
        layout.addWidget(self.video_widget)
        layout.addWidget(self.dismiss_button)
        self.setLayout(layout)

        self._audio_output = QAudioOutput(self)
        self._media_player = QMediaPlayer(self)
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.setVideoOutput(self.video_widget)
        self._sound_effect = QSoundEffect(self)

    def show(self, ctx: ReminderContext | None = None) -> None:
        if ctx is None:
            super().show()
            return
        self.message_label.setText(f"你已連續工作 {ctx.work_minutes} 分鐘，該休息了。")
        if ctx.media_type == "video":
            self.media_label.hide()
            self.video_widget.show()
            self._media_player.setSource(QUrl.fromLocalFile(ctx.media_path))
            self._media_player.play()
        else:
            self._media_player.stop()
            self.video_widget.hide()
            self.media_label.show()
            self.media_label.setPixmap(QPixmap(ctx.media_path))

        if ctx.sound_path:
            self._sound_effect.setSource(QUrl.fromLocalFile(ctx.sound_path))
            self._sound_effect.play()

        super().show()

    def hide(self) -> None:
        self._media_player.stop()
        super().hide()

    def _dismiss(self) -> None:
        self.dismissed.emit()
        self.hide()


def _as_widget(reminder: PopupReminder) -> QWidget:
    return reminder
