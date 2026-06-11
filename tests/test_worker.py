from __future__ import annotations

import itertools
import threading
import time
from datetime import datetime
from typing import Any

import numpy as np
import pytest

from src.presence import PresenceEvaluator
from src.timer_engine import TimerEngine
from src.types import (
    BBox,
    Detection,
    Frame,
    ReminderContext,
    RestCountMode,
    TimerEvent,
    TimerEventType,
    TimerState,
)

# ---------------------------------------------------------------------------
# Fake helpers
# ---------------------------------------------------------------------------


class FakeFrames:
    """Implements FrameProvider: latest() / is_opened.

    Mirrors the real FrameGrabber semantics: each queued frame is served once
    (timestamps advance while the stream is alive); after the queue is
    exhausted the *last* frame keeps being returned unchanged — i.e. a frozen
    stream whose timestamp no longer advances (proposal §4.2).
    """

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


class LiveFrames:
    """FrameProvider modelling a healthy live stream: every poll is fresh.

    Use this when a test must keep the detection loop running indefinitely
    (e.g. to observe loop-driven snapshots after a queued command), where a
    finite FakeFrames queue would freeze and trip the §4.2 staleness branch.
    """

    def __init__(self) -> None:
        self.release_calls = 0

    def latest(self) -> Frame:
        return _frame()

    @property
    def is_opened(self) -> bool:
        return True

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


_TS_COUNTER = itertools.count()


def _frame() -> Frame:
    """Build a frame with a unique, monotonically increasing timestamp.

    Real FrameGrabber frames carry advancing timestamps; the worker relies on
    timestamp freshness (§4.2), so every fabricated frame must be distinct.
    """
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    return Frame(image=image, width=10, height=10, timestamp=float(next(_TS_COUNTER)))


def _qualifying_detection() -> Detection:
    return Detection(BBox(0.2, 0.2, 0.3, 0.4), 0.9)


def _make_worker(
    frames: Any,
    detector: Any | None = None,
    timer_engine: Any | None = None,
    store: Any | None = None,
    clock: Any | None = None,
    logging_enabled: bool = True,
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
        logging_enabled=logging_enabled,
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
    # Enough distinct (fresh) frames to cover every detection cycle (§4.2).
    frames = FakeFrames([_frame() for _ in range(20)])
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
    frames = FakeFrames([_frame() for _ in range(10)])
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
    frames = FakeFrames([_frame() for _ in range(20)])
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


@pytest.mark.qt
def test_request_start_rest_is_applied_inside_run_loop(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    worker = _make_worker(
        FakeFrames([_frame() for _ in range(12)]),
        detector=FakeDetector([[qd]] * 12),
        timer_engine=TimerEngine(0.5, 5.0, 5.0, 3.0, RestCountMode.FIXED),
        clock=FakeClock(step=0.6),
    )

    snapshots: list[Any] = []
    worker.timer_updated.connect(snapshots.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    qtbot.waitUntil(lambda: any(s.state == TimerState.REMINDING for s in snapshots), timeout=3000)

    worker.request_start_rest()

    qtbot.waitUntil(lambda: any(s.state == TimerState.RESTING for s in snapshots), timeout=3000)
    worker.stop()
    thread.join(timeout=1.0)


@pytest.mark.qt
def test_request_confirm_return_resumes_working_and_elapsed_ticks(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    no_detect: list[Detection] = []
    detector = FakeDetector([[qd], [qd], no_detect, no_detect, [qd], [qd], [qd], [qd], [qd]])
    # LiveFrames: the loop must keep ticking after request_confirm_return is
    # drained, so the stream has to stay fresh for the whole test.
    worker = _make_worker(
        LiveFrames(),
        detector=detector,
        timer_engine=TimerEngine(0.5, 5.0, 0.5, 3.0, RestCountMode.FIXED),
        clock=FakeClock(step=0.6),
    )

    snapshots: list[Any] = []
    worker.timer_updated.connect(snapshots.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.return_prompt, timeout=5000):
        thread.start()

    marker = len(snapshots)
    worker.request_confirm_return()

    qtbot.waitUntil(
        lambda: any(s.state == TimerState.WORKING for s in snapshots[marker:]),
        timeout=3000,
    )
    qtbot.waitUntil(
        lambda: any(
            s.work_elapsed_sec > 0 for s in snapshots[marker:]
        ),
        timeout=3000,
    )
    worker.stop()
    thread.join(timeout=1.0)


@pytest.mark.qt
def test_request_pause_and_resume_work_while_run_loop_is_paused(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    worker = _make_worker(
        FakeFrames([_frame() for _ in range(20)]),
        detector=FakeDetector([[qd]] * 20),
        timer_engine=TimerEngine(100.0, 5.0, 5.0, 3.0),
        clock=FakeClock(step=0.6),
    )

    snapshots: list[Any] = []
    worker.timer_updated.connect(snapshots.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    qtbot.waitUntil(lambda: any(s.state == TimerState.WORKING for s in snapshots), timeout=3000)

    worker.request_pause()
    qtbot.waitUntil(lambda: any(s.state == TimerState.SUSPENDED for s in snapshots), timeout=3000)

    marker = len(snapshots)
    worker.request_resume()
    qtbot.waitUntil(
        lambda: any(s.state != TimerState.SUSPENDED for s in snapshots[marker:]),
        timeout=3000,
    )
    worker.stop()
    thread.join(timeout=1.0)


def test_request_set_roi_applies_last_value() -> None:
    worker = _make_worker(FakeFrames([None], is_opened=False))
    roi_a = BBox(0.1, 0.1, 0.3, 0.3)
    roi_b = BBox(0.2, 0.2, 0.4, 0.4)

    worker.request_set_roi(roi_a)
    worker.request_set_roi(roi_b)
    worker._drain_pending_commands()

    assert worker._presence_evaluator._roi == roi_b


# ---------------------------------------------------------------------------
# §4.2: 凍結影格（timestamp 不前進）必須視為無新影格 → 健康檢查 + 跳過偵測
# ---------------------------------------------------------------------------


class CountingDetector:
    """Counts detect() calls; always reports nobody present."""

    def __init__(self) -> None:
        self.calls = 0

    def detect(self, frame: Frame) -> list[Detection]:
        del frame
        self.calls += 1
        return []


@pytest.mark.qt
def test_worker_treats_frozen_frame_as_stale_and_stops_detecting(qtbot: pytest.QtBot) -> None:
    """One fresh frame, then latest() keeps returning the same frame
    (timestamp frozen) → health must degrade to TIMEOUT ("stream_error")
    and the detector must NOT be called again on the frozen frame.
    """
    from src.app.worker import DetectionWorker
    from src.capture.stream_health import StreamHealthMonitor

    clock = FakeClock(step=0.6)
    detector = CountingDetector()
    # Single queued frame; afterwards FakeFrames returns the same frozen frame.
    frames = FakeFrames([_frame()], is_opened=True)
    worker = DetectionWorker(
        frames=frames,
        detector=detector,
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(10.0, 5.0, 5.0, 3.0),
        store=FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=clock,
        stream_health_monitor=StreamHealthMonitor(timeout_sec=1.0, clock=clock),
    )

    # A set keeps membership checks O(1) and memory bounded even if a
    # regression makes the worker loop spin hot on the frozen frame.
    statuses: set[str] = set()
    worker.connection_status.connect(statuses.add)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    try:
        qtbot.waitUntil(lambda: "stream_error" in statuses, timeout=5000)
    finally:
        worker.stop()
        thread.join(timeout=2.0)

    assert "connected" in statuses, "the first (fresh) frame should report connected"
    assert detector.calls == 1, "frozen frames must not be fed to the detector"


@pytest.mark.qt
def test_worker_frozen_frame_with_closed_source_reports_reconnecting(
    qtbot: pytest.QtBot,
) -> None:
    """Frozen frame + is_opened=False → DISCONNECTED ("reconnecting")."""
    from src.app.worker import DetectionWorker
    from src.capture.stream_health import StreamHealthMonitor

    clock = FakeClock(step=0.6)
    detector = CountingDetector()
    frames = FakeFrames([_frame()], is_opened=False)
    worker = DetectionWorker(
        frames=frames,
        detector=detector,
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(10.0, 5.0, 5.0, 3.0),
        store=FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=clock,
        stream_health_monitor=StreamHealthMonitor(timeout_sec=1.0, clock=clock),
    )

    statuses: set[str] = set()
    worker.connection_status.connect(statuses.add)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    try:
        qtbot.waitUntil(lambda: "reconnecting" in statuses, timeout=5000)
    finally:
        worker.stop()
        thread.join(timeout=2.0)

    assert detector.calls == 1


class RecoveringFrames:
    """First serves one fresh frame, then freezes (same frame, timestamp stuck);
    after ``recover()`` every poll yields a fresh frame again (§4.2 acceptance:
    the stream resumes after an outage)."""

    def __init__(self) -> None:
        self._current = _frame()
        self._served_first = False
        self._recovered = threading.Event()

    def latest(self) -> Frame:
        if not self._served_first:
            self._served_first = True
            return self._current
        if self._recovered.is_set():
            self._current = _frame()
        return self._current

    def recover(self) -> None:
        self._recovered.set()

    @property
    def is_opened(self) -> bool:
        return True


@pytest.mark.qt
def test_worker_recovers_to_connected_after_frozen_stream_resumes(
    qtbot: pytest.QtBot,
) -> None:
    """§4.2 驗收：凍結→stream_error 之後恢復供新影格 → 自動回到 connected，
    且 detector 重新被呼叫。"""
    from src.app.worker import DetectionWorker
    from src.capture.stream_health import StreamHealthMonitor

    clock = FakeClock(step=0.6)
    detector = CountingDetector()
    frames = RecoveringFrames()
    worker = DetectionWorker(
        frames=frames,
        detector=detector,
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(10.0, 5.0, 5.0, 3.0),
        store=FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=clock,
        stream_health_monitor=StreamHealthMonitor(timeout_sec=1.0, clock=clock),
    )

    statuses: list[str] = []
    worker.connection_status.connect(statuses.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    try:
        qtbot.waitUntil(lambda: "stream_error" in statuses, timeout=5000)
        calls_while_frozen = detector.calls

        frames.recover()

        def _reconnected() -> bool:
            if "stream_error" not in statuses:
                return False
            after = statuses.index("stream_error") + 1
            return "connected" in statuses[after:]

        qtbot.waitUntil(_reconnected, timeout=5000)
    finally:
        worker.stop()
        thread.join(timeout=2.0)

    assert detector.calls > calls_while_frozen, "detection must resume after recovery"


class LowFpsFrames:
    """Healthy but slow stream: each frame is served for *repeats* polls before
    the timestamp advances (source fps lower than the detection poll rate)."""

    def __init__(self, repeats: int = 2) -> None:
        self._repeats = repeats
        self._serves = 0
        self._current = _frame()

    def latest(self) -> Frame:
        if self._serves and self._serves % self._repeats == 0:
            self._current = _frame()
        self._serves += 1
        return self._current

    @property
    def is_opened(self) -> bool:
        return True


@pytest.mark.qt
def test_worker_low_fps_source_stays_connected_without_no_signal(
    qtbot: pytest.QtBot,
) -> None:
    """§4.2 回歸：來源影格週期長於輪詢間隔的健康串流，不得間歇回報 no_signal。

    worker 預設的 StreamHealthMonitor 需帶 no-signal 寬限期。
    """
    clock = FakeClock(step=0.1)
    detector = CountingDetector()
    frames = LowFpsFrames(repeats=2)
    worker = _make_worker(frames, detector=detector, clock=clock)

    statuses: list[str] = []
    worker.connection_status.connect(statuses.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    try:
        qtbot.waitUntil(lambda: detector.calls >= 5, timeout=5000)
    finally:
        worker.stop()
        thread.join(timeout=2.0)

    assert "connected" in statuses
    assert "no_signal" not in statuses
    assert "stream_error" not in statuses


# ---------------------------------------------------------------------------
# §4.8: logging_enabled=False 時不得寫入 store
# ---------------------------------------------------------------------------


def test_logging_disabled_skips_session_writes() -> None:
    store = FakeStore()
    worker = _make_worker(FakeFrames([None]), store=store, logging_enabled=False)

    worker._dispatch(
        TimerEvent(TimerEventType.WORK_ENDED, at=1.0, duration_sec=5.0, ended_by="rest")
    )
    worker._dispatch(TimerEvent(TimerEventType.REST_ENDED, at=2.0, duration_sec=3.0))

    assert store.rows == []


def test_logging_enabled_by_default_writes_sessions() -> None:
    store = FakeStore()
    worker = _make_worker(FakeFrames([None]), store=store)

    worker._dispatch(
        TimerEvent(TimerEventType.WORK_ENDED, at=1.0, duration_sec=5.0, ended_by="rest")
    )
    worker._dispatch(TimerEvent(TimerEventType.REST_ENDED, at=2.0, duration_sec=3.0))

    assert [row[0] for row in store.rows] == ["work", "rest"]
