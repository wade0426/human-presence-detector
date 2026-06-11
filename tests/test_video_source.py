from __future__ import annotations

from collections.abc import Callable
from typing import Any

import cv2
import numpy as np
import pytest

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


# ---------------------------------------------------------------------------
# §4.10: RTSP open/read 逾時必須在 VideoCapture 建構子傳入
# §4.17: CAP_PROP_BUFFERSIZE（FFMPEG 不支援）不得再被無聲設定
# ---------------------------------------------------------------------------


class _RecordingCapture:
    """Stands in for cv2.VideoCapture; records constructor args and set() calls."""

    instances: list[_RecordingCapture] = []

    def __init__(self, *args: Any) -> None:
        self.args = args
        self.set_calls: list[tuple[Any, Any]] = []
        _RecordingCapture.instances.append(self)

    def set(self, prop: Any, value: Any) -> bool:
        self.set_calls.append((prop, value))
        return False

    def isOpened(self) -> bool:  # noqa: N802 - mimics cv2.VideoCapture API
        return True

    def release(self) -> None:
        pass


@pytest.fixture()
def recording_capture(monkeypatch: pytest.MonkeyPatch) -> type[_RecordingCapture]:
    _RecordingCapture.instances = []
    monkeypatch.setattr("src.capture.video_source.cv2.VideoCapture", _RecordingCapture)
    return _RecordingCapture


def test_rtsp_open_passes_timeouts_in_constructor(
    recording_capture: type[_RecordingCapture],
) -> None:
    source = RTSPSource("rtsp://example")

    source.open()

    assert len(recording_capture.instances) == 1
    args = recording_capture.instances[0].args
    assert args[0] == "rtsp://example"
    assert args[1] == cv2.CAP_FFMPEG
    assert len(args) >= 3, "timeouts must be passed as constructor params (set() is too late)"
    params = list(args[2])
    pairs = dict(zip(params[::2], params[1::2], strict=True))
    assert pairs.get(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC) == 5000
    assert pairs.get(cv2.CAP_PROP_READ_TIMEOUT_MSEC) == 5000


def test_rtsp_open_does_not_set_buffersize(
    recording_capture: type[_RecordingCapture],
) -> None:
    """CAP_PROP_BUFFERSIZE is a silent no-op on the FFMPEG backend (§4.17)."""
    source = RTSPSource("rtsp://example")

    source.open()

    set_props = [prop for prop, _ in recording_capture.instances[0].set_calls]
    assert cv2.CAP_PROP_BUFFERSIZE not in set_props


# ---------------------------------------------------------------------------
# §4.13: is_opened 的 TOCTOU 競態 — _cap 在兩次讀取之間被併發設為 None
# ---------------------------------------------------------------------------


class _FakeCap:
    def isOpened(self) -> bool:  # noqa: N802 - mimics cv2.VideoCapture API
        return True


def _racy_source(source_cls: type, *args: Any) -> Any:
    """Build a source whose `_cap` simulates a concurrent release():

    the first attribute read returns a live capture, every later read returns
    None — exactly the interleaving of the grabber thread nulling `_cap`
    between the worker thread's two reads in `is_opened`.
    """

    class RacySource(source_cls):  # type: ignore[misc, valid-type]
        @property
        def _cap(self) -> Any:
            reads = self.__dict__.get("_cap_reads", 0)
            self.__dict__["_cap_reads"] = reads + 1
            if reads == 0:
                return _FakeCap()
            return None

        @_cap.setter
        def _cap(self, value: Any) -> None:
            # Writes (e.g. from __init__) are irrelevant for this simulation.
            del value

    return RacySource(*args)


def test_webcam_is_opened_survives_concurrent_release() -> None:
    source = _racy_source(WebcamSource, 0)

    # Must not raise AttributeError; the snapshot taken first reads a live cap.
    assert source.is_opened is True


def test_rtsp_is_opened_survives_concurrent_release() -> None:
    source = _racy_source(RTSPSource, "rtsp://example")

    assert source.is_opened is True
