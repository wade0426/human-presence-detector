from __future__ import annotations

from collections.abc import Callable

import numpy as np

from src.capture.video_source import (
    ReconnectingSource,
    RTSPSource,
    WebcamSource,
    create_source,
)
from src.config import SourceConfig
from src.types import Frame


class FakeSource:
    def __init__(
        self,
        *,
        open_error: Exception | None = None,
        frame: Frame | None = None,
    ) -> None:
        self._open_error = open_error
        self._frame = frame
        self._is_opened = False
        self.open_calls = 0
        self.release_calls = 0

    def open(self) -> None:
        self.open_calls += 1
        if self._open_error is not None:
            raise self._open_error
        self._is_opened = True

    def read(self) -> Frame | None:
        return self._frame if self._is_opened else None

    def release(self) -> None:
        self.release_calls += 1
        self._is_opened = False

    @property
    def is_opened(self) -> bool:
        return self._is_opened


def _clock(values: list[float]) -> Callable[[], float]:
    iterator = iter(values)
    return lambda: next(iterator)


def test_reconnecting_source_opens_inner_on_first_read() -> None:
    frame = Frame(np.zeros((2, 2, 3), dtype=np.uint8), 2, 2, 0.0)
    inner = FakeSource(frame=frame)
    source = ReconnectingSource(inner, reconnect_interval_sec=5.0, clock=_clock([0.0]))

    result = source.read()

    assert result == frame
    assert inner.open_calls == 1


def test_reconnecting_source_throttles_open_retries_after_failure() -> None:
    inner = FakeSource(open_error=RuntimeError("boom"))
    source = ReconnectingSource(inner, reconnect_interval_sec=5.0, clock=_clock([0.0, 2.0, 6.0]))

    assert source.read() is None
    assert source.read() is None
    assert source.read() is None
    assert inner.open_calls == 2


def test_reconnecting_source_releases_after_failed_read() -> None:
    inner = FakeSource(frame=None)
    source = ReconnectingSource(inner, reconnect_interval_sec=5.0, clock=_clock([0.0]))

    assert source.read() is None
    assert inner.release_calls == 1


def test_create_source_returns_webcam_reconnecting_source() -> None:
    cfg = SourceConfig(type="webcam", webcam_index=3, reconnect_interval_sec=2.0)

    source = create_source(cfg)

    assert isinstance(source, ReconnectingSource)
    assert isinstance(source._inner, WebcamSource)


def test_create_source_returns_rtsp_reconnecting_source() -> None:
    cfg = SourceConfig(
        type="rtsp",
        rtsp_url="rtsp://example",
        reconnect_interval_sec=2.0,
    )

    source = create_source(cfg)

    assert isinstance(source, ReconnectingSource)
    assert isinstance(source._inner, RTSPSource)
