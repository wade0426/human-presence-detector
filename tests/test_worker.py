from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any

import numpy as np
import pytest

from src.presence import PresenceEvaluator
from src.timer_engine import TimerEngine
from src.types import BBox, Detection, Frame, ReminderContext, RestCountMode, TimerState

# ---------------------------------------------------------------------------
# Fake helpers
# ---------------------------------------------------------------------------


class FakeFrames:
    """Implements FrameProvider: latest() / is_opened."""

    def __init__(self, frames: list[Frame | None], is_opened: bool = False) -> None:
        self._frames = list(frames)
        self._index = 0
        self._is_opened = is_opened
        self.release_calls = 0

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

    def release(self) -> None:
        self.release_calls += 1


class FakeSource:
    """Legacy helper kept for backward compatibility; NOT used as FrameProvider."""

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

    def close(self) -> None:
        pass


class CloseTrackingStore(FakeStore):
    def __init__(self) -> None:
        super().__init__()
        self.close_thread_ids: list[int] = []

    def close(self) -> None:
        self.close_thread_ids.append(threading.get_ident())


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _frame() -> Frame:
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    return Frame(image=image, width=10, height=10, timestamp=0.0)


def _qualifying_detection() -> Detection:
    return Detection(BBox(0.2, 0.2, 0.3, 0.4), 0.9)


def _make_worker(
    frames: Any,
    detector: Any | None = None,
    timer_engine: Any | None = None,
    store: Any | None = None,
    clock: Any | None = None,
) -> Any:
    from src.app.worker import DetectionWorker

    return DetectionWorker(
        frames=frames,
        detector=detector or FakeDetector([[]]),
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=timer_engine or TimerEngine(10.0, 5.0, 5.0, 3.0),
        store=store or FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=clock or FakeClock(),
    )


# ---------------------------------------------------------------------------
# Test 1: 達門檻 → 發 reminder_show
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_worker_emits_reminder_show_when_timer_triggers(qtbot: pytest.QtBot) -> None:
    """Qualifying detections accumulate past the work threshold → reminder_show emitted."""
    from src.app.worker import DetectionWorker

    qd = _qualifying_detection()
    frames = FakeFrames([_frame(), _frame(), _frame(), _frame(), _frame()])
    worker = DetectionWorker(
        frames=frames,
        detector=FakeDetector([[qd], [qd], [qd], [qd], [qd]]),
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(0.5, 5.0, 5.0, 3.0),
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


# ---------------------------------------------------------------------------
# Test 2: start_rest() → 後續 timer_updated 快照 state == RESTING
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_start_rest_transitions_to_resting(qtbot: pytest.QtBot) -> None:
    """After reaching REMINDING, start_rest() should produce a RESTING snapshot."""
    from src.app.worker import DetectionWorker

    qd = _qualifying_detection()
    # work_threshold_sec=0.5; each clock step=0.6 so 1 step triggers REMINDING
    engine = TimerEngine(0.5, 5.0, 5.0, 3.0, RestCountMode.FIXED)
    store = FakeStore()
    frames = FakeFrames([_frame(), _frame(), _frame(), _frame(), _frame()])
    worker = DetectionWorker(
        frames=frames,
        detector=FakeDetector([[qd], [qd], [qd], [qd], [qd]]),
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=engine,
        store=store,
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=FakeClock(step=0.6),
    )

    snapshots: list[Any] = []
    worker.timer_updated.connect(snapshots.append)

    # Wait for reminder_show, meaning we're in REMINDING
    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.reminder_show, timeout=3000):
        thread.start()

    # Now call start_rest from this thread (simulating user action)
    worker.start_rest()

    # Wait for a snapshot with RESTING state
    def _has_resting() -> bool:
        return any(s.state == TimerState.RESTING for s in snapshots)

    qtbot.waitUntil(_has_resting, timeout=3000)
    worker.stop()
    thread.join(timeout=1.0)

    resting_snaps = [s for s in snapshots if s.state == TimerState.RESTING]
    assert len(resting_snaps) >= 1


# ---------------------------------------------------------------------------
# Test 3: 休息滿足後回座 → 發 return_prompt
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_worker_emits_return_prompt_after_sufficient_rest(qtbot: pytest.QtBot) -> None:
    """After enough rest + presence, return_prompt signal is emitted."""
    from src.app.worker import DetectionWorker

    qd = _qualifying_detection()
    # FIXED mode: required_rest_sec=0.5; step=1.0 so rest completes quickly
    engine = TimerEngine(0.5, 5.0, 0.5, 3.0, RestCountMode.FIXED)
    # Pattern: present → REMINDING → absent (REST_STARTED) → present (RETURN_PROMPT)
    frames = FakeFrames(
        [_frame()] * 4  # always return a frame
    )
    no_detect: list[Detection] = []
    # Detections: 2 present → trigger reminder, then absent → REST, then present again
    detector = FakeDetector([[qd], [qd], no_detect, no_detect, [qd], [qd], [qd]])

    worker = DetectionWorker(
        frames=frames,
        detector=detector,
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=engine,
        store=FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=FakeClock(step=0.6),
    )

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.return_prompt, timeout=5000):
        thread.start()
    worker.stop()
    thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# Test 4: confirm_return() → store.log_session 出現一筆 work
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_confirm_return_logs_session(qtbot: pytest.QtBot) -> None:
    """confirm_return() → REST_ENDED + WORK_STARTED; log_session called with 'rest'."""
    from src.app.worker import DetectionWorker

    qd = _qualifying_detection()
    engine = TimerEngine(0.5, 5.0, 0.5, 3.0, RestCountMode.FIXED)
    store = FakeStore()
    frames = FakeFrames([_frame()] * 10)
    no_detect: list[Detection] = []
    detector = FakeDetector([[qd], [qd], no_detect, no_detect, [qd], [qd], [qd], [qd], [qd]])

    worker = DetectionWorker(
        frames=frames,
        detector=detector,
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=engine,
        store=store,
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=FakeClock(step=0.6),
    )

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.return_prompt, timeout=5000):
        thread.start()

    # confirm_return → REST_ENDED logged, WORK_STARTED new round
    worker.confirm_return()

    def _has_rest_log() -> bool:
        return any(r[0] == "rest" for r in store.rows)

    qtbot.waitUntil(_has_rest_log, timeout=3000)
    worker.stop()
    thread.join(timeout=1.0)

    rest_rows = [r for r in store.rows if r[0] == "rest"]
    assert len(rest_rows) >= 1


# ---------------------------------------------------------------------------
# Test 5: pause() → 立即收到 SUSPENDED 快照；暫停期間不再有偵測
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_pause_emits_suspended_snapshot_immediately(qtbot: pytest.QtBot) -> None:
    """pause() must immediately emit a timer_updated with state==SUSPENDED."""
    from src.app.worker import DetectionWorker

    qd = _qualifying_detection()
    engine = TimerEngine(0.5, 5.0, 5.0, 3.0)
    frames = FakeFrames([_frame()] * 20)
    detector = FakeDetector([[qd]] * 20)

    snapshots: list[Any] = []
    worker = DetectionWorker(
        frames=frames,
        detector=detector,
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=engine,
        store=FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=FakeClock(step=0.6),
    )
    worker.timer_updated.connect(snapshots.append)

    # Wait for worker to be in WORKING state (at least 1 timer_updated)
    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()

    def _has_working() -> bool:
        return any(s.state == TimerState.WORKING for s in snapshots)

    qtbot.waitUntil(_has_working, timeout=3000)

    # Now pause — should immediately emit a SUSPENDED snapshot
    n_before = len(snapshots)
    worker.pause()

    def _has_suspended() -> bool:
        return any(s.state == TimerState.SUSPENDED for s in snapshots)

    qtbot.waitUntil(_has_suspended, timeout=1000)

    # While paused, count new snapshots for a bit
    count_after_pause = len([s for s in snapshots if s.state == TimerState.SUSPENDED])
    assert count_after_pause >= 1

    worker.stop()
    thread.join(timeout=1.0)

    # The SUSPENDED snapshot must have appeared right after the pause call
    assert any(s.state == TimerState.SUSPENDED for s in snapshots[n_before:])


# ---------------------------------------------------------------------------
# Test 6: 連線狀態 (latest()/is_opened) → connection_status
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_worker_emits_connecting_at_start(qtbot: pytest.QtBot) -> None:
    frames = FakeFrames([None], is_opened=False)
    worker = _make_worker(frames)

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.connection_status, timeout=3000) as blocker:
        thread.start()
    worker.stop()
    thread.join(timeout=1.0)

    assert blocker.args == ["connecting"]


@pytest.mark.qt
def test_worker_emits_no_signal_when_source_open_but_no_frame(qtbot: pytest.QtBot) -> None:
    frames = FakeFrames([None], is_opened=True)
    worker = _make_worker(frames)

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
    frames = FakeFrames([None], is_opened=False)
    worker = _make_worker(frames)

    statuses: list[str] = []
    worker.connection_status.connect(statuses.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    qtbot.waitUntil(lambda: "reconnecting" in statuses, timeout=3000)
    worker.stop()
    thread.join(timeout=1.0)

    assert statuses[:2] == ["connecting", "reconnecting"]


# ---------------------------------------------------------------------------
# Test 7: stop() → FakeFrames.release_calls == 0 (釋放由 grabber 負責)
# ---------------------------------------------------------------------------


def test_worker_stop_does_not_release_frames() -> None:
    """stop() should NOT call release on the FrameProvider (grabber handles it)."""
    frames = FakeFrames([_frame()])
    worker = _make_worker(frames)

    worker.stop()

    assert frames.release_calls == 0


# ---------------------------------------------------------------------------
# Additional: failed signal when store init crashes
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_worker_emits_failed_when_store_init_crashes(qtbot: pytest.QtBot) -> None:
    from src.app.worker import DetectionWorker

    frames = FakeFrames([_frame()])
    worker = DetectionWorker(
        frames=frames,
        detector=FakeDetector([[]]),
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(10.0, 5.0, 5.0, 3.0),
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


def test_worker_closes_store_from_worker_thread() -> None:
    store = CloseTrackingStore()
    frames = FakeFrames([None], is_opened=False)
    worker = _make_worker(frames, store=store)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    time.sleep(0.05)
    worker.stop()
    thread.join(timeout=1.0)

    assert store.close_thread_ids == [thread.ident]
