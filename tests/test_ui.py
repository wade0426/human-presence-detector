from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt

from src.config import AppConfig


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


def test_settings_dialog_can_be_created(qtbot: pytest.QtBot) -> None:
    from src.ui.settings import SettingsDialog

    dialog = SettingsDialog(AppConfig())
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() != ""


def test_tray_icon_can_be_created() -> None:
    from src.ui.tray import TrayIcon

    tray = TrayIcon()

    assert tray.contextMenu() is not None
