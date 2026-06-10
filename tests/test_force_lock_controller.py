from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal

from src.app.force_lock_controller import ForceLockController
from src.config import ForceLockConfig
from src.types import TimerSnapshot, TimerState


class FakeCountdownWindow(QObject):
    expired = Signal()
    cancelled = Signal()

    def __init__(self, seconds: int, cancellable: bool) -> None:
        super().__init__()
        self.seconds = seconds
        self.cancellable = cancellable
        self.started = False

    def start(self) -> None:
        self.started = True


def _resting_snapshot() -> TimerSnapshot:
    return TimerSnapshot(
        state=TimerState.RESTING,
        work_elapsed_sec=0.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=False,
    )


def _working_snapshot() -> TimerSnapshot:
    return TimerSnapshot(
        state=TimerState.WORKING,
        work_elapsed_sec=0.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=600.0,
        reminder_active=False,
    )


@pytest.mark.qt
def test_immediate_locks_on_trigger(qtbot) -> None:
    calls: list[None] = []
    config = ForceLockConfig(enabled=True, trigger="on_rest", warning_mode="immediate")
    controller = ForceLockController(config, lock_fn=lambda: calls.append(None) or True)

    controller.on_timer_updated(_resting_snapshot())

    assert len(calls) == 1


@pytest.mark.qt
def test_no_lock_when_policy_not_fired(qtbot) -> None:
    calls: list[None] = []
    config = ForceLockConfig(enabled=True, trigger="on_rest", warning_mode="immediate")
    controller = ForceLockController(config, lock_fn=lambda: calls.append(None) or True)

    controller.on_timer_updated(_working_snapshot())

    assert calls == []


@pytest.mark.qt
def test_countdown_cancel_does_not_lock(qtbot) -> None:
    calls: list[None] = []
    config = ForceLockConfig(
        enabled=True, trigger="on_rest", warning_mode="countdown_cancel", countdown_sec=5
    )
    controller = ForceLockController(
        config,
        lock_fn=lambda: calls.append(None) or True,
        window_factory=FakeCountdownWindow,
    )

    controller.on_timer_updated(_resting_snapshot())
    window = controller._countdown_window
    assert isinstance(window, FakeCountdownWindow)
    assert window.cancellable is True
    assert window.started is True

    window.cancelled.emit()

    assert calls == []
    assert controller._countdown_window is None


@pytest.mark.qt
def test_countdown_expire_locks(qtbot) -> None:
    calls: list[None] = []
    config = ForceLockConfig(
        enabled=True, trigger="on_rest", warning_mode="countdown_only", countdown_sec=5
    )
    controller = ForceLockController(
        config,
        lock_fn=lambda: calls.append(None) or True,
        window_factory=FakeCountdownWindow,
    )

    controller.on_timer_updated(_resting_snapshot())
    window = controller._countdown_window
    assert isinstance(window, FakeCountdownWindow)
    assert window.cancellable is False

    window.expired.emit()

    assert len(calls) == 1
    assert controller._countdown_window is None
