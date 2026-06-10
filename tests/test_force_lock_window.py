from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from src.ui.force_lock_window import ForceLockCountdownWindow
from src.ui.strings import FORCE_LOCK_CANCEL


@pytest.mark.qt
def test_cancel_button_visible_only_when_cancellable(qtbot) -> None:
    # cancellable=True 時有取消鈕
    win_cancellable = ForceLockCountdownWindow(seconds=5, cancellable=True)
    qtbot.addWidget(win_cancellable)
    from PySide6.QtWidgets import QPushButton
    cancel_btns = win_cancellable.findChildren(QPushButton)
    assert any(b.text() == FORCE_LOCK_CANCEL for b in cancel_btns)

    # cancellable=False 時沒有取消鈕
    win_no_cancel = ForceLockCountdownWindow(seconds=5, cancellable=False)
    qtbot.addWidget(win_no_cancel)
    cancel_btns2 = win_no_cancel.findChildren(QPushButton)
    assert not any(b.text() == FORCE_LOCK_CANCEL for b in cancel_btns2)


@pytest.mark.qt
def test_emits_cancelled_on_click(qtbot) -> None:
    win = ForceLockCountdownWindow(seconds=10, cancellable=True)
    qtbot.addWidget(win)
    win.start()

    from PySide6.QtWidgets import QPushButton
    cancel_btn = next(
        b for b in win.findChildren(QPushButton) if b.text() == FORCE_LOCK_CANCEL
    )
    with qtbot.waitSignal(win.cancelled, timeout=2000):
        qtbot.mouseClick(cancel_btn, Qt.MouseButton.LeftButton)


@pytest.mark.qt
def test_emits_expired_after_countdown(qtbot) -> None:
    win = ForceLockCountdownWindow(seconds=1, cancellable=False)
    qtbot.addWidget(win)
    with qtbot.waitSignal(win.expired, timeout=3000):
        win.start()
