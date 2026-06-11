from __future__ import annotations

import dataclasses
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import QObject, Signal

from src.capture.frame_grabber import FrameProvider
from src.capture.stream_health import (
    DEFAULT_NO_SIGNAL_GRACE_SEC,
    StreamHealth,
    StreamHealthMonitor,
)
from src.types import BBox, ReminderContext, TimerEvent, TimerEventType

_STREAM_STATUS_MAP: dict[StreamHealth, str] = {
    StreamHealth.OK: "connected",
    StreamHealth.NO_SIGNAL: "no_signal",
    StreamHealth.TIMEOUT: "stream_error",
    StreamHealth.DISCONNECTED: "reconnecting",
}


class DetectionWorker(QObject):
    presence_changed = Signal(bool)
    timer_updated = Signal(object)
    reminder_show = Signal(object)
    return_prompt = Signal()
    connection_status = Signal(str)
    failed = Signal(str)
    # FR-1.6：偵測端裝置 fallback（CUDA→CPU）發生時通知一次，參數為改用的裝置。
    device_fallback = Signal(str)

    def __init__(
        self,
        frames: FrameProvider,
        detector: Any,
        presence_evaluator: Any,
        timer_engine: Any,
        store: Any,
        detection_interval_sec: float,
        reminder_context: ReminderContext,
        clock: Callable[[], float] = time.monotonic,
        stream_health_monitor: StreamHealthMonitor | None = None,
        logging_enabled: bool = True,
    ) -> None:
        super().__init__()
        self._frames = frames
        self._detector = detector
        self._presence_evaluator = presence_evaluator
        self._timer_engine = timer_engine
        self._store = store
        self._detection_interval_sec = detection_interval_sec
        self._reminder_context = reminder_context
        self._clock = clock
        # §4.2：預設健康監視器帶 no-signal 寬限期——來源影格週期長於偵測輪詢
        # 間隔（低 FPS 子碼流）的健康串流，不得被間歇誤判為無訊號。
        self._stream_health = stream_health_monitor or StreamHealthMonitor(
            clock=clock,
            no_signal_after_sec=max(
                DEFAULT_NO_SIGNAL_GRACE_SEC, 2.0 * detection_interval_sec
            ),
        )
        self._logging_enabled = logging_enabled
        # §4.2: timestamp of the last frame actually processed; lets us tell a
        # fresh frame apart from a stale one left in the grabber after the
        # stream froze or disconnected.
        self._last_frame_ts: float | None = None
        # FR-1.6: device fallback is reported to the UI at most once.
        self._device_fallback_notified = False
        self._stop = False
        self._paused = False
        self._work_start_dt: datetime | None = None
        self._command_lock = threading.Lock()
        self._pending_start_rest = False
        self._pending_confirm_return = False
        self._pending_pause = False
        self._pending_resume = False
        self._pending_roi: BBox | None = None

    def run(self) -> None:
        try:
            self._store.init_schema()
            self.connection_status.emit("connecting")
            while not self._stop:
                self._drain_pending_commands()
                if self._paused:
                    time.sleep(0.1)
                    continue

                loop_start = self._clock()
                frame = self._frames.latest()
                now = self._clock()
                # §4.2: a frame is only "fresh" if its timestamp advanced past
                # the last processed one. A stale (frozen) frame must go down
                # the health-check branch — never into detection — so that a
                # broken stream cannot keep the presence state alive forever.
                if frame is None or frame.timestamp == self._last_frame_ts:
                    is_opened = self._frames.is_opened
                    health = self._stream_health.update(
                        has_frame=False, is_opened=is_opened, now=now
                    )
                    self.connection_status.emit(_STREAM_STATUS_MAP[health])
                    time.sleep(0.2)
                    continue

                self._last_frame_ts = frame.timestamp
                health = self._stream_health.update(
                    has_frame=True, is_opened=True, now=now
                )
                self.connection_status.emit(_STREAM_STATUS_MAP[health])
                detections = self._detector.detect(frame)
                self._notify_device_fallback_once()
                present = self._presence_evaluator.update(detections)
                self.presence_changed.emit(present)

                for event in self._timer_engine.update(present, self._clock()):
                    self._dispatch(event)

                self.timer_updated.emit(self._timer_engine.snapshot(self._clock()))

                elapsed = self._clock() - loop_start
                if elapsed < self._detection_interval_sec:
                    time.sleep(self._detection_interval_sec - elapsed)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            close = getattr(self._store, "close", None)
            if callable(close):
                close()
            self._stop = True

    def stop(self) -> None:
        self._stop = True

    def _notify_device_fallback_once(self) -> None:
        """FR-1.6：偵測啟動後若發生裝置 fallback（CUDA→CPU），通知 UI 一次。"""
        if self._device_fallback_notified:
            return
        if getattr(self._detector, "device_fallback", False):
            self._device_fallback_notified = True
            self.device_fallback.emit("cpu")

    def request_pause(self) -> None:
        with self._command_lock:
            self._pending_pause = True
            self._pending_resume = False

    def request_resume(self) -> None:
        with self._command_lock:
            self._pending_resume = True
            self._pending_pause = False

    def request_start_rest(self) -> None:
        with self._command_lock:
            self._pending_start_rest = True

    def request_confirm_return(self) -> None:
        with self._command_lock:
            self._pending_confirm_return = True

    def request_set_roi(self, roi: BBox) -> None:
        with self._command_lock:
            self._pending_roi = roi

    def pause(self) -> None:
        now = self._clock()
        self._paused = True
        self._timer_engine.pause(now)
        self.timer_updated.emit(self._timer_engine.snapshot(now))

    def resume(self) -> None:
        now = self._clock()
        self._timer_engine.resume(now)
        self._paused = False

    def start_rest(self) -> None:
        now = self._clock()
        for event in self._timer_engine.start_rest(now):
            self._dispatch(event)
        self.timer_updated.emit(self._timer_engine.snapshot(now))

    def confirm_return(self) -> None:
        now = self._clock()
        for event in self._timer_engine.confirm_return(now):
            self._dispatch(event)
        self.timer_updated.emit(self._timer_engine.snapshot(now))

    def set_roi(self, roi: BBox) -> None:
        self._presence_evaluator.set_roi(roi)

    def _drain_pending_commands(self) -> None:
        with self._command_lock:
            pending_pause = self._pending_pause
            pending_resume = self._pending_resume
            pending_start_rest = self._pending_start_rest
            pending_confirm_return = self._pending_confirm_return
            pending_roi = self._pending_roi
            self._pending_pause = False
            self._pending_resume = False
            self._pending_start_rest = False
            self._pending_confirm_return = False
            self._pending_roi = None

        if pending_roi is not None:
            self.set_roi(pending_roi)
        if pending_pause:
            self.pause()
        if pending_resume:
            self.resume()
            self.timer_updated.emit(self._timer_engine.snapshot(self._clock()))
        if pending_start_rest:
            self.start_rest()
        if pending_confirm_return:
            self.confirm_return()

    def _dispatch(self, event: TimerEvent) -> None:
        now_dt = datetime.now()
        if event.type in (TimerEventType.REMINDER_TRIGGERED, TimerEventType.REMINDER_REPEATED):
            # FR-3：注入當下實際連續工作秒數，不再使用固定門檻值
            snap = self._timer_engine.snapshot(self._clock())
            ctx = dataclasses.replace(
                self._reminder_context, work_elapsed_sec=snap.work_elapsed_sec
            )
            self.reminder_show.emit(ctx)
        elif event.type == TimerEventType.RETURN_PROMPT:
            self.return_prompt.emit()
        elif event.type == TimerEventType.WORK_STARTED:
            self._work_start_dt = now_dt
        elif event.type == TimerEventType.WORK_ENDED:
            # §4.8: honour the logging.enabled setting — skip persistence when off.
            if self._logging_enabled:
                self._store.log_session(
                    "work",
                    self._work_start_dt or now_dt,
                    now_dt,
                    int(event.duration_sec),
                    event.ended_by,
                )
            self._work_start_dt = None
        elif event.type == TimerEventType.REST_ENDED:
            if self._logging_enabled:
                start_dt = now_dt - timedelta(seconds=event.duration_sec)
                self._store.log_session("rest", start_dt, now_dt, int(event.duration_sec), "")
