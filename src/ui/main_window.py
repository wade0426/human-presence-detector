from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QPushButton, QVBoxLayout, QWidget

from src.app.connection_state import ConnectionState, from_status
from src.config import AppConfig, save_config
from src.logging_store import TodaySummary
from src.today_work_model import TodayWorkModel
from src.types import BBox, Frame, TimerSnapshot
from src.ui.settings_schema import set_value
from src.ui.strings import CLEAR_DATA_BUTTON, CONN_ERROR_PREFIX, CONN_TEXT
from src.ui.widgets.action_bar import ActionBar
from src.ui.widgets.connection_badge import ConnectionBadge
from src.ui.widgets.presence_badge import PresenceBadge
from src.ui.widgets.preview_view import PreviewView
from src.ui.widgets.status_strip import StatusStrip
from src.ui.widgets.today_summary_view import TodaySummaryView


class SummaryStore(Protocol):
    def today_summary(self) -> TodaySummary: ...


class _FallbackStore:
    def today_summary(self) -> TodaySummary:
        return TodaySummary(0, 0, 0)


class MainWindow(QMainWindow):
    roi_changed = Signal(object)
    request_pause = Signal(bool)
    request_settings = Signal()
    clear_data_requested = Signal()

    def __init__(
        self,
        config: AppConfig,
        store: SummaryStore | None = None,
        config_path: str = "config.yaml",
    ) -> None:
        super().__init__()
        self._config = config
        self._store = store if store is not None else _FallbackStore()
        self._config_path = config_path
        self._work_threshold_sec = config.timer.work_threshold_min * 60.0
        self._reminding_mode = config.reminder.reminding_display_mode  # FR-1
        self._today_model = TodayWorkModel()                            # FR-4
        self._rest_count: int = 0
        self._last_snapshot: TimerSnapshot | None = None

        self.setWindowTitle("人體辨識休息提醒系統")
        self._build_ui()
        self._wire_internal()

        self._summary_timer = QTimer(self)
        self._summary_timer.setInterval(30_000)
        self._summary_timer.timeout.connect(self._refresh_base)  # FR-4 保險刷新
        self._summary_timer.start()
        self._refresh_base()  # FR-4 啟動時取一次 DB 基準

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        self._preview = PreviewView()
        self._preview.set_roi(self._config.presence.roi)
        self._status = StatusStrip()
        self._badge = ConnectionBadge()
        self._presence_badge = PresenceBadge()
        self._summary = TodaySummaryView()
        self._actions = ActionBar()
        self._clear_data_btn = QPushButton(CLEAR_DATA_BUTTON)
        self._clear_data_btn.clicked.connect(self.clear_data_requested.emit)

        top_bar = QHBoxLayout()
        top_bar.addStretch()
        top_bar.addWidget(self._presence_badge)
        top_bar.addWidget(self._badge)

        middle_bar = QHBoxLayout()
        middle_bar.addWidget(self._summary, stretch=1)
        middle_bar.addWidget(self._clear_data_btn)

        main_layout = QVBoxLayout(central)
        main_layout.addLayout(top_bar)
        main_layout.addWidget(self._preview, stretch=1)
        main_layout.addWidget(self._status)
        main_layout.addLayout(middle_bar)
        main_layout.addWidget(self._actions)

    def _wire_internal(self) -> None:
        self._actions.edit_roi_toggled.connect(self._preview.set_edit_mode)
        self._actions.pause_toggled.connect(self.request_pause)
        self._actions.open_settings.connect(self.request_settings)
        self._preview.roi_committed.connect(self._on_roi_committed)

    def _refresh_base(self) -> None:
        """從 DB 抓取最新今日統計基準（FR-4）。失敗時沿用上次顯示，不影響 UI。"""
        try:
            summary = self._store.today_summary()
            self._today_model.set_base(summary.work_seconds)
            self._rest_count = summary.rest_count
            if self._last_snapshot is not None:
                display = self._today_model.observe(self._last_snapshot).display_seconds
            else:
                display = summary.work_seconds
            self._summary.set_today(display, self._rest_count)
        except Exception:
            pass

    def _refresh_summary(self) -> None:
        """向後相容保留，轉發至 _refresh_base。"""
        self._refresh_base()

    def _on_roi_committed(self, roi: BBox) -> None:
        updated = set_value(self._config, "presence.roi", roi)
        self._config = updated
        save_config(updated, self._config_path)
        self.roi_changed.emit(roi)

    def on_frame_ready(self, frame: Frame) -> None:
        self._preview.set_frame(frame)

    def on_presence_changed(self, present: bool) -> None:
        self._presence_badge.set_present(present)

    def on_timer_updated(self, snap: TimerSnapshot) -> None:
        """每次計時器快照更新：即時更新今日統計與狀態列（FR-1, FR-4）。"""
        self._last_snapshot = snap
        result = self._today_model.observe(snap)
        if result.base_refresh_needed:
            # 工作剛結束，DB 應已寫入，重抓基準
            self._refresh_base()
            result = self._today_model.observe(snap)
        self._summary.set_today(result.display_seconds, self._rest_count)
        self._status.update_snapshot(snap, self._work_threshold_sec, self._reminding_mode)

    def on_connection_status(self, status: str) -> None:
        state = from_status(status)
        self._badge.set_state(state)
        if state in (
            ConnectionState.NO_SIGNAL,
            ConnectionState.RECONNECTING,
            ConnectionState.CONNECTING,
            ConnectionState.STREAM_ERROR,
        ):
            self._preview.set_overlay_text(CONN_TEXT.get(state, ""))
            self._presence_badge.set_present(False)
        else:
            self._preview.set_overlay_text("")

    def on_failed(self, message: str) -> None:
        self._badge.set_state(ConnectionState.ERROR)
        self._preview.set_overlay_text(f"{CONN_ERROR_PREFIX}{message}")

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()
