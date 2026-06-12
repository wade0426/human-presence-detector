"""主視窗（自 src/ui/main_window.py 移植，改 v2）。

移植：PreviewView／徽章／操作列／今日統計（TodayWorkModel）／暫停同步（§4.11）／
ROI 磁碟基底儲存（§4.7）＋寫檔前 clamp（§4.8）。

重設計新增（spec §9）：
- REST_PENDING 狀態列顯示由 StatusStrip 處理（「等待離席／已等待 mm:ss」）。
- REST_INTERRUPTED 通知列：由 snapshot 轉換偵測（RESTING → WORKING/REMINDING
  即中斷——正常滿額一律先經 AWAITING_RETURN；worker 鎖定介面無中斷專用訊號），
  顯示後倒數自動隱藏，進入下一次休息（RESTING/REST_PENDING）立即清除。
"""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.events import TimerSnapshot, TimerState
from src.infra.config import AppConfig, ConfigError, clamp_roi, load_config, save_config
from src.shell.settings.schema import set_value
from src.shell.strings import (
    CLEAR_DATA_BUTTON,
    CONN_ERROR_PREFIX,
    CONN_TEXT,
    REST_INTERRUPTED_NOTICE,
)
from src.shell.widgets.action_bar import ActionBar
from src.shell.widgets.connection_badge import ConnectionBadge
from src.shell.widgets.connection_state import ConnectionState, from_status
from src.shell.widgets.presence_badge import PresenceBadge
from src.shell.widgets.preview_view import PreviewView
from src.shell.widgets.status_strip import StatusStrip
from src.shell.widgets.today_summary_view import TodaySummaryView
from src.shell.widgets.today_work_model import TodayWorkModel
from src.types import BBox, Frame

# REST_INTERRUPTED 通知列自動隱藏時間（毫秒）
INTERRUPT_NOTICE_TIMEOUT_MS = 10_000

# 中斷後的次態：remind → REMINDING、new_work → WORKING（spec §4.2）
_INTERRUPT_NEXT_STATES = (TimerState.WORKING, TimerState.REMINDING)


class SummaryStore(Protocol):
    """今日統計查詢介面（v2 RecordStore 的子集）。"""

    def today_work_seconds(self) -> float: ...
    def today_rest_count(self) -> int: ...


class _FallbackStore:
    def today_work_seconds(self) -> float:
        return 0.0

    def today_rest_count(self) -> int:
        return 0


class MainWindow(QMainWindow):
    roi_changed = Signal(object)
    request_pause = Signal(bool)
    request_settings = Signal()
    request_quit = Signal()
    clear_data_requested = Signal()

    def __init__(
        self,
        config: AppConfig,
        store: SummaryStore | None = None,
        config_path: str = "config.yaml",
    ) -> None:
        super().__init__()
        self._config = config
        self._store: SummaryStore = store if store is not None else _FallbackStore()
        self._config_path = config_path
        self._work_threshold_sec = config.timer.work_threshold_min * 60.0
        self._reminding_mode = config.reminder.reminding_display_mode  # FR-1
        self._today_model = TodayWorkModel()  # FR-4
        self._rest_count: int = 0
        self._last_snapshot: TimerSnapshot | None = None

        self.setWindowTitle("人體辨識休息提醒系統")
        self._build_ui()
        self._wire_internal()

        self._summary_timer = QTimer(self)
        self._summary_timer.setInterval(30_000)
        self._summary_timer.timeout.connect(self.refresh_base)  # FR-4 保險刷新
        self._summary_timer.start()
        self.refresh_base()  # FR-4 啟動時取一次 DB 基準

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

        # REST_INTERRUPTED 通知列（spec §9）：預設隱藏，倒數自動消失
        self._interrupt_notice = QLabel(REST_INTERRUPTED_NOTICE)
        self._interrupt_notice.setProperty("role", "warning")
        self._interrupt_notice.setWordWrap(True)
        self._interrupt_notice.hide()
        self._interrupt_timer = QTimer(self)
        self._interrupt_timer.setInterval(INTERRUPT_NOTICE_TIMEOUT_MS)
        self._interrupt_timer.setSingleShot(True)
        self._interrupt_timer.timeout.connect(self._interrupt_notice.hide)

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
        main_layout.addWidget(self._interrupt_notice)
        main_layout.addLayout(middle_bar)
        main_layout.addWidget(self._actions)

    def _wire_internal(self) -> None:
        self._actions.edit_roi_toggled.connect(self._preview.set_edit_mode)
        self._actions.pause_toggled.connect(self.request_pause)
        self._actions.open_settings.connect(self.request_settings)
        self._actions.request_quit.connect(self.request_quit)
        self._preview.roi_committed.connect(self._on_roi_committed)

    @Slot()
    def refresh_base(self) -> None:
        """從 DB 抓取最新今日統計基準（FR-4）。失敗時沿用上次顯示，不影響 UI。"""
        try:
            work_seconds = self._store.today_work_seconds()
            self._today_model.set_base(work_seconds)
            self._rest_count = self._store.today_rest_count()
            if self._last_snapshot is not None:
                display = self._today_model.observe(self._last_snapshot).display_seconds
            else:
                display = round(work_seconds)
            self._summary.set_today(display, self._rest_count)
        except Exception:
            pass

    def _on_roi_committed(self, roi: BBox) -> None:
        # §4.8 防鎖死（縱深防禦）：寫檔前 clamp，確保不會寫出下次啟動
        # 會被驗證拒絕的越界 roi。
        roi = clamp_roi(roi)
        # §4.7: 以磁碟上的最新 config 為基底再套用 roi，避免把設定視窗剛存的
        # 值蓋回啟動時注入的舊值；磁碟讀取失敗時退回目前持有的 config。
        try:
            base = load_config(self._config_path)
        except ConfigError:
            base = self._config
        updated = set_value(base, "presence.roi", roi)
        self._config = updated
        save_config(updated, self._config_path)
        self.roi_changed.emit(roi)

    def set_paused(self, paused: bool) -> None:
        """§4.11: 由外部（托盤/主程式）同步暫停按鈕狀態，不重發 request_pause。"""
        self._actions.set_paused(paused)

    @Slot(object)
    def on_frame_ready(self, frame: Frame) -> None:
        self._preview.set_frame(frame)

    @Slot(bool)
    def on_presence_changed(self, present: bool) -> None:
        self._presence_badge.set_present(present)

    @Slot(object)
    def on_timer_updated(self, snap: TimerSnapshot) -> None:
        """每次計時器快照更新：今日統計、狀態列與中斷通知（FR-1, FR-4, spec §9）。"""
        previous = self._last_snapshot
        self._last_snapshot = snap
        result = self._today_model.observe(snap)
        if result.base_refresh_needed:
            # 工作剛結束，DB 應已寫入，重抓基準
            self.refresh_base()
            result = self._today_model.observe(snap)
        self._summary.set_today(result.display_seconds, self._rest_count)
        self._status.update_snapshot(snap, self._work_threshold_sec, self._reminding_mode)
        self._update_interrupt_notice(previous, snap)

    def _update_interrupt_notice(
        self, previous: TimerSnapshot | None, snap: TimerSnapshot
    ) -> None:
        """RESTING → WORKING/REMINDING 即休息中斷（正常滿額必經 AWAITING_RETURN）。"""
        if (
            previous is not None
            and previous.state is TimerState.RESTING
            and snap.state in _INTERRUPT_NEXT_STATES
        ):
            self._interrupt_notice.show()
            self._interrupt_timer.start()
        elif snap.state in (TimerState.RESTING, TimerState.REST_PENDING):
            self._interrupt_timer.stop()
            self._interrupt_notice.hide()

    @Slot(str)
    def on_connection_status(self, status: str) -> None:
        state = from_status(status)
        self._badge.set_state(state)
        if state in (
            ConnectionState.NO_SIGNAL,
            ConnectionState.RECONNECTING,
            ConnectionState.CONNECTING,
            ConnectionState.STREAM_ERROR,
        ):
            self._preview.set_overlay_text(CONN_TEXT.get(state.value, ""))
            self._presence_badge.set_present(False)
        else:
            self._preview.set_overlay_text("")

    @Slot(str)
    def on_failed(self, message: str) -> None:
        self._badge.set_state(ConnectionState.ERROR)
        self._preview.set_overlay_text(f"{CONN_ERROR_PREFIX}{message}")

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()
