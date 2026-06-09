from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from src.duration_format import format_clock
from src.types import TimerSnapshot, TimerState
from src.ui.strings import STATE_TEXT


class StatusStrip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state_label = QLabel("待機")
        self._time_label = QLabel("00:00")
        self._progress = QProgressBar()
        self._progress.setMaximumHeight(6)
        self._progress.setTextVisible(False)

        layout = QHBoxLayout(self)
        layout.addWidget(self._state_label)
        layout.addWidget(self._time_label)
        layout.addWidget(self._progress, stretch=1)

    def update_snapshot(
        self,
        snap: TimerSnapshot,
        work_threshold_sec: float,
        reminding_mode: str = "overtime",  # "overtime" | "work_and_reminder"
    ) -> None:
        """更新狀態列顯示。

        時間標籤規則（依優先順序）：
        1. RESTING → 顯示休息倒數或已休息時間
        2. reminder_active=True（REMINDING 或從 REMINDING 暫停的 SUSPENDED）：
           - "overtime"          → "超時 MM:SS"（超時 = overtime_sec）
           - "work_and_reminder" → "工作 MM:SS / 提醒 MM:SS"
           - 未知 mode           → 退回 "overtime" 行為
        3. 其餘 → format_clock(work_elapsed_sec)
        """
        self._state_label.setText(STATE_TEXT.get(snap.state, ""))

        if snap.state == TimerState.RESTING:
            # FIXED 模式：rest_remaining_sec > 0 顯示倒數；PRESENCE 模式：顯示已休息時間
            if snap.rest_remaining_sec > 0:
                self._time_label.setText(format_clock(snap.rest_remaining_sec))
            else:
                self._time_label.setText(format_clock(snap.rest_elapsed_sec))
            # 休息中進度條不具意義，設為 0
            self._progress.setMaximum(max(1, int(work_threshold_sec)))
            self._progress.setValue(0)
        elif snap.reminder_active:
            # REMINDING 或從 REMINDING 暫停的 SUSPENDED
            if reminding_mode == "work_and_reminder":
                work_str = format_clock(snap.work_elapsed_sec)
                overtime_str = format_clock(snap.overtime_sec)
                self._time_label.setText(f"工作 {work_str} / 提醒 {overtime_str}")
            else:
                # "overtime" 或未知模式（退回 overtime 行為）
                self._time_label.setText(f"超時 {format_clock(snap.overtime_sec)}")
            # 提醒中進度條滿格
            maximum = max(1, int(work_threshold_sec))
            self._progress.setMaximum(maximum)
            self._progress.setValue(maximum)
        else:
            elapsed = snap.work_elapsed_sec
            self._time_label.setText(format_clock(elapsed))
            maximum = max(1, int(work_threshold_sec))
            self._progress.setMaximum(maximum)
            self._progress.setValue(min(int(elapsed), maximum))
