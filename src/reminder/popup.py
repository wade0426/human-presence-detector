from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.reminder.media import is_playable_video, load_pixmap, safe_sound_url
from src.types import ReminderContext
from src.ui import strings


class PopupReminder(QDialog):
    dismissed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(strings.REMIND_TITLE)
        self.message_label = QLabel(strings.REMIND_TITLE)
        self.media_label = QLabel()
        self.media_label.setScaledContents(True)
        self.video_widget = QVideoWidget()
        self.video_widget.hide()
        self.dismiss_button = QPushButton(strings.REMIND_START_REST)
        self.dismiss_button.clicked.connect(self._dismiss)
        self.close_button = QPushButton(strings.REMIND_CLOSE)
        self.close_button.clicked.connect(self.hide)
        self._button_layout = QHBoxLayout()

        layout = QVBoxLayout()
        layout.addWidget(self.message_label)
        layout.addWidget(self.media_label)
        layout.addWidget(self.video_widget)
        self._button_layout.addWidget(self.dismiss_button)
        self._button_layout.addWidget(self.close_button)
        layout.addLayout(self._button_layout)
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
        self.message_label.setText(strings.REMIND_BODY.format(minutes=ctx.work_minutes))
        self._setup_buttons(ctx)
        if ctx.media_type == "video" and is_playable_video(ctx.media_path):
            self.media_label.hide()
            self.video_widget.show()
            self._media_player.setSource(QUrl.fromLocalFile(ctx.media_path))
            self._media_player.play()
        else:
            self._media_player.stop()
            self.video_widget.hide()
            self.media_label.show()
            self.media_label.setPixmap(
                load_pixmap(ctx.media_path, fallback_text=strings.REMIND_TITLE)
            )

        sound_url = safe_sound_url(ctx.sound_path)
        if sound_url is not None:
            self._sound_effect.setSource(sound_url)
            self._sound_effect.play()

        super().show()

    def hide(self) -> None:
        self._media_player.stop()
        super().hide()

    def _dismiss(self) -> None:
        self.dismissed.emit()
        self.hide()

    def _setup_buttons(self, ctx: ReminderContext) -> None:
        if ctx.reset_mode == "snooze":
            self.dismiss_button.setText(strings.REMIND_SNOOZE.format(minutes=ctx.snooze_minutes))
        elif ctx.reset_mode == "dismiss":
            self.dismiss_button.setText(strings.REMIND_START_REST)
        else:
            self.dismiss_button.setText(strings.REMIND_ACK)
        self.close_button.setText(strings.REMIND_CLOSE)


def _as_widget(reminder: PopupReminder) -> QWidget:
    return reminder
