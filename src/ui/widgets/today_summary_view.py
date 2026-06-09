from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.logging_store import TodaySummary
from src.ui.strings import TODAY_EMPTY, TODAY_REST_LABEL, TODAY_WORK_LABEL


class TodaySummaryView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._work_label = QLabel(TODAY_EMPTY)
        self._rest_label = QLabel("")

        layout = QHBoxLayout(self)
        layout.addWidget(self._work_label)
        layout.addWidget(self._rest_label)

    def set_summary(self, summary: TodaySummary | None) -> None:
        if summary is None or (summary.work_seconds == 0 and summary.rest_count == 0):
            self._work_label.setText(TODAY_EMPTY)
            self._rest_label.setText("")
            return

        minutes = summary.work_seconds // 60
        self._work_label.setText(f"{TODAY_WORK_LABEL}：{minutes} 分鐘")
        self._rest_label.setText(f"{TODAY_REST_LABEL}：{summary.rest_count} 次")
