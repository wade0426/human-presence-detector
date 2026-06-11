from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

import cv2

from src.config import SourceConfig
from src.types import Frame

# §4.10: FFmpeg can block for tens of seconds (or forever) on an unresponsive
# RTSP server; bound both the initial open and every read.
RTSP_TIMEOUT_MSEC = 5000


class VideoSource(Protocol):
    def open(self) -> None: ...
    def read(self) -> Frame | None: ...
    def release(self) -> None: ...

    @property
    def is_opened(self) -> bool: ...


class WebcamSource:
    def __init__(self, index: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._index = index
        self._clock = clock
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        self._cap = cv2.VideoCapture(self._index)

    def read(self) -> Frame | None:
        if self._cap is None:
            return None
        ok, image = self._cap.read()
        if not ok:
            return None
        height, width = image.shape[:2]
        return Frame(image=image, width=width, height=height, timestamp=self._clock())

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_opened(self) -> bool:
        # §4.13: snapshot the attribute first — the grabber thread may set
        # self._cap to None (release) between two reads, raising AttributeError.
        cap = self._cap
        return cap is not None and bool(cap.isOpened())


class RTSPSource:
    def __init__(self, url: str, clock: Callable[[], float] = time.monotonic) -> None:
        self._url = url
        self._clock = clock
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        # §4.10: open/read timeouts must be passed via the constructor params —
        # setting them with cap.set() after construction is too late for the
        # FFMPEG backend (the blocking open already happened).
        # §4.17: CAP_PROP_BUFFERSIZE was removed — the FFMPEG backend does not
        # support it (set() returns False, silent no-op). Latency is handled by
        # FrameGrabber continuously grabbing at high frequency and keeping only
        # the latest frame.
        self._cap = cv2.VideoCapture(
            self._url,
            cv2.CAP_FFMPEG,
            [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                RTSP_TIMEOUT_MSEC,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                RTSP_TIMEOUT_MSEC,
            ],
        )

    def read(self) -> Frame | None:
        if self._cap is None:
            return None
        ok, image = self._cap.read()
        if not ok:
            return None
        height, width = image.shape[:2]
        return Frame(image=image, width=width, height=height, timestamp=self._clock())

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_opened(self) -> bool:
        # §4.13: snapshot first to avoid the TOCTOU race with release().
        cap = self._cap
        return cap is not None and bool(cap.isOpened())


class ReconnectingSource:
    def __init__(
        self,
        inner: VideoSource,
        reconnect_interval_sec: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self._reconnect_interval_sec = reconnect_interval_sec
        self._clock = clock
        self._last_attempt: float | None = None

    def open(self) -> None:
        self._inner.open()
        self._last_attempt = self._clock()

    def read(self) -> Frame | None:
        if not self._inner.is_opened:
            now = self._clock()
            if (
                self._last_attempt is not None
                and (now - self._last_attempt) < self._reconnect_interval_sec
            ):
                return None
            self._last_attempt = now
            try:
                self._inner.open()
            except Exception:
                return None

        frame = self._inner.read()
        if frame is None:
            self._inner.release()
        return frame

    def release(self) -> None:
        self._inner.release()

    @property
    def is_opened(self) -> bool:
        return self._inner.is_opened


def create_source(
    cfg: SourceConfig, clock: Callable[[], float] = time.monotonic
) -> ReconnectingSource:
    inner: VideoSource
    if cfg.type == "webcam":
        inner = WebcamSource(cfg.webcam_index, clock=clock)
    else:
        inner = RTSPSource(cfg.rtsp_url, clock=clock)
    return ReconnectingSource(inner, cfg.reconnect_interval_sec, clock)
