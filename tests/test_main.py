from __future__ import annotations

import inspect

import numpy as np
import pytest
from PySide6.QtCore import Qt, QThread

import src.main
from src.app.worker import DetectionWorker
from src.main import _shutdown_worker_thread
from src.presence import PresenceEvaluator
from src.reminder.popup import PopupReminder
from src.reminder.return_prompt import ReturnPromptDialog
from src.timer_engine import TimerEngine
from src.types import BBox, Detection, Frame, ReminderContext, RestCountMode, TimerState


class FakeWorker:
    def __init__(self) -> None:
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


class FakeThread:
    def __init__(self, *, wait_result: bool) -> None:
        self.quit_calls = 0
        self.wait_calls: list[int] = []
        self.terminate_calls = 0
        self._wait_result = wait_result

    def quit(self) -> None:
        self.quit_calls += 1

    def wait(self, timeout: int) -> bool:
        self.wait_calls.append(timeout)
        return self._wait_result

    def terminate(self) -> None:
        self.terminate_calls += 1


class FakeFrames:
    def __init__(self, frames: list[Frame | None], is_opened: bool = True) -> None:
        self._frames = list(frames)
        self._index = 0
        self._is_opened = is_opened

    def latest(self) -> Frame | None:
        if not self._frames:
            return None
        if self._index >= len(self._frames):
            return self._frames[-1]
        frame = self._frames[self._index]
        self._index += 1
        return frame

    @property
    def is_opened(self) -> bool:
        return self._is_opened


class FakeDetector:
    def __init__(self, detections: list[list[Detection]]) -> None:
        self._detections = list(detections)
        self._index = 0

    def detect(self, frame: Frame) -> list[Detection]:
        del frame
        if self._index >= len(self._detections):
            return self._detections[-1]
        result = self._detections[self._index]
        self._index += 1
        return result


class FakeStore:
    def init_schema(self) -> None:
        return None

    def log_session(
        self, kind: str, start_ts: object, end_ts: object, duration_sec: int, ended_by: str
    ) -> int:
        del kind, start_ts, end_ts, duration_sec, ended_by
        return 1

    def close(self) -> None:
        return None


class FakeClock:
    def __init__(self, start: float = 0.0, step: float = 0.6) -> None:
        self.current = start
        self.step = step

    def __call__(self) -> float:
        value = self.current
        self.current += self.step
        return value


def _frame() -> Frame:
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    return Frame(image=image, width=10, height=10, timestamp=0.0)


def _qualifying_detection() -> Detection:
    return Detection(BBox(0.2, 0.2, 0.3, 0.4), 0.9)


def _make_worker(detector: FakeDetector, *, rest_mode: RestCountMode) -> DetectionWorker:
    return DetectionWorker(
        frames=FakeFrames([_frame()] * 24),
        detector=detector,
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(0.5, 5.0, 0.5, 3.0, rest_mode),
        store=FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=FakeClock(step=0.6),
    )


def _stop_worker_thread(worker: DetectionWorker, thread: QThread) -> None:
    worker.stop()
    thread.quit()
    if not thread.wait(1500):
        thread.terminate()
        thread.wait(500)


def test_shutdown_worker_thread_stops_worker_and_quits_thread() -> None:
    worker = FakeWorker()
    thread = FakeThread(wait_result=True)

    _shutdown_worker_thread(worker, thread)

    assert worker.stop_calls == 1
    assert thread.quit_calls == 1
    assert thread.wait_calls == [1500]
    assert thread.terminate_calls == 0


def test_shutdown_worker_thread_terminates_when_thread_does_not_exit() -> None:
    worker = FakeWorker()
    thread = FakeThread(wait_result=False)

    _shutdown_worker_thread(worker, thread)

    assert worker.stop_calls == 1
    assert thread.quit_calls == 1
    assert thread.wait_calls == [1500, 500]
    assert thread.terminate_calls == 1


def test_failed_signal_not_connected_to_quit() -> None:
    source = inspect.getsource(src.main.main)
    assert "worker.failed.connect(lambda _message: app.quit())" not in source


def test_main_imports_new_modules() -> None:
    assert hasattr(src.main, "setup_logging")
    assert hasattr(src.main, "suppress_decoder_noise")
    assert hasattr(src.main, "ThemeManager")


def test_main_uses_request_worker_apis_for_ui_commands() -> None:
    source = inspect.getsource(src.main.main)

    assert "reminder.start_rest.connect(lambda: worker.request_start_rest())" in source
    assert (
        "return_prompt_dialog.confirmed.connect(lambda: worker.request_confirm_return())"
        in source
    )
    assert "window.roi_changed.connect(lambda roi: worker.request_set_roi(roi))" in source
    assert "worker.request_pause()" in source
    assert "worker.request_resume()" in source


@pytest.mark.qt
def test_qthread_return_prompt_confirmed_bridge_starts_new_round(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    no_detect: list[Detection] = []
    detector = FakeDetector([[qd], [qd], no_detect, no_detect, [qd], [qd], [qd], [qd], [qd]])
    worker = _make_worker(detector, rest_mode=RestCountMode.FIXED)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    dialog = ReturnPromptDialog()
    qtbot.addWidget(dialog)
    snapshots: list[object] = []
    worker.timer_updated.connect(snapshots.append)
    worker.return_prompt.connect(dialog.show_prompt)
    dialog.confirmed.connect(lambda: worker.request_confirm_return())

    try:
        thread.start()
        qtbot.waitUntil(dialog.isVisible, timeout=5000)
        marker = len(snapshots)
        qtbot.mouseClick(dialog._confirm_btn, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: any(
                getattr(s, "state", None) == TimerState.WORKING for s in snapshots[marker:]
            ),
            timeout=3000,
        )
        qtbot.waitUntil(
            lambda: any(getattr(s, "work_elapsed_sec", 0.0) > 0 for s in snapshots[marker:]),
            timeout=3000,
        )
    finally:
        _stop_worker_thread(worker, thread)


@pytest.mark.qt
def test_qthread_popup_start_rest_bridge_enters_resting(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    detector = FakeDetector([[qd]] * 12)
    worker = _make_worker(detector, rest_mode=RestCountMode.FIXED)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    popup = PopupReminder()
    qtbot.addWidget(popup)
    snapshots: list[object] = []
    worker.timer_updated.connect(snapshots.append)
    worker.reminder_show.connect(popup.show)
    popup.start_rest.connect(lambda: worker.request_start_rest())

    try:
        thread.start()
        qtbot.waitUntil(popup.isVisible, timeout=5000)
        marker = len(snapshots)
        qtbot.mouseClick(popup.dismiss_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: any(
                getattr(s, "state", None) == TimerState.RESTING for s in snapshots[marker:]
            ),
            timeout=3000,
        )
    finally:
        _stop_worker_thread(worker, thread)


# ---------------------------------------------------------------------------
# INT Tests — _maybe_build_force_lock
# ---------------------------------------------------------------------------


def test_maybe_build_force_lock_returns_none_when_disabled() -> None:
    from src.config import AppConfig, ForceLockConfig
    from src.main import _maybe_build_force_lock

    cfg = AppConfig(force_lock=ForceLockConfig(enabled=False))

    assert _maybe_build_force_lock(cfg) is None


@pytest.mark.qt
def test_maybe_build_force_lock_returns_controller_when_enabled(qtbot: pytest.QtBot) -> None:
    from src.app.force_lock_controller import ForceLockController
    from src.config import AppConfig, ForceLockConfig
    from src.main import _maybe_build_force_lock

    cfg = AppConfig(force_lock=ForceLockConfig(enabled=True))

    controller = _maybe_build_force_lock(cfg)

    assert isinstance(controller, ForceLockController)
