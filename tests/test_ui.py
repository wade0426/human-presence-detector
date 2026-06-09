from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QWidget

from src.config import AppConfig
from src.logging_store import TodaySummary
from src.types import TimerSnapshot, TimerState
from src.ui.settings_schema import SCHEMA


class FakeSummaryStore:
    def __init__(self, summary: TodaySummary | None = None) -> None:
        self._summary = summary or TodaySummary(0, 0, 0)

    def today_summary(self) -> TodaySummary:
        return self._summary


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
