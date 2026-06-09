from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import QObject, Signal

from src.capture.frame_grabber import FrameProvider
from src.types import BBox, ReminderContext, TimerEvent, TimerEventType


class DetectionWorker(QObject):
    presence_changed = Signal(bool)
    timer_updated = Signal(object)
    reminder_show = Signal(object)
    return_prompt = Signal(object)
    connection_status = Signal(str)
    failed = Signal(str)

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
        self._stop = False
        self._paused = False
        self._work_start_dt: datetime | None = None

    def run(self) -> None:
        try:
            self._store.init_schema()
            self.connection_status.emit("connecting")
            while not self._stop:
                if self._paused:
                    time.sleep(0.1)
                    continue

                loop_start = self._clock()
                frame = self._frames.latest()
                if frame is None:
                    is_opened = self._frames.is_opened
                    if is_opened:
                        self.connection_status.emit("no_signal")
                    else:
                        self.connection_status.emit("reconnecting")
                    time.sleep(0.2)
                    continue

                self.connection_status.emit("connected")
                detections = self._detector.detect(frame)
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

    def _dispatch(self, event: TimerEvent) -> None:
        now_dt = datetime.now()
        if event.type in (TimerEventType.REMINDER_TRIGGERED, TimerEventType.REMINDER_REPEATED):
            self.reminder_show.emit(self._reminder_context)
        elif event.type == TimerEventType.RETURN_PROMPT:
            self.return_prompt.emit(self._reminder_context)
        elif event.type == TimerEventType.WORK_STARTED:
            self._work_start_dt = now_dt
        elif event.type == TimerEventType.WORK_ENDED:
            self._store.log_session(
                "work",
                self._work_start_dt or now_dt,
                now_dt,
                int(event.duration_sec),
                event.ended_by,
            )
            self._work_start_dt = None
        elif event.type == TimerEventType.REST_ENDED:
            start_dt = now_dt - timedelta(seconds=event.duration_sec)
            self._store.log_session("rest", start_dt, now_dt, int(event.duration_sec), "")
