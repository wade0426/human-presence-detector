from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Protocol

from src.capture.video_source import VideoSource
from src.types import Frame


class FrameProvider(Protocol):
    """Abstraction consumed by downstream workers (e.g. M4 worker.py)."""

    def latest(self) -> Frame | None: ...

    @property
    def is_opened(self) -> bool: ...


class FrameGrabber:
    """Continuously reads from a VideoSource in a background thread.

    Only the *latest* frame is retained; older frames are discarded.
    The public API (``latest`` / ``is_opened``) is thread-safe.
    """

    def __init__(
        self,
        source: VideoSource,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._source = source
        self._clock = clock
        self._lock = threading.Lock()
        self._latest: Frame | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background capture thread."""
        self._running = True
        self._thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the thread to stop, wait for it, then release the source."""
        self._running = False
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        self._source.release()
        with self._lock:
            self._latest = None

    def latest(self) -> Frame | None:
        """Return the most recently captured frame (thread-safe)."""
        with self._lock:
            return self._latest

    @property
    def is_opened(self) -> bool:
        """Delegate to the underlying source."""
        return self._source.is_opened

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _grab_loop(self) -> None:
        while self._running:
            frame = self._source.read()
            if frame is not None:
                with self._lock:
                    self._latest = frame
            else:
                # Source not ready or momentarily unavailable — avoid busy-spin.
                time.sleep(0.005)
