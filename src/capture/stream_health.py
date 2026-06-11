"""Stream health monitoring for RTSP capture sources (FR-6)."""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum

DEFAULT_STREAM_TIMEOUT_SEC: float = 10.0

# §4.2：no-signal 寬限期預設值——已收過影格的串流，短於此秒數的影格空窗
# 仍視為健康（OK），避免來源 FPS 低於偵測輪詢頻率時被間歇誤判為無訊號。
DEFAULT_NO_SIGNAL_GRACE_SEC: float = 2.0


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
        no_signal_after_sec: float = 0.0,
    ) -> None:
        self._timeout_sec = timeout_sec
        # §4.2 寬限期：已收過影格後，距上次影格不足此秒數仍回報 OK。
        # 預設 0.0（不啟用）維持既有行為。
        self._no_signal_after_sec = no_signal_after_sec
        self._last_frame_t: float = clock()
        self._has_seen_frame = False

    def update(self, has_frame: bool, is_opened: bool, now: float) -> StreamHealth:
        """Evaluate stream health for the current detection cycle.

        Args:
            has_frame: Whether a new frame was successfully grabbed in this cycle.
            is_opened: Whether the capture source reports itself as open/connected.
            now: Current monotonic timestamp (seconds).

        Returns:
            The :class:`StreamHealth` state for this cycle. With *no_signal_after_sec*
            set, an established stream (at least one frame seen) reports OK while the
            gap since the last frame is shorter than the grace window, NO_SIGNAL
            between the grace window and *timeout_sec*, and TIMEOUT beyond that.
        """
        if has_frame:
            self._last_frame_t = now
            self._has_seen_frame = True
            return StreamHealth.OK

        if not is_opened:
            return StreamHealth.DISCONNECTED

        elapsed = now - self._last_frame_t
        if self._has_seen_frame and elapsed < self._no_signal_after_sec:
            # §4.2：來源 FPS 低於輪詢頻率時的短暫空窗仍視為健康，
            # 避免健康串流在 connected / no_signal 間反覆切換。
            return StreamHealth.OK
        if elapsed < self._timeout_sec:
            return StreamHealth.NO_SIGNAL
        return StreamHealth.TIMEOUT
