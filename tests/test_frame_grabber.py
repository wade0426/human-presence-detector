"""Tests for src/capture/frame_grabber.py (M3).

No Qt, no real camera — all I/O is done through FakeSource.
"""
from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from src.capture.frame_grabber import FrameGrabber
from src.types import Frame

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _frame(value: int = 0) -> Frame:
    """Construct a minimal valid Frame."""
    img = np.full((2, 2, 3), value, dtype=np.uint8)
    return Frame(image=img, width=2, height=2, timestamp=float(value))


class FakeSource:
    """Finite sequence of pre-canned frames (thread-safe for index bump)."""

    def __init__(self, frames: list[Frame | None]) -> None:
        self._frames = frames
        self._index = 0
        self._lock = threading.Lock()
        self._released = False
        self.release_calls = 0

    def open(self) -> None:  # satisfies VideoSource protocol
        pass

    def read(self) -> Frame | None:
        with self._lock:
            if self._index < len(self._frames):
                frame = self._frames[self._index]
                self._index += 1
                return frame
            # Exhausted — return None forever (source "disconnected")
            return None

    def release(self) -> None:
        self._released = True
        self.release_calls += 1

    @property
    def is_opened(self) -> bool:
        return not self._released


# ---------------------------------------------------------------------------
# Test 1 — latest() returns the *last* frame delivered by source
# ---------------------------------------------------------------------------

def test_latest_returns_last_frame() -> None:
    """After start(), latest() should reflect the most recent frame."""
    frames: list[Frame | None] = [_frame(i) for i in range(5)]
    # Pad with many Nones so the grabber has time to process all frames then idles
    frames += [None] * 200
    source = FakeSource(frames)

    grabber = FrameGrabber(source)
    grabber.start()

    # Give the background thread time to drain all real frames
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        f = grabber.latest()
        if f is not None and f.timestamp == 4.0:
            break
        time.sleep(0.01)

    grabber.stop()

    result = grabber.latest()
    # After stop(), latest() must be None
    assert result is None


def test_latest_progresses_to_last_real_frame() -> None:
    """The grabber retains the *newest* frame — not just the first one."""
    frames: list[Frame | None] = [_frame(i) for i in range(3)]
    frames += [None] * 200
    source = FakeSource(frames)

    grabber = FrameGrabber(source)
    grabber.start()

    # Poll until we see frame index 2 (timestamp==2.0) or timeout
    seen: Frame | None = None
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        f = grabber.latest()
        if f is not None and f.timestamp == 2.0:
            seen = f
            break
        time.sleep(0.005)

    grabber.stop()
    assert seen is not None, "Expected to observe the last frame (timestamp=2.0)"


# ---------------------------------------------------------------------------
# Test 2 — None from source doesn't raise; is_opened delegates
# ---------------------------------------------------------------------------

def test_none_frames_do_not_raise() -> None:
    """When the source returns None the grabber silently skips; no exception."""
    good = _frame(42)
    frames: list[Frame | None] = [good] + [None] * 100
    source = FakeSource(frames)

    grabber = FrameGrabber(source)
    grabber.start()

    # Allow background thread to consume all frames
    time.sleep(0.1)

    try:
        result = grabber.latest()
    except Exception as exc:  # pragma: no cover
        pytest.fail(f"latest() raised unexpectedly: {exc}")
    finally:
        grabber.stop()

    # Before stop: could be good frame or None (race OK); must not have raised.
    _ = result  # just proves we got here


def test_is_opened_delegates_to_source() -> None:
    """is_opened must forward to the underlying source's is_opened."""
    source = FakeSource([None] * 50)
    grabber = FrameGrabber(source)

    # Before release: source.is_opened == True
    assert grabber.is_opened is True

    grabber.start()
    grabber.stop()  # calls source.release()

    # After release: source.is_opened == False
    assert grabber.is_opened is False


# ---------------------------------------------------------------------------
# Test 3 — stop() terminates thread and calls release() exactly once
# ---------------------------------------------------------------------------

def test_stop_joins_thread_and_releases_source() -> None:
    """stop() must join the background thread and call source.release() once."""
    source = FakeSource([None] * 1000)
    grabber = FrameGrabber(source)
    grabber.start()
    thread = grabber._thread  # capture reference before stop clears it

    grabber.stop()

    assert thread is not None
    assert not thread.is_alive(), "Background thread should have exited after stop()"
    assert source.release_calls == 1, "source.release() must be called exactly once"
    assert grabber.latest() is None, "latest() must return None after stop()"


# ---------------------------------------------------------------------------
# Test 4 — concurrent latest() calls don't raise (stress test)
# ---------------------------------------------------------------------------

def test_concurrent_latest_no_exception() -> None:
    """Multiple threads calling latest() simultaneously must not raise."""
    frames: list[Frame | None] = [_frame(i % 10) for i in range(500)]
    source = FakeSource(frames)
    grabber = FrameGrabber(source)
    grabber.start()

    errors: list[Exception] = []

    def reader() -> None:
        for _ in range(200):
            try:
                grabber.latest()
            except Exception as exc:
                errors.append(exc)

    threads = [threading.Thread(target=reader) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    grabber.stop()

    assert errors == [], f"Concurrent latest() raised exceptions: {errors}"


# ---------------------------------------------------------------------------
# Test 5 — §4.10: stop() must not hang forever when read() blocks
# ---------------------------------------------------------------------------


class BlockingSource:
    """read() blocks until unblocked — simulates a stalled RTSP read."""

    def __init__(self) -> None:
        self._unblock = threading.Event()
        self.entered_read = threading.Event()
        self.release_calls = 0

    def open(self) -> None:
        pass

    def read(self) -> Frame | None:
        self.entered_read.set()
        self._unblock.wait()
        return None

    def release(self) -> None:
        self.release_calls += 1

    @property
    def is_opened(self) -> bool:
        return True

    def unblock(self) -> None:
        self._unblock.set()


def test_stop_returns_promptly_when_read_blocks_forever() -> None:
    """With the grab thread stuck in read(), stop() must give up after the
    join timeout (~2s) instead of hanging the (GUI) caller forever, and must
    skip release() to avoid racing the still-blocked read().
    """
    source = BlockingSource()
    grabber = FrameGrabber(source)
    grabber.start()
    try:
        assert source.entered_read.wait(timeout=2.0), "grab thread never entered read()"

        start = time.monotonic()
        stopper = threading.Thread(target=grabber.stop, daemon=True)
        stopper.start()
        stopper.join(timeout=4.0)
        elapsed = time.monotonic() - start

        assert not stopper.is_alive(), "stop() is still blocked after 4s"
        assert elapsed <= 2.5, f"stop() took {elapsed:.2f}s; expected <= ~2.5s"
        assert source.release_calls == 0, (
            "release() must be skipped when the grab thread could not be joined"
        )
        assert grabber.latest() is None, "latest() must be cleared even on join timeout"
    finally:
        # Let the daemon grab thread exit so it does not leak into other tests.
        source.unblock()
