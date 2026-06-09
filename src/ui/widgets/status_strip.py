from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

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

    def update_snapshot(self, snap: TimerSnapshot, work_threshold_sec: float) -> None:
        self._state_label.setText(STATE_TEXT.get(snap.state, ""))

        if snap.state == TimerState.RESTING:
            # FIXED mode: show countdown (rest_remaining_sec > 0)
            # PRESENCE mode: show elapsed rest time (rest_elapsed_sec)
            if snap.rest_remaining_sec > 0:
                secs = int(snap.rest_remaining_sec)
            else:
                secs = int(snap.rest_elapsed_sec)
            self._time_label.setText(f"{secs // 60:02d}:{secs % 60:02d}")
            # Progress bar: not meaningful during rest; keep at 0
            self._progress.setMaximum(max(1, int(work_threshold_sec)))
            self._progress.setValue(0)
        else:
            elapsed = int(snap.work_elapsed_sec)
            self._time_label.setText(f"{elapsed // 60:02d}:{elapsed % 60:02d}")
            maximum = max(1, int(work_threshold_sec))
            self._progress.setMaximum(maximum)
            self._progress.setValue(min(elapsed, maximum))

