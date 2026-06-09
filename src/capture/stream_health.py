"""Stream health monitoring for RTSP capture sources (FR-6)."""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum

DEFAULT_STREAM_TIMEOUT_SEC: float = 10.0


class StreamHealth(Enum):
    """Represents the current health state of a video stream."""

    OK = "ok"
    NO_SIGNAL = "no_signal"
    TIMEOUT = "timeout"
    DISCONNECTED = "disconnected"


class StreamHealthMonitor:
    """Tracks stream health by comparing frame arrival times against a timeout threshold.

    Designed as a pure-logic class: no Qt, no OpenCV, no side effects.
    Inject a custom *clock* callable for deterministic unit testing.
    """

    def __init__(
        self,
        timeout_sec: float = DEFAULT_STREAM_TIMEOUT_SEC,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._timeout_sec = timeout_sec
        self._last_frame_t: float = clock()

    def update(self, has_frame: bool, is_opened: bool, now: float) -> StreamHealth:
        """Evaluate stream health for the current detection cycle.

        Args:
            has_frame: Whether a new frame was successfully grabbed in this cycle.
            is_opened: Whether the capture source reports itself as open/connected.
            now: Current monotonic timestamp (seconds).

        Returns:
            The :class:`StreamHealth` state for this cycle.
        """
        if has_frame:
            self._last_frame_t = now
            return StreamHealth.OK

        if not is_opened:
            return StreamHealth.DISCONNECTED

        elapsed = now - self._last_frame_t
        if elapsed < self._timeout_sec:
            return StreamHealth.NO_SIGNAL
        return StreamHealth.TIMEOUT
