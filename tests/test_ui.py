from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QWidget

from src.config import AppConfig
from src.ui.settings_schema import SCHEMA


def test_main_window_can_be_created(qtbot: pytest.QtBot) -> None:
    from src.ui.main_window import MainWindow

    window = MainWindow(AppConfig())
    qtbot.addWidget(window)

    assert window.preview_label is not None


def test_main_window_emits_normalized_roi_from_drag(qtbot: pytest.QtBot) -> None:
    from src.types import BBox
    from src.ui.main_window import MainWindow

    window = MainWindow(AppConfig())
    qtbot.addWidget(window)
    window.show()
    window.preview_label.resize(500, 400)

    with qtbot.waitSignal(window.roi_changed, timeout=3000) as blocker:
        qtbot.mousePress(window.preview_label, Qt.MouseButton.LeftButton, pos=QPoint(10, 20))
        qtbot.mouseMove(window.preview_label, QPoint(110, 120))
        qtbot.mouseRelease(window.preview_label, Qt.MouseButton.LeftButton, pos=QPoint(110, 120))

    roi = blocker.args[0]
    assert isinstance(roi, BBox)
    assert roi.x == pytest.approx(0.02, abs=0.01)
    assert roi.y == pytest.approx(0.05, abs=0.01)
    assert roi.w == pytest.approx(0.2, abs=0.01)
    assert roi.h == pytest.approx(0.25, abs=0.01)


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


def test_tray_icon_can_be_created() -> None:
    from src.ui.tray import TrayIcon

    tray = TrayIcon()

    assert tray.contextMenu() is not None
