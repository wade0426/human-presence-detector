from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.duration_format import format_duration_zh
from src.ui.strings import TODAY_EMPTY, TODAY_REST_LABEL, TODAY_WORK_LABEL


class TodaySummaryView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._work_label = QLabel(TODAY_EMPTY)
        self._rest_label = QLabel("")

        layout = QHBoxLayout(self)
        layout.addWidget(self._work_label)
        layout.addWidget(self._rest_label)

    def set_today(self, work_seconds: int, rest_count: int) -> None:
        """更新今日統計顯示。

        - work_seconds > 0 或 rest_count > 0：使用 format_duration_zh 顯示動態時長
        - 兩者皆為 0：顯示空狀態文案（TODAY_EMPTY）
        """
        if work_seconds <= 0 and rest_count <= 0:
            self._work_label.setText(TODAY_EMPTY)
            self._rest_label.setText("")
            return

        duration_text = format_duration_zh(float(work_seconds))
        self._work_label.setText(f"{TODAY_WORK_LABEL}：{duration_text}")
        self._rest_label.setText(f"{TODAY_REST_LABEL}：{rest_count} 次")

    def set_summary(self, summary: object | None) -> None:
        """向後相容介面（接受 TodaySummary 或 None）。

        呼叫端應優先使用 set_today()；此方法保留以避免破壞現有程式碼。
        """
        if summary is None:
            self.set_today(0, 0)
            return
        # 透過 duck-typing 讀取 work_seconds / rest_count
        work_seconds: int = getattr(summary, "work_seconds", 0)
        rest_count: int = getattr(summary, "rest_count", 0)
        self.set_today(work_seconds, rest_count)
