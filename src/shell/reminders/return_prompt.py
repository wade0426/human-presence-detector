from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from src.infra.config import ReturnSoundConfig
from src.shell.reminders.sound import LoopingSoundPlayer, QtLoopingSoundPlayer
from src.shell.strings import RETURN_BODY, RETURN_CONFIRM, RETURN_TITLE


class ReturnPromptDialog(QDialog):
    """'Welcome back' confirmation dialog shown after a complete rest.

    Cannot be dismissed by closing the window — only the confirm button works.
    Until confirmed, the timer stays at IDLE and does not advance.
    """

    confirmed = Signal()

    def __init__(
        self,
        *,
        return_sound: ReturnSoundConfig | None = None,
        player: LoopingSoundPlayer | None = None,
        parent: object = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(RETURN_TITLE)

        self._return_sound = return_sound
        self._player: LoopingSoundPlayer = (
            player if player is not None else QtLoopingSoundPlayer(self)
        )

        self._message_label = QLabel(RETURN_BODY)
        self._message_label.setWordWrap(True)

        self._confirm_btn = QPushButton(RETURN_CONFIRM)
        self._confirm_btn.clicked.connect(self._on_confirmed)

        layout = QVBoxLayout()
        layout.addWidget(self._message_label)
        layout.addWidget(self._confirm_btn)
        self.setLayout(layout)

    def show_prompt(self, *_unused: object) -> None:
        """Display the dialog with the fixed return message."""
        self._message_label.setText(RETURN_BODY)
        self.show()
        if self._return_sound is not None and self._return_sound.enabled:
            self._player.play(self._return_sound.sound_path)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Ignore close events — dialog must stay open until user confirms."""
        event.ignore()

    def _on_confirmed(self) -> None:
        self._player.stop()
        self.confirmed.emit()
        self.accept()
