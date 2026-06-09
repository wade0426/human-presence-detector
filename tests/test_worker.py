from __future__ import annotations

import threading
from datetime import datetime

import numpy as np
import pytest

from src.presence import PresenceEvaluator
from src.timer_engine import TimerEngine
from src.types import BBox, Detection, Frame, ReminderContext, ResetMode


class FakeSource:
    def __init__(self, frames: list[Frame | None]) -> None:
        self._frames = list(frames)
        self._index = 0
        self.release_calls = 0
        self.is_opened = False

    def read(self) -> Frame | None:
        if self._index >= len(self._frames):
            return self._frames[-1]
        frame = self._frames[self._index]
        self._index += 1
        return frame

    def release(self) -> None:
        self.release_calls += 1


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
    def __init__(self) -> None:
        self.schema_init_calls = 0
        self.rows: list[tuple[str, datetime, datetime, int, str]] = []

    def init_schema(self) -> None:
        self.schema_init_calls += 1

    def log_session(
        self, kind: str, start_ts: datetime, end_ts: datetime, duration_sec: int, ended_by: str
    ) -> int:
        self.rows.append((kind, start_ts, end_ts, duration_sec, ended_by))
        return len(self.rows)


class ExplodingStore(FakeStore):
    def init_schema(self) -> None:
        raise RuntimeError("boom")


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


def _make_worker(source: FakeSource) -> object:
    from src.app.worker import DetectionWorker

    return DetectionWorker(
        source=source,
        detector=FakeDetector([[]]),
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(10.0, 5.0, 5.0, ResetMode.DETECTION, 3.0, 2.0),
        store=FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=FakeClock(),
    )


@pytest.mark.qt
def test_worker_emits_frame_ready_after_running(qtbot: pytest.QtBot) -> None:
    from src.app.worker import DetectionWorker

    worker = DetectionWorker(
        source=FakeSource([_frame(), _frame(), _frame()]),
        detector=FakeDetector([[], [], []]),
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(10.0, 5.0, 5.0, ResetMode.DETECTION, 3.0, 2.0),
        store=FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=FakeClock(),
    )

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.frame_ready, timeout=3000):
        thread.start()
    worker.stop()
    thread.join(timeout=1.0)


@pytest.mark.qt
def test_worker_emits_connecting_at_start(qtbot: pytest.QtBot) -> None:
    source = FakeSource([None])
    source.is_opened = False
    worker = _make_worker(source)

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.connection_status, timeout=3000) as blocker:
        thread.start()
    worker.stop()
    thread.join(timeout=1.0)

    assert blocker.args == ["connecting"]


@pytest.mark.qt
def test_worker_emits_no_signal_when_source_open_but_no_frame(qtbot: pytest.QtBot) -> None:
    source = FakeSource([None])
    source.is_opened = True
    worker = _make_worker(source)

    statuses: list[str] = []
    worker.connection_status.connect(statuses.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    qtbot.waitUntil(lambda: "no_signal" in statuses, timeout=3000)
    worker.stop()
    thread.join(timeout=1.0)

    assert statuses[:2] == ["connecting", "no_signal"]


@pytest.mark.qt
def test_worker_emits_reconnecting_when_source_closed(qtbot: pytest.QtBot) -> None:
    source = FakeSource([None])
    source.is_opened = False
    worker = _make_worker(source)

    statuses: list[str] = []
    worker.connection_status.connect(statuses.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    qtbot.waitUntil(lambda: "reconnecting" in statuses, timeout=3000)
    worker.stop()
    thread.join(timeout=1.0)

    assert statuses[:2] == ["connecting", "reconnecting"]


@pytest.mark.qt
def test_worker_emits_reminder_show_when_timer_triggers(qtbot: pytest.QtBot) -> None:
    from src.app.worker import DetectionWorker

    qualifying_detection = Detection(BBox(0.2, 0.2, 0.3, 0.4), 0.9)
    worker = DetectionWorker(
        source=FakeSource([_frame(), _frame(), _frame()]),
        detector=FakeDetector(
            [[qualifying_detection], [qualifying_detection], [qualifying_detection]]
        ),
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(0.5, 5.0, 5.0, ResetMode.DETECTION, 3.0, 2.0),
        store=FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=FakeClock(step=0.6),
    )

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.reminder_show, timeout=3000):
        thread.start()
    worker.stop()
    thread.join(timeout=1.0)


@pytest.mark.qt
def test_worker_emits_failed_when_store_init_crashes(qtbot: pytest.QtBot) -> None:
    from src.app.worker import DetectionWorker

    worker = DetectionWorker(
        source=FakeSource([_frame()]),
        detector=FakeDetector([[]]),
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(10.0, 5.0, 5.0, ResetMode.DETECTION, 3.0, 2.0),
        store=ExplodingStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=FakeClock(),
    )

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.failed, timeout=3000) as blocker:
        thread.start()
    thread.join(timeout=1.0)

    assert blocker.args == ["boom"]


def test_worker_stop_releases_source() -> None:
    source = FakeSource([_frame()])
    from src.app.worker import DetectionWorker

    worker = DetectionWorker(
        source=source,
        detector=FakeDetector([[]]),
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(10.0, 5.0, 5.0, ResetMode.DETECTION, 3.0, 2.0),
        store=FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=FakeClock(),
    )

    worker.stop()

    assert source.release_calls == 1
