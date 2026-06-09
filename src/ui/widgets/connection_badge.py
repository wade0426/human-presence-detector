from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.app.connection_state import ConnectionState, icon_key, severity
from src.ui.strings import CONN_TEXT

_ICON_CHARS: dict[str, str] = {
    "conn-idle": "○",
    "conn-connecting": "◌",
    "conn-connected": "●",
    "conn-reconnecting": "↻",
    "conn-no-signal": "⊘",
    "conn-stream-error": "⚠",  # ★ 新增：影像異常
    "conn-error": "✕",
}


class ConnectionBadge(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_label = QLabel("○")
        self._text_label = QLabel("待機")
        self._current_state = ConnectionState.IDLE

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label)

    def set_state(self, state: ConnectionState) -> None:
        self._current_state = state
        role = severity(state)
        text = CONN_TEXT.get(state, "")
        icon = _ICON_CHARS.get(icon_key(state), "?")
        self._icon_label.setText(icon)
        self._text_label.setText(text)
        for label in (self._icon_label, self._text_label):
            label.setProperty("role", role)
            label.style().unpolish(label)
            label.style().polish(label)
