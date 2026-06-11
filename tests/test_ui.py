from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QPushButton, QWidget

from src.config import AppConfig
from src.logging_store import TodaySummary
from src.types import TimerSnapshot, TimerState
from src.ui.settings_schema import SCHEMA


class FakeSummaryStore:
    def __init__(self, summary: TodaySummary | None = None) -> None:
        self._summary = summary or TodaySummary(0, 0, 0)

    def today_summary(self) -> TodaySummary:
        return self._summary


class SequenceSummaryStore:
    def __init__(self, summaries: list[TodaySummary]) -> None:
        self._summaries = list(summaries)
        self.calls = 0

    def today_summary(self) -> TodaySummary:
        index = min(self.calls, len(self._summaries) - 1)
        self.calls += 1
        return self._summaries[index]


def test_main_window_can_be_created(qtbot: pytest.QtBot, tmp_path: object) -> None:
    from src.ui.main_window import MainWindow

    window = MainWindow(
        AppConfig(),
        FakeSummaryStore(),
        config_path=str(tmp_path / "main-window.yaml"),
    )
    qtbot.addWidget(window)

    assert window._preview is not None


def test_main_window_emits_normalized_roi_from_drag(
    qtbot: pytest.QtBot, tmp_path: object
) -> None:
    from src.types import BBox
    from src.ui.main_window import MainWindow

    window = MainWindow(
        AppConfig(),
        FakeSummaryStore(),
        config_path=str(tmp_path / "main-window.yaml"),
    )
    qtbot.addWidget(window)
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


def test_settings_window_initial_values(qtbot: pytest.QtBot, tmp_path: object) -> None:
    from src.ui.settings import SettingsWindow

    window = SettingsWindow(AppConfig(), config_path=str(tmp_path / "cfg.yaml"))
    qtbot.addWidget(window)

    for spec in SCHEMA:
        widget = window._widgets.get(spec.key)
        if isinstance(widget, QDoubleSpinBox):
            assert widget.minimum() == (spec.minimum or 0)


def test_settings_window_save_invalid_blocks(qtbot: pytest.QtBot, tmp_path: object) -> None:
    from src.ui.settings import SettingsWindow

    cfg_path = tmp_path / "cfg.yaml"
    window = SettingsWindow(AppConfig(), config_path=str(cfg_path))
    qtbot.addWidget(window)

    widget = window._widgets.get("timer.work_threshold_min")
    if isinstance(widget, QDoubleSpinBox):
        widget.setValue(0.0)

    window._on_save()

    assert not os.path.exists(cfg_path)


def test_settings_window_save_valid_writes_file(
    qtbot: pytest.QtBot, tmp_path: object
) -> None:
    from src.ui.settings import SettingsWindow

    cfg_path = tmp_path / "cfg.yaml"
    window = SettingsWindow(AppConfig(), config_path=str(cfg_path))
    qtbot.addWidget(window)

    combo = window._widgets.get("source.type")
    if isinstance(combo, QComboBox):
        combo.setCurrentText("webcam")

    with patch("PySide6.QtWidgets.QMessageBox.information"):
        window._on_save()

    assert os.path.exists(cfg_path)


def test_source_type_toggle(qtbot: pytest.QtBot, tmp_path: object) -> None:
    from src.ui.settings import SettingsWindow

    window = SettingsWindow(AppConfig(), config_path=str(tmp_path / "cfg.yaml"))
    qtbot.addWidget(window)

    combo = window._widgets.get("source.type")
    if isinstance(combo, QComboBox):
        combo.setCurrentText("webcam")

    rtsp_widget = window._widgets.get("source.rtsp_url")
    if isinstance(rtsp_widget, QWidget):
        assert not rtsp_widget.isEnabled()


def test_tray_icon_can_be_created(qtbot: pytest.QtBot) -> None:
    from src.ui.tray import TrayIcon

    tray = TrayIcon()
    qtbot.addWidget(QWidget())

    assert tray.contextMenu() is not None


def test_tray_icon_not_null(qtbot: pytest.QtBot) -> None:
    from src.ui.tray import TrayIcon

    tray = TrayIcon()
    qtbot.addWidget(QWidget())

    assert not tray.icon().isNull()


def test_tray_set_paused_changes_toggle_text(qtbot: pytest.QtBot) -> None:
    from src.ui import strings
    from src.ui.tray import TrayIcon

    tray = TrayIcon()
    qtbot.addWidget(QWidget())
    tray.set_paused(True)
    assert tray.toggle_action.text() == strings.TRAY_RESUME

    tray.set_paused(False)
    assert tray.toggle_action.text() == strings.TRAY_PAUSE


def test_tray_tooltip_updates_with_state(qtbot: pytest.QtBot) -> None:
    from src.app.connection_state import ConnectionState
    from src.types import TimerState
    from src.ui.tray import TrayIcon

    tray = TrayIcon()
    qtbot.addWidget(QWidget())
    tray.set_timer_state(TimerState.WORKING)
    tray.set_connection(ConnectionState.CONNECTED)

    tooltip = tray.toolTip()
    assert "工作中" in tooltip
    assert "已連線" in tooltip


def test_status_strip_displays_state(qtbot: pytest.QtBot) -> None:
    from src.ui.widgets.status_strip import StatusStrip

    strip = StatusStrip()
    qtbot.addWidget(strip)
    snapshot = TimerSnapshot(
        state=TimerState.WORKING,
        work_elapsed_sec=90.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=2610.0,
        reminder_active=False,
    )

    strip.update_snapshot(snapshot, work_threshold_sec=2700.0)

    assert "工作中" in strip._state_label.text()
    assert "01:30" in strip._time_label.text()


def test_connection_badge_has_text_and_icon(qtbot: pytest.QtBot) -> None:
    from src.app.connection_state import ConnectionState
    from src.ui.widgets.connection_badge import ConnectionBadge

    badge = ConnectionBadge()
    qtbot.addWidget(badge)
    badge.set_state(ConnectionState.CONNECTED)

    assert badge._text_label.text() == "已連線"
    assert badge._icon_label.text() != ""


def test_today_summary_view_empty_state(qtbot: pytest.QtBot) -> None:
    from src.ui.strings import TODAY_EMPTY
    from src.ui.widgets.today_summary_view import TodaySummaryView

    view = TodaySummaryView()
    qtbot.addWidget(view)
    view.set_summary(TodaySummary(0, 0, 0))

    assert TODAY_EMPTY in view._work_label.text()


def test_preview_view_no_roi_in_non_edit_mode(qtbot: pytest.QtBot) -> None:
    from src.ui.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.set_edit_mode(False)
    signals: list[object] = []
    view.roi_committed.connect(signals.append)

    qtbot.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    qtbot.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))

    assert len(signals) == 0


# ---------------------------------------------------------------------------
# M5 Tests — PresenceBadge & StatusStrip new states
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_presence_badge_set_present_true(qtbot: pytest.QtBot) -> None:
    """PresenceBadge.set_present(True) → text shows '有人'."""
    from src.ui.widgets.presence_badge import PresenceBadge

    badge = PresenceBadge()
    qtbot.addWidget(badge)
    badge.set_present(True)

    assert badge._text_label.text() == "有人"


@pytest.mark.qt
def test_presence_badge_set_present_false(qtbot: pytest.QtBot) -> None:
    """PresenceBadge.set_present(False) → text shows '無人'."""
    from src.ui.widgets.presence_badge import PresenceBadge

    badge = PresenceBadge()
    qtbot.addWidget(badge)
    badge.set_present(False)

    assert badge._text_label.text() == "無人"


@pytest.mark.qt
def test_status_strip_resting_state(qtbot: pytest.QtBot) -> None:
    """StatusStrip.update_snapshot with RESTING state shows '休息中'."""
    from src.ui.widgets.status_strip import StatusStrip

    strip = StatusStrip()
    qtbot.addWidget(strip)
    snapshot = TimerSnapshot(
        state=TimerState.RESTING,
        work_elapsed_sec=0.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=False,
        rest_remaining_sec=120.0,
        rest_elapsed_sec=0.0,
    )
    strip.update_snapshot(snapshot, work_threshold_sec=2700.0)

    assert strip._state_label.text() == "休息中"


@pytest.mark.qt
def test_status_strip_suspended_state(qtbot: pytest.QtBot) -> None:
    """StatusStrip.update_snapshot with SUSPENDED state shows '已暫停'."""
    from src.ui.widgets.status_strip import StatusStrip

    strip = StatusStrip()
    qtbot.addWidget(strip)
    snapshot = TimerSnapshot(
        state=TimerState.SUSPENDED,
        work_elapsed_sec=60.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=2640.0,
        reminder_active=False,
    )
    strip.update_snapshot(snapshot, work_threshold_sec=2700.0)

    assert strip._state_label.text() == "已暫停"


@pytest.mark.qt
def test_presence_badge_away_vs_suspended_distinguishable(qtbot: pytest.QtBot) -> None:
    """AWAY shows '短暫離開' and SUSPENDED shows '已暫停' (distinguishable)."""
    from src.ui.strings import STATE_TEXT

    assert STATE_TEXT[TimerState.AWAY] == "短暫離開"
    assert STATE_TEXT[TimerState.SUSPENDED] == "已暫停"
    assert STATE_TEXT[TimerState.AWAY] != STATE_TEXT[TimerState.SUSPENDED]


@pytest.mark.qt
def test_main_window_on_connection_status_no_signal_resets_presence(
    qtbot: pytest.QtBot, tmp_path: object
) -> None:
    """on_connection_status('no_signal') → PresenceBadge shows '無人'."""
    from src.ui.main_window import MainWindow

    window = MainWindow(
        AppConfig(),
        config_path=str(tmp_path / "cfg.yaml"),
    )
    qtbot.addWidget(window)

    # First set present
    window.on_presence_changed(True)
    assert window._presence_badge._text_label.text() == "有人"

    # Then simulate connection loss
    window.on_connection_status("no_signal")
    assert window._presence_badge._text_label.text() == "無人"


# ---------------------------------------------------------------------------
# M6 Tests — ActionBar quit button, ROI edit toggle, PreviewView hint
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_action_bar_roi_toggle_true_shows_active_text(qtbot: pytest.QtBot) -> None:
    """ROI button toggled(True) → text changes to '完成編輯', isChecked()==True."""
    from src.ui.widgets.action_bar import ActionBar

    bar = ActionBar()
    qtbot.addWidget(bar)
    bar._roi_btn.setChecked(True)

    assert bar._roi_btn.text() == "完成編輯"
    assert bar._roi_btn.isChecked() is True


@pytest.mark.qt
def test_action_bar_roi_toggle_false_restores_original_text(qtbot: pytest.QtBot) -> None:
    """ROI button toggled(False) → text restores to '編輯 ROI'."""
    from src.ui.widgets.action_bar import ActionBar

    bar = ActionBar()
    qtbot.addWidget(bar)
    bar._roi_btn.setChecked(True)
    bar._roi_btn.setChecked(False)

    assert bar._roi_btn.text() == "編輯 ROI"


@pytest.mark.qt
def test_action_bar_quit_button_emits_request_quit(qtbot: pytest.QtBot) -> None:
    """Clicking quit button → request_quit signal is emitted."""
    from src.ui.widgets.action_bar import ActionBar

    bar = ActionBar()
    qtbot.addWidget(bar)

    with qtbot.waitSignal(bar.request_quit, timeout=1000):
        bar._quit_btn.click()


@pytest.mark.qt
def test_preview_view_edit_mode_shows_hint(qtbot: pytest.QtBot) -> None:
    """set_edit_mode(True) → hint overlay shows ROI_HINT text (§4.9 覆蓋層)."""
    from src.ui.strings import ROI_HINT
    from src.ui.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.set_edit_mode(True)

    assert view._overlay.text() == ROI_HINT
    assert not view._overlay.isHidden()


@pytest.mark.qt
def test_preview_view_edit_mode_false_hides_hint(qtbot: pytest.QtBot) -> None:
    """set_edit_mode(False) → hint overlay is cleared and hidden."""
    from src.ui.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.set_edit_mode(True)
    view.set_edit_mode(False)

    assert view._overlay.text() == ""
    assert view._overlay.isHidden()


# ---------------------------------------------------------------------------
# 批次 4 Tests — StatusStrip FR-1/FR-2 & TodaySummaryView FR-4
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_status_strip_working_format_clock(qtbot: pytest.QtBot) -> None:
    """WORKING 狀態：顯示 format_clock(work_elapsed_sec)（FR-1）。"""
    from src.ui.widgets.status_strip import StatusStrip

    strip = StatusStrip()
    qtbot.addWidget(strip)
    snapshot = TimerSnapshot(
        state=TimerState.WORKING,
        work_elapsed_sec=90.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=2610.0,
        reminder_active=False,
    )
    strip.update_snapshot(snapshot, work_threshold_sec=2700.0)

    assert "工作中" in strip._state_label.text()
    assert "01:30" in strip._time_label.text()


@pytest.mark.qt
def test_status_strip_reminding_overtime_mode(qtbot: pytest.QtBot) -> None:
    """REMINDING + reminding_mode='overtime' → 顯示「超時 MM:SS」（FR-1）。"""
    from src.ui.widgets.status_strip import StatusStrip

    strip = StatusStrip()
    qtbot.addWidget(strip)
    snapshot = TimerSnapshot(
        state=TimerState.REMINDING,
        work_elapsed_sec=2760.0,  # 2700 + 60
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=True,
        overtime_sec=60.0,
    )
    strip.update_snapshot(snapshot, work_threshold_sec=2700.0, reminding_mode="overtime")

    assert "超時" in strip._time_label.text()
    assert "01:00" in strip._time_label.text()


@pytest.mark.qt
def test_status_strip_reminding_work_and_reminder_mode(qtbot: pytest.QtBot) -> None:
    """REMINDING + reminding_mode='work_and_reminder' → 含工作時間與提醒持續時間（FR-1）。"""
    from src.ui.widgets.status_strip import StatusStrip

    strip = StatusStrip()
    qtbot.addWidget(strip)
    snapshot = TimerSnapshot(
        state=TimerState.REMINDING,
        work_elapsed_sec=2760.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=True,
        overtime_sec=60.0,
    )
    strip.update_snapshot(
        snapshot, work_threshold_sec=2700.0, reminding_mode="work_and_reminder"
    )

    text = strip._time_label.text()
    assert "工作" in text
    assert "提醒" in text


@pytest.mark.qt
def test_status_strip_suspended_from_reminding_frozen(qtbot: pytest.QtBot) -> None:
    """SUSPENDED（reminder_active=True）：數字凍結不跳變（FR-2）。"""
    from src.ui.widgets.status_strip import StatusStrip

    strip = StatusStrip()
    qtbot.addWidget(strip)
    snapshot = TimerSnapshot(
        state=TimerState.SUSPENDED,
        work_elapsed_sec=2760.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=True,
        overtime_sec=60.0,
    )
    strip.update_snapshot(snapshot, work_threshold_sec=2700.0, reminding_mode="overtime")

    assert "已暫停" in strip._state_label.text()
    assert "超時" in strip._time_label.text()

    # 連續多次呼叫，overtime_sec 不變 → 數字不跳
    text_first = strip._time_label.text()
    strip.update_snapshot(snapshot, work_threshold_sec=2700.0, reminding_mode="overtime")
    assert strip._time_label.text() == text_first


@pytest.mark.qt
def test_today_summary_view_set_today_empty(qtbot: pytest.QtBot) -> None:
    """set_today(0, 0) → 顯示 TODAY_EMPTY（FR-4）。"""
    from src.ui.strings import TODAY_EMPTY
    from src.ui.widgets.today_summary_view import TodaySummaryView

    view = TodaySummaryView()
    qtbot.addWidget(view)
    view.set_today(0, 0)

    assert TODAY_EMPTY in view._work_label.text()
    assert view._rest_label.text() == ""


@pytest.mark.qt
def test_today_summary_view_set_today_with_data(qtbot: pytest.QtBot) -> None:
    """set_today(90, 2) → 顯示「1 分 30 秒」及休息次數（FR-4）。"""
    from src.ui.widgets.today_summary_view import TodaySummaryView

    view = TodaySummaryView()
    qtbot.addWidget(view)
    view.set_today(90, 2)

    assert "1 分 30 秒" in view._work_label.text()
    assert "2" in view._rest_label.text()


@pytest.mark.qt
def test_today_summary_view_set_today_seconds_only(qtbot: pytest.QtBot) -> None:
    """set_today(30, 0) → 顯示「30 秒」（FR-4）。"""
    from src.ui.widgets.today_summary_view import TodaySummaryView

    view = TodaySummaryView()
    qtbot.addWidget(view)
    view.set_today(30, 0)

    assert "30 秒" in view._work_label.text()


@pytest.mark.qt
def test_main_window_today_work_updates_with_working_snapshots(
    qtbot: pytest.QtBot, tmp_path: object
) -> None:
    from src.ui.main_window import MainWindow

    window = MainWindow(
        AppConfig(),
        store=FakeSummaryStore(TodaySummary(600, 1, 1)),
        config_path=str(tmp_path / "cfg.yaml"),
    )
    qtbot.addWidget(window)

    first = TimerSnapshot(
        state=TimerState.WORKING,
        work_elapsed_sec=30.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=2670.0,
        reminder_active=False,
    )
    second = TimerSnapshot(
        state=TimerState.WORKING,
        work_elapsed_sec=60.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=2640.0,
        reminder_active=False,
    )

    window.on_timer_updated(first)
    first_text = window._summary._work_label.text()
    window.on_timer_updated(second)
    second_text = window._summary._work_label.text()

    assert "10 分 30 秒" in first_text
    assert "11 分鐘" in second_text


@pytest.mark.qt
def test_main_window_refreshes_base_once_when_work_session_ends(
    qtbot: pytest.QtBot, tmp_path: object
) -> None:
    from src.ui.main_window import MainWindow

    store = SequenceSummaryStore([TodaySummary(600, 1, 1), TodaySummary(660, 1, 2)])
    window = MainWindow(
        AppConfig(),
        store=store,
        config_path=str(tmp_path / "cfg.yaml"),
    )
    qtbot.addWidget(window)

    active = TimerSnapshot(
        state=TimerState.WORKING,
        work_elapsed_sec=60.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=2640.0,
        reminder_active=False,
    )
    ended = TimerSnapshot(
        state=TimerState.RESTING,
        work_elapsed_sec=0.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=False,
        rest_remaining_sec=120.0,
    )

    window.on_timer_updated(active)
    calls_before_end = store.calls
    window.on_timer_updated(ended)

    assert store.calls == calls_before_end + 1
    assert "11 分鐘" in window._summary._work_label.text()


@pytest.mark.qt
def test_main_window_stream_error_shows_overlay_and_clears_presence(
    qtbot: pytest.QtBot, tmp_path: object
) -> None:
    from src.ui.main_window import MainWindow

    window = MainWindow(
        AppConfig(),
        config_path=str(tmp_path / "cfg.yaml"),
    )
    qtbot.addWidget(window)

    window.on_presence_changed(True)
    assert window._presence_badge._text_label.text() == "有人"

    window.on_connection_status("stream_error")

    assert window._presence_badge._text_label.text() == "無人"
    assert window._preview._overlay.text() == "影像異常"


# ---------------------------------------------------------------------------
# T3 Tests — PreviewView ROI 留邊換算（§4.3）與文字覆蓋層分離（§4.9）
# ---------------------------------------------------------------------------


def _make_frame(width: int, height: int) -> object:
    import numpy as np

    from src.types import Frame

    image = np.zeros((height, width, 3), dtype=np.uint8)
    return Frame(image=image, width=width, height=height, timestamp=0.0)


@pytest.mark.qt
def test_preview_view_roi_conversion_compensates_letterbox(qtbot: pytest.QtBot) -> None:
    """640x360 影格放入 400x400 widget：scaled=400x225、上下留邊約 87px。

    框選座標需扣除留邊偏移、以實際顯示影像尺寸正規化（§4.3）。
    """
    from src.types import BBox
    from src.ui.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.setFixedSize(400, 400)
    view.show()
    qtbot.waitExposed(view)

    view.set_frame(_make_frame(640, 360))
    view.set_edit_mode(True)

    signals: list[object] = []
    view.roi_committed.connect(signals.append)

    qtbot.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(40, 137))
    qtbot.mouseMove(view, QPoint(240, 237))
    qtbot.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(240, 237))

    assert len(signals) == 1
    roi = signals[0]
    assert isinstance(roi, BBox)
    # 顯示矩形：x∈[0,400)、y∈[87.5, 312.5)（留邊 (400-225)/2）
    assert roi.x == pytest.approx(40 / 400, abs=0.01)
    assert roi.y == pytest.approx((137 - 87.5) / 225, abs=0.01)
    assert roi.w == pytest.approx(200 / 400, abs=0.01)
    assert roi.h == pytest.approx(100 / 225, abs=0.01)


@pytest.mark.qt
def test_preview_view_roi_clamped_to_image_area(qtbot: pytest.QtBot) -> None:
    """框選超出影像區域（拖進留邊）時，結果需 clamp 至 [0,1]（§4.3）。"""
    from src.types import BBox
    from src.ui.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.setFixedSize(400, 400)
    view.show()
    qtbot.waitExposed(view)

    view.set_frame(_make_frame(640, 360))
    view.set_edit_mode(True)

    signals: list[object] = []
    view.roi_committed.connect(signals.append)

    # 從上方留邊一路拖到下方留邊：y 應 clamp 成 [0,1]
    qtbot.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(100, 10))
    qtbot.mouseMove(view, QPoint(300, 390))
    qtbot.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(300, 390))

    assert len(signals) == 1
    roi = signals[0]
    assert isinstance(roi, BBox)
    assert roi.y == pytest.approx(0.0, abs=0.01)
    assert roi.h == pytest.approx(1.0, abs=0.01)
    assert roi.x == pytest.approx(100 / 400, abs=0.01)
    assert roi.w == pytest.approx(200 / 400, abs=0.01)


@pytest.mark.qt
def test_preview_view_no_frame_selection_clamped_to_widget(qtbot: pytest.QtBot) -> None:
    """§4.8：尚無影格的 fallback 換算也必須 clamp，不得產出 x+w>1 的越界 ROI。

    滑鼠拖曳因 Qt mouse grab 可超出 widget 邊界，框選矩形可為負或超界。
    """
    from PySide6.QtCore import QRect

    from src.types import BBox
    from src.ui.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.setFixedSize(400, 300)
    view.show()
    qtbot.waitExposed(view)
    view.set_edit_mode(True)

    # 拖出右下邊界：(350,250)→(450,350)
    roi = view._roi_from_selection(QRect(350, 250, 100, 100))
    assert isinstance(roi, BBox)
    assert roi.x == pytest.approx(350 / 400)
    assert roi.y == pytest.approx(250 / 300)
    assert roi.x + roi.w <= 1.0
    assert roi.y + roi.h <= 1.0

    # 拖出左上邊界：負座標需 clamp 回 0
    roi = view._roi_from_selection(QRect(-50, -50, 100, 100))
    assert isinstance(roi, BBox)
    assert roi.x == pytest.approx(0.0)
    assert roi.y == pytest.approx(0.0)

    # 完全落在 widget 之外：拒絕提交
    assert view._roi_from_selection(QRect(450, 350, 50, 50)) is None


@pytest.mark.qt
def test_main_window_roi_commit_clamps_out_of_range_roi(
    qtbot: pytest.QtBot, tmp_path: object
) -> None:
    """§4.8 防鎖死：寫檔前 clamp，越界 roi 不得進 config.yaml 害下次啟動被拒。"""
    from src.config import load_config, save_config
    from src.types import BBox
    from src.ui.main_window import MainWindow
    from src.ui.settings_schema import set_value

    cfg_path = str(tmp_path / "cfg.yaml")  # type: ignore[operator]
    save_config(set_value(AppConfig(), "source.type", "webcam"), cfg_path)

    window = MainWindow(AppConfig(), FakeSummaryStore(), config_path=cfg_path)
    qtbot.addWidget(window)

    emitted: list[object] = []
    window.roi_changed.connect(emitted.append)

    window._on_roi_committed(BBox(0.875, 0.25, 0.25, 0.25))

    saved = load_config(cfg_path)
    assert saved.presence.roi == BBox(0.875, 0.25, 0.125, 0.25)
    assert emitted == [BBox(0.875, 0.25, 0.125, 0.25)]


@pytest.mark.qt
def test_preview_view_roi_drag_entirely_in_margin_rejected(qtbot: pytest.QtBot) -> None:
    """完全落在留邊內的框選不得提交（不發 signal）（§4.3）。"""
    from src.ui.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.setFixedSize(400, 400)
    view.show()
    qtbot.waitExposed(view)

    view.set_frame(_make_frame(640, 360))
    view.set_edit_mode(True)

    signals: list[object] = []
    view.roi_committed.connect(signals.append)

    # 上方留邊為 y < 87，整個框選落在其中
    qtbot.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(20, 10))
    qtbot.mouseMove(view, QPoint(300, 60))
    qtbot.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(300, 60))

    assert len(signals) == 0


@pytest.mark.qt
def test_preview_view_hint_survives_frame_updates(qtbot: pytest.QtBot) -> None:
    """set_edit_mode(True) 後連續 set_frame，提示文字仍可見（§4.9）。"""
    from src.ui.strings import ROI_HINT
    from src.ui.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.setFixedSize(400, 400)
    view.show()
    qtbot.waitExposed(view)

    view.set_edit_mode(True)
    for _ in range(3):
        view.set_frame(_make_frame(640, 360))

    assert view._overlay.isVisible()
    assert view._overlay.text() == ROI_HINT


@pytest.mark.qt
def test_preview_view_overlay_text_survives_frame_updates(qtbot: pytest.QtBot) -> None:
    """set_overlay_text 後連續 set_frame，覆蓋文字仍可見（§4.9）。"""
    from src.ui.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.setFixedSize(400, 400)
    view.show()
    qtbot.waitExposed(view)

    view.set_overlay_text("影像異常")
    for _ in range(3):
        view.set_frame(_make_frame(640, 360))

    assert view._overlay.isVisible()
    assert view._overlay.text() == "影像異常"


@pytest.mark.qt
def test_preview_view_clear_overlay_text_hides_overlay(qtbot: pytest.QtBot) -> None:
    """set_overlay_text('') 應清除並隱藏覆蓋層（§4.9）。"""
    from src.ui.widgets.preview_view import PreviewView

    view = PreviewView()
    qtbot.addWidget(view)
    view.setFixedSize(400, 400)
    view.show()
    qtbot.waitExposed(view)

    view.set_overlay_text("影像異常")
    view.set_overlay_text("")

    assert not view._overlay.isVisible()
    assert view._overlay.text() == ""


# ---------------------------------------------------------------------------
# T8 Tests — §4.6 tray 槽方法、§4.11 暫停同步、§4.7 ROI 端磁碟基底
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_tray_on_timer_updated_slot_updates_tooltip(qtbot: pytest.QtBot) -> None:
    """§4.6：TrayIcon.on_timer_updated(snapshot) 薄槽方法更新 tooltip。"""
    from src.ui.tray import TrayIcon

    tray = TrayIcon()
    qtbot.addWidget(QWidget())
    snapshot = TimerSnapshot(
        state=TimerState.WORKING,
        work_elapsed_sec=10.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=100.0,
        reminder_active=False,
    )

    tray.on_timer_updated(snapshot)

    assert "工作中" in tray.toolTip()


@pytest.mark.qt
def test_tray_on_connection_status_slot_updates_tooltip(qtbot: pytest.QtBot) -> None:
    """§4.6：TrayIcon.on_connection_status(status 字串) 薄槽方法更新 tooltip。"""
    from src.ui.tray import TrayIcon

    tray = TrayIcon()
    qtbot.addWidget(QWidget())

    tray.on_connection_status("connected")

    assert "已連線" in tray.toolTip()


@pytest.mark.qt
def test_action_bar_set_paused_syncs_button_without_emitting(qtbot: pytest.QtBot) -> None:
    """§4.11：ActionBar.set_paused 同步 checked 與文字，且不得重發 pause_toggled。"""
    from src.ui.strings import ACTION_PAUSE, ACTION_RESUME
    from src.ui.widgets.action_bar import ActionBar

    bar = ActionBar()
    qtbot.addWidget(bar)
    emitted: list[bool] = []
    bar.pause_toggled.connect(emitted.append)

    bar.set_paused(True)
    assert bar._pause_btn.isChecked() is True
    assert bar._pause_btn.text() == ACTION_RESUME

    bar.set_paused(False)
    assert bar._pause_btn.isChecked() is False
    assert bar._pause_btn.text() == ACTION_PAUSE

    assert emitted == []


@pytest.mark.qt
def test_action_bar_click_after_external_set_paused_emits_opposite(
    qtbot: pytest.QtBot,
) -> None:
    """§4.11：外部 set_paused(True) 後，使用者點擊應發出 pause_toggled(False)。"""
    from src.ui.widgets.action_bar import ActionBar

    bar = ActionBar()
    qtbot.addWidget(bar)
    bar.set_paused(True)

    emitted: list[bool] = []
    bar.pause_toggled.connect(emitted.append)
    bar._pause_btn.click()

    assert emitted == [False]


@pytest.mark.qt
def test_main_window_set_paused_forwards_to_action_bar(
    qtbot: pytest.QtBot, tmp_path: object
) -> None:
    """§4.11：MainWindow.set_paused 轉發至 ActionBar，且不得重發 request_pause。"""
    from src.ui.main_window import MainWindow

    window = MainWindow(
        AppConfig(),
        FakeSummaryStore(),
        config_path=str(tmp_path / "cfg.yaml"),
    )
    qtbot.addWidget(window)
    emitted: list[bool] = []
    window.request_pause.connect(emitted.append)

    window.set_paused(True)

    assert window._actions._pause_btn.isChecked() is True
    assert emitted == []


@pytest.mark.qt
def test_main_window_roi_commit_uses_disk_config_as_base(
    qtbot: pytest.QtBot, tmp_path: object
) -> None:
    """§4.7 ROI 端：先存設定（磁碟有新值）→ ROI 重框寫檔後設定值保留。"""
    from src.config import load_config, save_config
    from src.types import BBox
    from src.ui.main_window import MainWindow
    from src.ui.settings_schema import set_value

    cfg_path = str(tmp_path / "cfg.yaml")  # type: ignore[operator]
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


# ---------------------------------------------------------------------------
# M4 Tests — tooltip and clear button
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_settings_widgets_have_tooltip(qtbot: pytest.QtBot, tmp_path: object) -> None:
    from src.config import AppConfig
    from src.ui.settings import SettingsWindow

    window = SettingsWindow(AppConfig(), config_path=str(tmp_path / "config.yaml"))
    qtbot.addWidget(window)

    for key in ("reminder.method", "force_lock.enabled", "timer.rest_count_mode"):
        widget = window._widgets[key]
        assert isinstance(widget, QWidget)
        assert widget.toolTip() != "", f"Widget for {key} has no tooltip"


@pytest.mark.qt
def test_settings_has_clear_button(qtbot: pytest.QtBot, tmp_path: object) -> None:
    from src.config import AppConfig
    from src.ui.settings import SettingsWindow
    from src.ui.settings_schema import CATEGORIES
    from src.ui.strings import CLEAR_DATA_BUTTON

    window = SettingsWindow(AppConfig(), config_path=str(tmp_path / "config.yaml"))
    qtbot.addWidget(window)

    record_index = list(CATEGORIES).index("紀錄")
    page = window._stack.widget(record_index)
    buttons = [b for b in page.findChildren(QPushButton) if b.text() == CLEAR_DATA_BUTTON]
    assert len(buttons) == 1

    with qtbot.waitSignal(window.clear_data_requested, timeout=1000):
        qtbot.mouseClick(buttons[0], Qt.MouseButton.LeftButton)


# ---------------------------------------------------------------------------
# INT Tests — clear_data_requested signal from MainWindow
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_main_window_emits_clear_requested(qtbot: pytest.QtBot, tmp_path: object) -> None:
    from src.ui.main_window import MainWindow

    window = MainWindow(
        AppConfig(),
        FakeSummaryStore(),
        config_path=str(tmp_path / "main-window.yaml"),
    )
    qtbot.addWidget(window)

    with qtbot.waitSignal(window.clear_data_requested, timeout=1000):
        qtbot.mouseClick(window._clear_data_btn, Qt.MouseButton.LeftButton)
