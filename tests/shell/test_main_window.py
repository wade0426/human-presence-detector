"""T10 主視窗測試（移植 tests/test_ui.py 的 MainWindow/widgets 區段，改 v2）。

新增（重設計）：
- REST_PENDING 狀態列：``STATUS_REST_PENDING`` ＋ ``REST_PENDING_DWELL``（mm:ss）。
- REST_INTERRUPTED 通知列：RESTING → WORKING/REMINDING 的 snapshot 轉換顯示，
  進入下一次休息（RESTING/REST_PENDING）即清除；正常滿額路徑不顯示。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt

from src.core.events import TimerSnapshot, TimerState
from src.infra.config import AppConfig, load_config, save_config
from src.shell import strings
from src.shell.main_window import MainWindow
from src.shell.settings.schema import set_value
from src.shell.widgets.status_strip import StatusStrip
from src.types import BBox, Frame

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


class FakeSummaryStore:
    def __init__(self, work_seconds: float = 0.0, rest_count: int = 0) -> None:
        self._work_seconds = work_seconds
        self._rest_count = rest_count

    def today_work_seconds(self) -> float:
        return self._work_seconds

    def today_rest_count(self) -> int:
        return self._rest_count


class SequenceSummaryStore:
    """today_work_seconds 依呼叫次序回傳序列值（最後一值重複）。"""

    def __init__(self, work_seconds: list[float], rest_count: int = 1) -> None:
        self._work_seconds = list(work_seconds)
        self._rest_count = rest_count
        self.calls = 0

    def today_work_seconds(self) -> float:
        index = min(self.calls, len(self._work_seconds) - 1)
        self.calls += 1
        return self._work_seconds[index]

    def today_rest_count(self) -> int:
        return self._rest_count


def snap(
    state: TimerState,
    *,
    work: float = 0.0,
    rest_remaining: float = 0.0,
    rest_elapsed: float = 0.0,
    overtime: float = 0.0,
    dwell: float = 0.0,
    stage: int = -1,
    reminder_active: bool | None = None,
) -> TimerSnapshot:
    return TimerSnapshot(
        state=state,
        work_elapsed_sec=work,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=(
            reminder_active
            if reminder_active is not None
            else state is TimerState.REMINDING
        ),
        rest_remaining_sec=rest_remaining,
        rest_elapsed_sec=rest_elapsed,
        overtime_sec=overtime,
        pending_dwell_sec=dwell,
        escalation_stage=stage,
    )


def make_window(
    qtbot: QtBot,
    tmp_path: object,
    store: object | None = None,
    cfg: AppConfig | None = None,
) -> MainWindow:
    window = MainWindow(
        cfg if cfg is not None else AppConfig(),
        store if store is not None else FakeSummaryStore(),
        config_path=f"{tmp_path}/main-window.yaml",
    )
    qtbot.addWidget(window)
    return window


def _frame(width: int = 10, height: int = 10) -> Frame:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    return Frame(image=image, width=width, height=height, timestamp=0.0)


# ---------------------------------------------------------------------------
# 建構與 ROI（移植）
# ---------------------------------------------------------------------------


def test_main_window_can_be_created(qtbot: QtBot, tmp_path: object) -> None:
    window = make_window(qtbot, tmp_path)

    assert window._preview is not None


def test_main_window_emits_normalized_roi_from_drag(qtbot: QtBot, tmp_path: object) -> None:
    window = make_window(qtbot, tmp_path)
    window.resize(900, 700)
    window.show()
    window._preview.set_edit_mode(True)

    with qtbot.waitSignal(window.roi_changed, timeout=3000) as blocker:
        qtbot.mousePress(window._preview, Qt.MouseButton.LeftButton, pos=QPoint(10, 20))
        qtbot.mouseMove(window._preview, QPoint(110, 120))
        qtbot.mouseRelease(window._preview, Qt.MouseButton.LeftButton, pos=QPoint(110, 120))

    roi = blocker.args[0]
    width = max(window._preview.width(), 1)
    height = max(window._preview.height(), 1)
    assert isinstance(roi, BBox)
    assert roi.x == pytest.approx(10 / width, abs=0.01)
    assert roi.y == pytest.approx(20 / height, abs=0.01)
    assert roi.w == pytest.approx(100 / width, abs=0.01)
    assert roi.h == pytest.approx(100 / height, abs=0.01)


def test_main_window_roi_commit_uses_disk_config_as_base(
    qtbot: QtBot, tmp_path: object
) -> None:
    """§4.7 ROI 端：先存設定（磁碟有新值）→ ROI 重框寫檔後設定值保留。"""
    cfg_path = f"{tmp_path}/cfg.yaml"
    window = MainWindow(AppConfig(), FakeSummaryStore(), config_path=cfg_path)
    qtbot.addWidget(window)

    # 模擬設定視窗在 window 啟動後把新值存到磁碟（window 仍持有啟動時的舊 config）
    disk_cfg = set_value(AppConfig(), "source.type", "webcam")  # 確保重讀可通過驗證
    disk_cfg = set_value(disk_cfg, "timer.work_threshold_min", 33.0)
    save_config(disk_cfg, cfg_path)

    window._on_roi_committed(BBox(0.1, 0.2, 0.3, 0.4))

    saved = load_config(cfg_path)
    assert saved.timer.work_threshold_min == 33.0
    assert saved.presence.roi == BBox(0.1, 0.2, 0.3, 0.4)


def test_main_window_roi_commit_clamps_out_of_range_roi(
    qtbot: QtBot, tmp_path: object
) -> None:
    """§4.8 防鎖死：越界 roi 寫檔前 clamp，避免下次啟動被驗證拒絕。"""
    cfg_path = f"{tmp_path}/cfg.yaml"
    window = MainWindow(AppConfig(), FakeSummaryStore(), config_path=cfg_path)
    qtbot.addWidget(window)
    # 磁碟需有可通過驗證的基底（預設 rtsp＋空 URL 會被 v2 驗證拒絕）
    save_config(set_value(AppConfig(), "source.type", "webcam"), cfg_path)

    window._on_roi_committed(BBox(0.5, 0.5, 0.9, 0.9))

    saved = load_config(cfg_path)
    assert saved.presence.roi.x + saved.presence.roi.w <= 1.0
    assert saved.presence.roi.y + saved.presence.roi.h <= 1.0


# ---------------------------------------------------------------------------
# REST_PENDING 狀態列（新）
# ---------------------------------------------------------------------------


def test_rest_pending_snapshot_shows_status_and_dwell(qtbot: QtBot, tmp_path: object) -> None:
    window = make_window(qtbot, tmp_path)

    window.on_timer_updated(snap(TimerState.REST_PENDING, work=3000.0, dwell=42.0, stage=0))

    assert window._status._state_label.text() == strings.STATUS_REST_PENDING
    assert window._status._time_label.text() == strings.REST_PENDING_DWELL.format(
        duration="00:42"
    )


def test_status_strip_rest_pending_progress_is_full(qtbot: QtBot) -> None:
    strip = StatusStrip()
    qtbot.addWidget(strip)

    strip.update_snapshot(
        snap(TimerState.REST_PENDING, work=3000.0, dwell=10.0, stage=0),
        work_threshold_sec=2700.0,
    )

    assert strip._progress.value() == strip._progress.maximum()


# ---------------------------------------------------------------------------
# REST_INTERRUPTED 通知列（新）
# ---------------------------------------------------------------------------


def test_interrupt_notice_hidden_initially(qtbot: QtBot, tmp_path: object) -> None:
    window = make_window(qtbot, tmp_path)
    window.show()

    assert not window._interrupt_notice.isVisible()


def test_interrupt_notice_shown_on_resting_to_reminding(
    qtbot: QtBot, tmp_path: object
) -> None:
    """中斷 remind 模式：RESTING →（未滿額）REMINDING → 顯示「休息中斷」。"""
    window = make_window(qtbot, tmp_path)
    window.show()

    window.on_timer_updated(snap(TimerState.RESTING, rest_elapsed=30.0))
    window.on_timer_updated(snap(TimerState.REMINDING, work=120.0))

    assert window._interrupt_notice.isVisible()
    assert window._interrupt_notice.text() == strings.REST_INTERRUPTED_NOTICE


def test_interrupt_notice_shown_on_resting_to_working(qtbot: QtBot, tmp_path: object) -> None:
    """中斷 new_work 模式：RESTING → WORKING 同樣顯示通知。"""
    window = make_window(qtbot, tmp_path)
    window.show()

    window.on_timer_updated(snap(TimerState.RESTING, rest_elapsed=30.0))
    window.on_timer_updated(snap(TimerState.WORKING, work=120.0))

    assert window._interrupt_notice.isVisible()


def test_interrupt_notice_not_shown_on_normal_completion(
    qtbot: QtBot, tmp_path: object
) -> None:
    """正常滿額：RESTING → AWAITING_RETURN → WORKING 不顯示通知。"""
    window = make_window(qtbot, tmp_path)
    window.show()

    window.on_timer_updated(snap(TimerState.RESTING, rest_elapsed=600.0))
    window.on_timer_updated(snap(TimerState.AWAITING_RETURN))
    window.on_timer_updated(snap(TimerState.WORKING, work=1.0))

    assert not window._interrupt_notice.isVisible()


def test_interrupt_notice_clears_when_next_rest_starts(qtbot: QtBot, tmp_path: object) -> None:
    window = make_window(qtbot, tmp_path)
    window.show()

    window.on_timer_updated(snap(TimerState.RESTING, rest_elapsed=30.0))
    window.on_timer_updated(snap(TimerState.REMINDING, work=120.0))
    assert window._interrupt_notice.isVisible()

    window.on_timer_updated(snap(TimerState.REST_PENDING, work=130.0, dwell=1.0, stage=0))

    assert not window._interrupt_notice.isVisible()


# ---------------------------------------------------------------------------
# 今日統計（移植 FR-4）
# ---------------------------------------------------------------------------


def test_main_window_today_work_updates_with_working_snapshots(
    qtbot: QtBot, tmp_path: object
) -> None:
    window = make_window(qtbot, tmp_path, store=FakeSummaryStore(600.0, 1))

    window.on_timer_updated(snap(TimerState.WORKING, work=30.0))
    first_text = window._summary._work_label.text()
    window.on_timer_updated(snap(TimerState.WORKING, work=60.0))
    second_text = window._summary._work_label.text()

    assert "10 分 30 秒" in first_text
    assert "11 分鐘" in second_text


def test_main_window_refreshes_base_once_when_work_session_ends(
    qtbot: QtBot, tmp_path: object
) -> None:
    store = SequenceSummaryStore([600.0, 660.0], rest_count=1)
    window = make_window(qtbot, tmp_path, store=store)

    window.on_timer_updated(snap(TimerState.WORKING, work=60.0))
    calls_before_end = store.calls
    window.on_timer_updated(snap(TimerState.RESTING, rest_remaining=120.0))

    assert store.calls == calls_before_end + 1
    assert "11 分鐘" in window._summary._work_label.text()


# ---------------------------------------------------------------------------
# 暫停同步（§4.11）與清除資料入口（移植）
# ---------------------------------------------------------------------------


def test_main_window_set_paused_forwards_to_action_bar(
    qtbot: QtBot, tmp_path: object
) -> None:
    """§4.11：MainWindow.set_paused 轉發至 ActionBar，且不得重發 request_pause。"""
    window = make_window(qtbot, tmp_path)
    emitted: list[bool] = []
    window.request_pause.connect(emitted.append)

    window.set_paused(True)

    assert window._actions._pause_btn.isChecked() is True
    assert emitted == []


def test_main_window_emits_clear_requested(qtbot: QtBot, tmp_path: object) -> None:
    window = make_window(qtbot, tmp_path)

    with qtbot.waitSignal(window.clear_data_requested, timeout=1000):
        qtbot.mouseClick(window._clear_data_btn, Qt.MouseButton.LeftButton)


# ---------------------------------------------------------------------------
# 連線狀態與失敗（移植）
# ---------------------------------------------------------------------------


def test_main_window_stream_error_shows_overlay_and_clears_presence(
    qtbot: QtBot, tmp_path: object
) -> None:
    window = make_window(qtbot, tmp_path)

    window.on_presence_changed(True)
    assert window._presence_badge._text_label.text() == strings.PRESENCE_YES

    window.on_connection_status("stream_error")

    assert window._presence_badge._text_label.text() == strings.PRESENCE_NO
    assert window._preview._overlay.text() == "影像異常"


def test_main_window_connected_clears_overlay_text(qtbot: QtBot, tmp_path: object) -> None:
    window = make_window(qtbot, tmp_path)

    window.on_connection_status("no_signal")
    assert window._preview._overlay.text() != ""

    window.on_connection_status("connected")

    assert window._preview._overlay.text() == ""


def test_main_window_on_failed_shows_error(qtbot: QtBot, tmp_path: object) -> None:
    window = make_window(qtbot, tmp_path)

    window.on_failed("boom")

    assert strings.CONN_ERROR_PREFIX in window._preview._overlay.text()
    assert "boom" in window._preview._overlay.text()


# ---------------------------------------------------------------------------
# StatusStrip（移植 FR-1 顯示規則）
# ---------------------------------------------------------------------------


def test_status_strip_working_format_clock(qtbot: QtBot) -> None:
    strip = StatusStrip()
    qtbot.addWidget(strip)

    strip.update_snapshot(snap(TimerState.WORKING, work=90.0), work_threshold_sec=2700.0)

    assert "工作中" in strip._state_label.text()
    assert "01:30" in strip._time_label.text()


def test_status_strip_reminding_overtime_mode(qtbot: QtBot) -> None:
    strip = StatusStrip()
    qtbot.addWidget(strip)

    strip.update_snapshot(
        snap(TimerState.REMINDING, work=2760.0, overtime=60.0),
        work_threshold_sec=2700.0,
        reminding_mode="overtime",
    )

    assert strip._time_label.text() == "超時 01:00"


def test_status_strip_reminding_work_and_reminder_mode(qtbot: QtBot) -> None:
    strip = StatusStrip()
    qtbot.addWidget(strip)

    strip.update_snapshot(
        snap(TimerState.REMINDING, work=2760.0, overtime=60.0),
        work_threshold_sec=2700.0,
        reminding_mode="work_and_reminder",
    )

    assert strip._time_label.text() == "工作 46:00 / 提醒 01:00"


def test_status_strip_resting_presence_shows_elapsed(qtbot: QtBot) -> None:
    strip = StatusStrip()
    qtbot.addWidget(strip)

    strip.update_snapshot(
        snap(TimerState.RESTING, rest_elapsed=75.0), work_threshold_sec=2700.0
    )

    assert strip._state_label.text() == "休息中"
    assert strip._time_label.text() == "01:15"


def test_status_strip_resting_fixed_shows_countdown(qtbot: QtBot) -> None:
    strip = StatusStrip()
    qtbot.addWidget(strip)

    strip.update_snapshot(
        snap(TimerState.RESTING, rest_remaining=120.0), work_threshold_sec=2700.0
    )

    assert strip._time_label.text() == "02:00"


def test_status_strip_suspended_from_reminding_keeps_overtime(qtbot: QtBot) -> None:
    """從 REMINDING 暫停：snapshot.state=SUSPENDED 但 reminder_active=True，
    時間標籤維持超時顯示（凍結值）。"""
    strip = StatusStrip()
    qtbot.addWidget(strip)

    strip.update_snapshot(
        snap(TimerState.SUSPENDED, work=2760.0, overtime=60.0, reminder_active=True),
        work_threshold_sec=2700.0,
    )

    assert strip._state_label.text() == "已暫停"
    assert strip._time_label.text() == "超時 01:00"


# ---------------------------------------------------------------------------
# PreviewView（移植 §4.3 留邊換算與 §4.9 覆蓋層分離的代表性回歸）
# ---------------------------------------------------------------------------


def test_preview_view_hint_survives_frame_updates(qtbot: QtBot) -> None:
    from src.shell.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.resize(400, 300)
    view.show()

    view.set_edit_mode(True)
    view.set_frame(_frame())
    view.set_frame(_frame())

    assert view._overlay.isVisible()
    assert view._overlay.text() == strings.ROI_HINT


def test_preview_view_roi_conversion_compensates_letterbox(qtbot: QtBot) -> None:
    """§4.3：寬幅影像置中後上下留邊，框選換算需以實際顯示矩形為基準。"""
    from src.shell.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.resize(400, 400)
    view.show()
    view.set_frame(_frame(width=400, height=200))  # 2:1 影像進 1:1 視窗 → 上下留邊
    view.set_edit_mode(True)

    display = view._display_rect()
    assert display is not None
    # 框住整個顯示影像區域 → ROI 應為全幅 (0,0,1,1)
    roi = view._roi_from_selection(display)

    assert roi is not None
    assert roi.x == pytest.approx(0.0, abs=0.02)
    assert roi.y == pytest.approx(0.0, abs=0.02)
    assert roi.w == pytest.approx(1.0, abs=0.02)
    assert roi.h == pytest.approx(1.0, abs=0.02)


def test_preview_view_drag_in_margin_rejected(qtbot: QtBot) -> None:
    from PySide6.QtCore import QRect

    from src.shell.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.resize(400, 400)
    view.show()
    view.set_frame(_frame(width=400, height=100))  # 4:1 → 大片上下留邊

    display = view._display_rect()
    assert display is not None
    margin_rect = QRect(0, 0, display.width(), max(1, display.y() - 2))  # 全在上留邊

    assert view._roi_from_selection(margin_rect) is None
