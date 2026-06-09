from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from src.ui.strings import RETURN_BODY, RETURN_CONFIRM, RETURN_TITLE


class ReturnPromptDialog(QDialog):
    """'Welcome back' confirmation dialog shown after a complete rest.

    Cannot be dismissed by closing the window — only the confirm button works.
    Until confirmed, the timer stays at IDLE and does not advance.
    """

    confirmed = Signal()

    def __init__(self, parent: object = None) -> None:
        super().__init__()
        self.setWindowTitle(RETURN_TITLE)

        self._message_label = QLabel(RETURN_BODY)
        self._message_label.setWordWrap(True)

        self._confirm_btn = QPushButton(RETURN_CONFIRM)
        self._confirm_btn.clicked.connect(self._on_confirmed)

        layout = QVBoxLayout()
        layout.addWidget(self._message_label)
        layout.addWidget(self._confirm_btn)
        self.setLayout(layout)

    def show_prompt(self, rest_minutes: int | None = None) -> None:
        """Display the dialog, optionally showing how many minutes were rested."""
        if rest_minutes is not None:
            self._message_label.setText(f"{RETURN_BODY}（已休息 {rest_minutes} 分鐘）")
        else:
            self._message_label.setText(RETURN_BODY)
        self.show()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Ignore close events — dialog must stay open until user confirms."""
        event.ignore()

    def _on_confirmed(self) -> None:
        self.confirmed.emit()
        self.accept()
