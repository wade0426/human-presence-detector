"""ROI 內有人/無人徽章（自 src/ui/widgets/presence_badge.py 移植）。"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.shell.strings import PRESENCE_NO, PRESENCE_YES


class PresenceBadge(QWidget):
    """Shows whether a person is detected in the ROI (green dot = present, grey = absent)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_label = QLabel("○")
        self._text_label = QLabel(PRESENCE_NO)
        self._present = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label)

        # Initial state: no person
        self._apply(False)

    def set_present(self, present: bool) -> None:
        if self._present == present:
            return
        self._present = present
        self._apply(present)

    def _apply(self, present: bool) -> None:
        if present:
            self._icon_label.setText("●")
            self._text_label.setText(PRESENCE_YES)
            role = "success"
        else:
            self._icon_label.setText("○")
            self._text_label.setText(PRESENCE_NO)
            role = "muted"

        for label in (self._icon_label, self._text_label):
            label.setProperty("role", role)
            label.style().unpolish(label)
            label.style().polish(label)
