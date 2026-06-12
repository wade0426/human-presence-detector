"""狀態列（自 src/ui/widgets/status_strip.py 移植；新增 REST_PENDING 顯示）。"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from src.core.events import TimerSnapshot, TimerState
from src.duration_format import format_clock
from src.shell.strings import REST_PENDING_DWELL, STATE_TEXT


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
        1. REST_PENDING → 「已等待 mm:ss」（滯留時長；spec §9 新增）
        2. RESTING → 顯示休息倒數或已休息時間
        3. reminder_active=True（REMINDING 或從 REMINDING 暫停的 SUSPENDED）：
           - "overtime"          → "超時 MM:SS"（超時 = overtime_sec）
           - "work_and_reminder" → "工作 MM:SS / 提醒 MM:SS"
           - 未知 mode           → 退回 "overtime" 行為
        4. 其餘 → format_clock(work_elapsed_sec)
        """
        self._state_label.setText(STATE_TEXT.get(snap.state.value, ""))
        maximum = max(1, int(work_threshold_sec))
        self._progress.setMaximum(maximum)

        if snap.state is TimerState.REST_PENDING:
            # 等待離席：顯示滯留時長；提醒仍在升級階梯上 → 進度條滿格
            self._time_label.setText(
                REST_PENDING_DWELL.format(duration=format_clock(snap.pending_dwell_sec))
            )
            self._progress.setValue(maximum)
        elif snap.state is TimerState.RESTING:
            # FIXED 模式：rest_remaining_sec > 0 顯示倒數；PRESENCE 模式：顯示已休息時間
            if snap.rest_remaining_sec > 0:
                self._time_label.setText(format_clock(snap.rest_remaining_sec))
            else:
                self._time_label.setText(format_clock(snap.rest_elapsed_sec))
            # 休息中進度條不具意義，設為 0
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
            self._progress.setValue(maximum)
        else:
            elapsed = snap.work_elapsed_sec
            self._time_label.setText(format_clock(elapsed))
            self._progress.setValue(min(int(elapsed), maximum))
