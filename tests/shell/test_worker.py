"""T8 偵測 worker 測試（移植 tests/test_worker.py 的 LiveFrames/遞增 timestamp 模式）。

核心換為 RestFlowMachine＋SessionTranslator＋RecordStore；訊號與指令槽依
計畫「鎖定介面」：timer_updated/reminder_show/reminder_repeat/return_prompt/
lock_requested/connection_status/device_fallback/failed＋request_* 指令槽。
"""

from __future__ import annotations

import itertools
import threading
import time
from datetime import datetime
from typing import Any

import numpy as np
import pytest

from src.core.escalation import EscalationPolicy
from src.core.events import (
    LedgerEvent,
    SessionRecord,
    TimerEvent,
    TimerEventType,
    TimerState,
)
from src.core.state_machine import MachineConfig, RestFlowMachine
from src.presence import PresenceEvaluator
from src.shell.reminders.context import ReminderContext
from src.types import BBox, Detection, Frame

# ---------------------------------------------------------------------------
# Fake helpers（移植自 tests/test_worker.py）
# ---------------------------------------------------------------------------


_TS_COUNTER = itertools.count()


def _frame() -> Frame:
    """Build a frame with a unique, monotonically increasing timestamp.

    Real FrameGrabber frames carry advancing timestamps; the worker relies on
    timestamp freshness (§4.2), so every fabricated frame must be distinct.
    """
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    return Frame(image=image, width=10, height=10, timestamp=float(next(_TS_COUNTER)))


class FakeFrames:
    """Implements FrameProvider: latest() / is_opened.

    Mirrors the real FrameGrabber semantics: each queued frame is served once
    (timestamps advance while the stream is alive); after the queue is
    exhausted the *last* frame keeps being returned unchanged — i.e. a frozen
    stream whose timestamp no longer advances (§4.2).
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


class CountingDetector:
    """Counts detect() calls; always reports nobody present."""

    def __init__(self) -> None:
        self.calls = 0

    def detect(self, frame: Frame) -> list[Detection]:
        del frame
        self.calls += 1
        return []


class FakeStore:
    """RecordStore 替身：以 SessionRecord / LedgerEvent 收集寫入。"""

    def __init__(self) -> None:
        self.schema_init_calls = 0
        self.sessions: list[SessionRecord] = []
        self.events: list[LedgerEvent] = []

    def init_schema(self) -> None:
        self.schema_init_calls += 1

    def log_session(self, rec: SessionRecord) -> None:
        self.sessions.append(rec)

    def log_event(self, ev: LedgerEvent) -> None:
        self.events.append(ev)

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


class ManualClock:
    """讀取時不前進的時鐘；由測試顯式設定 now。"""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _qualifying_detection() -> Detection:
    return Detection(BBox(0.2, 0.2, 0.3, 0.4), 0.9)


def _machine(
    work: float = 10.0,
    reset: float = 5.0,
    rest: float = 5.0,
    repeat: float = 30.0,
    mode: str = "presence",
    stages: tuple[float, float, float] = (60.0, 120.0, 180.0),
    max_stage: int = 3,
    apply_to_reminding: bool = True,
) -> RestFlowMachine:
    cfg = MachineConfig(
        work_threshold_sec=work,
        reset_threshold_sec=reset,
        required_rest_sec=rest,
        repeat_interval_sec=repeat,
        rest_count_mode=mode,
        apply_to_reminding=apply_to_reminding,
    )
    return RestFlowMachine(cfg, EscalationPolicy(stages, max_stage))


def _make_worker(
    frames: Any,
    detector: Any | None = None,
    machine: Any | None = None,
    store: Any | None = None,
    clock: Any | None = None,
    wall_clock: Any | None = None,
    logging_enabled: bool = True,
    stream_health_monitor: Any | None = None,
) -> Any:
    from src.shell.worker import DetectionWorker

    kwargs: dict[str, Any] = {}
    if wall_clock is not None:
        kwargs["wall_clock"] = wall_clock
    return DetectionWorker(
        frames=frames,
        detector=detector or FakeDetector([[]]),
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        machine=machine or _machine(),
        store=store or FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=clock or FakeClock(),
        logging_enabled=logging_enabled,
        stream_health_monitor=stream_health_monitor,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 達門檻 → reminder_show（ctx 含實際連續工作秒數）
# ---------------------------------------------------------------------------


def test_worker_emits_reminder_show_when_threshold_reached(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    worker = _make_worker(
        FakeFrames([_frame() for _ in range(5)]),
        detector=FakeDetector([[qd]] * 5),
        machine=_machine(work=0.5),
        clock=FakeClock(step=0.6),
    )

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.reminder_show, timeout=3000) as blocker:
        thread.start()
    worker.stop()
    thread.join(timeout=1.0)

    ctx = blocker.args[0]
    assert isinstance(ctx, ReminderContext)
    assert ctx.work_elapsed_sec >= 0.5  # FR-3：注入實際連續工作秒數


def test_reminder_repeat_reemits_reminder_show_with_refreshed_work_duration() -> None:
    """FR-3：REMINDER_REPEATED 必須以「當下實際連續工作秒數」重發
    reminder_show——重複提醒不得顯示首次觸發時快取的舊時長
    （舊 worker 於 REPEATED 重發 reminder_show 的行為等價移植）。"""
    machine = _machine(work=1.0, repeat=2.0, stages=(600.0, 1200.0, 1800.0))
    clock = ManualClock()
    worker = _make_worker(FakeFrames([None]), machine=machine, clock=clock)

    shows: list[ReminderContext] = []
    repeats: list[bool] = []
    worker.reminder_show.connect(shows.append)
    worker.reminder_repeat.connect(lambda: repeats.append(True))

    clock.now = 0.0
    for event in machine.tick(True, 0.0):  # WORK_STARTED
        worker._dispatch(event)
    clock.now = 1.5
    for event in machine.tick(True, 1.5):  # REMINDER_TRIGGERED（work_elapsed=1.5）
        worker._dispatch(event)
    clock.now = 4.0
    for event in machine.tick(True, 4.0):  # REMINDER_REPEATED（work_elapsed=4.0）
        worker._dispatch(event)

    assert repeats == [True]
    assert len(shows) == 2
    assert shows[0].work_elapsed_sec == pytest.approx(1.5)
    assert shows[1].work_elapsed_sec == pytest.approx(4.0)  # 重複提醒帶最新時長


def test_worker_emits_reminder_repeat_signal(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    worker = _make_worker(
        LiveFrames(),
        detector=FakeDetector([[qd]]),
        machine=_machine(work=0.5, repeat=1.0, stages=(600.0, 1200.0, 1800.0)),
        clock=FakeClock(step=0.6),
    )

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.reminder_repeat, timeout=3000):
        thread.start()
    worker.stop()
    thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# REST_PENDING 指令流：request_start_rest / request_cancel_pending
# ---------------------------------------------------------------------------


def test_request_start_rest_enters_rest_pending(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    worker = _make_worker(
        LiveFrames(),
        detector=FakeDetector([[qd]]),
        machine=_machine(work=0.5),
        clock=FakeClock(step=0.6),
    )

    snapshots: list[Any] = []
    worker.timer_updated.connect(snapshots.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    qtbot.waitUntil(
        lambda: any(s.state == TimerState.REMINDING for s in snapshots), timeout=3000
    )

    worker.request_start_rest()

    qtbot.waitUntil(
        lambda: any(s.state == TimerState.REST_PENDING for s in snapshots), timeout=3000
    )
    worker.stop()
    thread.join(timeout=1.0)


def test_request_cancel_pending_returns_to_reminding(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    worker = _make_worker(
        LiveFrames(),
        detector=FakeDetector([[qd]]),
        machine=_machine(work=0.5),
        clock=FakeClock(step=0.6),
    )

    snapshots: list[Any] = []
    worker.timer_updated.connect(snapshots.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    qtbot.waitUntil(
        lambda: any(s.state == TimerState.REMINDING for s in snapshots), timeout=3000
    )
    worker.request_start_rest()
    qtbot.waitUntil(
        lambda: any(s.state == TimerState.REST_PENDING for s in snapshots), timeout=3000
    )

    marker = len(snapshots)
    worker.request_cancel_pending()

    qtbot.waitUntil(
        lambda: any(s.state == TimerState.REMINDING for s in snapshots[marker:]),
        timeout=3000,
    )
    worker.stop()
    thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# 升級階梯到第 3 階 → lock_requested 訊號
# ---------------------------------------------------------------------------


def test_lock_requested_emitted_when_escalation_reaches_stage3(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    worker = _make_worker(
        LiveFrames(),
        detector=FakeDetector([[qd]]),
        machine=_machine(work=0.5, stages=(0.5, 1.0, 1.5), max_stage=3),
        clock=FakeClock(step=0.6),
    )

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.lock_requested, timeout=5000):
        thread.start()
    worker.stop()
    thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# 休息滿額 → return_prompt；confirm_return 記一筆 rest session
# ---------------------------------------------------------------------------


def test_worker_emits_return_prompt_after_sufficient_rest(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    no_detect: list[Detection] = []
    detector = FakeDetector([[qd], [qd], no_detect, no_detect, [qd], [qd], [qd]])
    worker = _make_worker(
        LiveFrames(),
        detector=detector,
        machine=_machine(work=0.5, rest=0.5, mode="fixed"),
        clock=FakeClock(step=0.6),
    )

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.return_prompt, timeout=5000):
        thread.start()
    worker.stop()
    thread.join(timeout=1.0)


def test_request_confirm_return_logs_rest_session_and_resumes_working(
    qtbot: pytest.QtBot,
) -> None:
    qd = _qualifying_detection()
    no_detect: list[Detection] = []
    detector = FakeDetector([[qd], [qd], no_detect, no_detect, [qd], [qd], [qd]])
    store = FakeStore()
    worker = _make_worker(
        LiveFrames(),
        detector=detector,
        machine=_machine(work=0.5, rest=0.5, mode="fixed"),
        store=store,
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
        lambda: any(rec.kind == "rest" for rec in store.sessions), timeout=3000
    )
    qtbot.waitUntil(
        lambda: any(s.state == TimerState.WORKING for s in snapshots[marker:]),
        timeout=3000,
    )
    worker.stop()
    thread.join(timeout=1.0)

    rest_records = [rec for rec in store.sessions if rec.kind == "rest"]
    assert len(rest_records) >= 1
    assert all(isinstance(rec, SessionRecord) for rec in rest_records)


# ---------------------------------------------------------------------------
# 暫停 / 恢復（request_* 指令槽）
# ---------------------------------------------------------------------------


def test_request_pause_and_resume_work_while_run_loop_is_paused(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    worker = _make_worker(
        LiveFrames(),
        detector=FakeDetector([[qd]]),
        machine=_machine(work=100.0),
        clock=FakeClock(step=0.6),
    )

    snapshots: list[Any] = []
    worker.timer_updated.connect(snapshots.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    qtbot.waitUntil(
        lambda: any(s.state == TimerState.WORKING for s in snapshots), timeout=3000
    )

    worker.request_pause()
    qtbot.waitUntil(
        lambda: any(s.state == TimerState.SUSPENDED for s in snapshots), timeout=3000
    )

    marker = len(snapshots)
    worker.request_resume()
    qtbot.waitUntil(
        lambda: any(s.state != TimerState.SUSPENDED for s in snapshots[marker:]),
        timeout=3000,
    )
    worker.stop()
    thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# 連線狀態（latest()/is_opened → connection_status）
# ---------------------------------------------------------------------------


def test_worker_emits_connecting_at_start(qtbot: pytest.QtBot) -> None:
    worker = _make_worker(FakeFrames([None], is_opened=False))

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.connection_status, timeout=3000) as blocker:
        thread.start()
    worker.stop()
    thread.join(timeout=1.0)

    assert blocker.args == ["connecting"]


def test_worker_emits_no_signal_when_source_open_but_no_frame(qtbot: pytest.QtBot) -> None:
    worker = _make_worker(FakeFrames([None], is_opened=True))

    statuses: list[str] = []
    worker.connection_status.connect(statuses.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    qtbot.waitUntil(lambda: "no_signal" in statuses, timeout=3000)
    worker.stop()
    thread.join(timeout=1.0)

    assert statuses[:2] == ["connecting", "no_signal"]


def test_worker_emits_reconnecting_when_source_closed(qtbot: pytest.QtBot) -> None:
    worker = _make_worker(FakeFrames([None], is_opened=False))

    statuses: list[str] = []
    worker.connection_status.connect(statuses.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    qtbot.waitUntil(lambda: "reconnecting" in statuses, timeout=3000)
    worker.stop()
    thread.join(timeout=1.0)

    assert statuses[:2] == ["connecting", "reconnecting"]


# ---------------------------------------------------------------------------
# §4.2 影格新鮮度：凍結影格必須走健康檢查分支、不得餵進偵測
# ---------------------------------------------------------------------------


def test_worker_treats_frozen_frame_as_stale_and_stops_detecting(qtbot: pytest.QtBot) -> None:
    """One fresh frame, then latest() keeps returning the same frame
    (timestamp frozen) → health must degrade to TIMEOUT ("stream_error")
    and the detector must NOT be called again on the frozen frame.
    """
    from src.capture.stream_health import StreamHealthMonitor

    clock = FakeClock(step=0.6)
    detector = CountingDetector()
    worker = _make_worker(
        FakeFrames([_frame()], is_opened=True),
        detector=detector,
        clock=clock,
        stream_health_monitor=StreamHealthMonitor(timeout_sec=1.0, clock=clock),
    )

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


def test_worker_frozen_frame_with_closed_source_reports_reconnecting(
    qtbot: pytest.QtBot,
) -> None:
    """Frozen frame + is_opened=False → DISCONNECTED ("reconnecting")."""
    from src.capture.stream_health import StreamHealthMonitor

    clock = FakeClock(step=0.6)
    detector = CountingDetector()
    worker = _make_worker(
        FakeFrames([_frame()], is_opened=False),
        detector=detector,
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


def test_worker_recovers_to_connected_after_frozen_stream_resumes(
    qtbot: pytest.QtBot,
) -> None:
    """§4.2 驗收：凍結→stream_error 之後恢復供新影格 → 自動回到 connected，
    且 detector 重新被呼叫。"""
    from src.capture.stream_health import StreamHealthMonitor

    clock = FakeClock(step=0.6)
    detector = CountingDetector()
    frames = RecoveringFrames()
    worker = _make_worker(
        frames,
        detector=detector,
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


def test_worker_low_fps_source_stays_connected_without_no_signal(
    qtbot: pytest.QtBot,
) -> None:
    """§4.2 回歸：來源影格週期長於輪詢間隔的健康串流，不得間歇回報 no_signal。

    worker 預設的 StreamHealthMonitor 需帶 no-signal 寬限期。
    """
    clock = FakeClock(step=0.1)
    detector = CountingDetector()
    worker = _make_worker(LowFpsFrames(repeats=2), detector=detector, clock=clock)

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
# 生命週期：stop / failed / store close
# ---------------------------------------------------------------------------


def test_worker_stop_does_not_release_frames() -> None:
    """stop() should NOT call release on the FrameProvider (grabber handles it)."""
    frames = FakeFrames([_frame()])
    worker = _make_worker(frames)

    worker.stop()

    assert frames.release_calls == 0


def test_worker_emits_failed_when_store_init_crashes(qtbot: pytest.QtBot) -> None:
    worker = _make_worker(FakeFrames([_frame()]), store=ExplodingStore())

    thread = threading.Thread(target=worker.run, daemon=True)
    with qtbot.waitSignal(worker.failed, timeout=3000) as blocker:
        thread.start()
    thread.join(timeout=1.0)

    assert blocker.args == ["boom"]


def test_worker_closes_store_from_worker_thread() -> None:
    store = CloseTrackingStore()
    worker = _make_worker(FakeFrames([None], is_opened=False), store=store)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    time.sleep(0.05)
    worker.stop()
    thread.join(timeout=1.0)

    assert store.close_thread_ids == [thread.ident]


# ---------------------------------------------------------------------------
# ROI 指令佇列
# ---------------------------------------------------------------------------


def test_request_set_roi_applies_last_value() -> None:
    worker = _make_worker(FakeFrames([None], is_opened=False))
    roi_a = BBox(0.1, 0.1, 0.3, 0.3)
    roi_b = BBox(0.2, 0.2, 0.4, 0.4)

    worker.request_set_roi(roi_a)
    worker.request_set_roi(roi_b)
    worker._drain_pending_commands()

    assert worker._presence_evaluator._roi == roi_b


# ---------------------------------------------------------------------------
# §4.8 logging_enabled 兩態：translate 結果非 None 才寫入；停用即兩者都不寫
# ---------------------------------------------------------------------------


def test_logging_disabled_skips_all_store_writes() -> None:
    store = FakeStore()
    worker = _make_worker(FakeFrames([None]), store=store, logging_enabled=False)

    worker._dispatch(
        TimerEvent(TimerEventType.WORK_ENDED, at=10.0, duration_sec=5.0, ended_by="rest")
    )
    worker._dispatch(TimerEvent(TimerEventType.REST_ENDED, at=20.0, duration_sec=3.0))
    worker._dispatch(TimerEvent(TimerEventType.ESCALATED, at=30.0, stage=2))

    assert store.sessions == []
    assert store.events == []


def test_logging_enabled_by_default_writes_sessions_and_ledger_events() -> None:
    """落盤時間戳必須在牆鐘域：機器時鐘（monotonic 域的 event.at）不得直接
    寫進 RecordStore，否則「今日」epoch 區間查詢永遠對不上（雙時鐘設計）。"""
    store = FakeStore()
    wall_now = 1_765_512_000.0  # 固定牆鐘 epoch；與機器時鐘域（10/20/30）明顯不同
    worker = _make_worker(FakeFrames([None]), store=store, wall_clock=lambda: wall_now)

    worker._dispatch(
        TimerEvent(TimerEventType.WORK_ENDED, at=10.0, duration_sec=5.0, ended_by="rest")
    )
    worker._dispatch(TimerEvent(TimerEventType.REST_ENDED, at=20.0, duration_sec=3.0))
    worker._dispatch(TimerEvent(TimerEventType.ESCALATED, at=30.0, stage=2))
    worker._dispatch(TimerEvent(TimerEventType.WORK_STARTED, at=40.0))  # → (None, None)

    assert store.sessions == [
        SessionRecord(
            kind="work",
            start_ts=wall_now - 5.0,
            end_ts=wall_now,
            duration_sec=5.0,
            ended_by="rest",
        ),
        SessionRecord(
            kind="rest",
            start_ts=wall_now - 3.0,
            end_ts=wall_now,
            duration_sec=3.0,
            ended_by="",
        ),
    ]
    assert store.events == [LedgerEvent(ts=wall_now, type="escalated", payload={"stage": 2})]


def test_worker_persisted_rows_visible_to_real_record_store_today_queries(
    tmp_path: Any,
) -> None:
    """Worker→真 RecordStore 整合：worker 落盤的列必須能被 today_* 查到、
    clear_today 必須能刪除（舊缺口：monotonic 時間戳永遠落在今日區間外）。"""
    from src.infra.store import RecordStore

    fixed_dt = datetime(2026, 6, 12, 12, 0, 0)
    store = RecordStore(str(tmp_path / "records.sqlite"))
    store.init_schema()
    worker = _make_worker(
        FakeFrames([None]),
        store=store,
        wall_clock=lambda: fixed_dt.timestamp(),
    )

    # event.at 是 monotonic 域（開機秒數量級）——落盤後仍須屬於「今日」
    worker._dispatch(
        TimerEvent(TimerEventType.WORK_ENDED, at=10.0, duration_sec=5.0, ended_by="rest")
    )
    worker._dispatch(TimerEvent(TimerEventType.REST_ENDED, at=20.0, duration_sec=3.0))
    worker._dispatch(TimerEvent(TimerEventType.ESCALATED, at=30.0, stage=2))

    try:
        assert store.today_work_seconds(now=fixed_dt) == 5.0
        assert store.today_rest_count(now=fixed_dt) == 1
        assert store.clear_today(now=fixed_dt) == 3  # 2 sessions + 1 event
        assert store.today_work_seconds(now=fixed_dt) == 0.0
    finally:
        store.close()


# ---------------------------------------------------------------------------
# device_fallback（FR-1.6）：偵測端 fallback 只通知一次
# ---------------------------------------------------------------------------


class FallbackDetector:
    """Always reports a CUDA→CPU fallback; nobody present."""

    device_fallback = True

    def detect(self, frame: Frame) -> list[Detection]:
        del frame
        return []


def test_worker_emits_device_fallback_once(qtbot: pytest.QtBot) -> None:
    worker = _make_worker(LiveFrames(), detector=FallbackDetector(), clock=FakeClock(step=0.6))

    fallbacks: list[str] = []
    worker.device_fallback.connect(fallbacks.append)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    qtbot.waitUntil(lambda: len(fallbacks) >= 1, timeout=3000)
    # 再跑幾輪迴圈，確認不會重複通知
    time.sleep(0.1)
    worker.stop()
    thread.join(timeout=1.0)

    assert fallbacks == ["cpu"]


def test_worker_without_fallback_does_not_emit(qtbot: pytest.QtBot) -> None:
    """無 device_fallback 屬性的偵測器（向後相容）→ 不發通知。

    自 tests/test_cuda_check.py 的 worker 段移植（T11 切換）。
    """
    worker = _make_worker(LiveFrames())  # FakeDetector 無 device_fallback 屬性

    emissions: list[str] = []
    worker.device_fallback.connect(emissions.append)

    worker._notify_device_fallback_once()
    worker._notify_device_fallback_once()

    assert emissions == []


# ---------------------------------------------------------------------------
# spec §5 階梯音效輸入：REST_PENDING_ENTERED → rest_pending_entered 訊號
# ---------------------------------------------------------------------------


def test_rest_pending_entered_event_emits_signal() -> None:
    worker = _make_worker(FakeFrames([None]))
    entered: list[bool] = []
    worker.rest_pending_entered.connect(lambda: entered.append(True))

    worker._dispatch(TimerEvent(TimerEventType.REST_PENDING_ENTERED, at=10.0))

    assert entered == [True]


def test_other_events_do_not_emit_rest_pending_entered() -> None:
    worker = _make_worker(FakeFrames([None]))
    entered: list[bool] = []
    worker.rest_pending_entered.connect(lambda: entered.append(True))

    worker._dispatch(TimerEvent(TimerEventType.ESCALATED, at=10.0, stage=1))
    worker._dispatch(TimerEvent(TimerEventType.REST_PENDING_CANCELLED, at=11.0))

    assert entered == []


# ---------------------------------------------------------------------------
# spec §5「鎖屏後回來」：request_notify_unlocked → 階梯歸零（單週期鎖屏不重發）
# ---------------------------------------------------------------------------


def test_request_notify_unlocked_resets_machine_escalation() -> None:
    machine = _machine(work=10.0, stages=(60.0, 120.0, 180.0))
    clock = ManualClock()
    worker = _make_worker(FakeFrames([None]), machine=machine, clock=clock)

    machine.tick(True, 0.0)
    machine.tick(True, 10.0)   # REMINDING（apply_to_reminding 錨點=10）
    machine.tick(True, 200.0)  # dwell 190 → 1..3 階＋LOCK_REQUESTED
    assert machine.snapshot(200.0).escalation_stage == 3

    snapshots: list[Any] = []
    worker.timer_updated.connect(snapshots.append)
    clock.now = 205.0
    worker.request_notify_unlocked()
    worker._drain_pending_commands()

    assert machine.snapshot(205.0).escalation_stage == 0
    assert snapshots  # 歸零後立即重發 snapshot，覆蓋層在 stage 0 重現
    assert snapshots[-1].escalation_stage == 0
