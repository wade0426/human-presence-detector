from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Protocol

from src.capture.video_source import VideoSource
from src.types import Frame

logger = logging.getLogger(__name__)

# §4.10: upper bound for waiting on the grab thread during stop(); a thread
# stuck in a blocking read() must not freeze the (GUI) caller forever.
STOP_JOIN_TIMEOUT_SEC = 2.0


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
        """Signal the thread to stop, wait for it (bounded), then release the source.

        §4.10: the join is bounded by :data:`STOP_JOIN_TIMEOUT_SEC`. If the grab
        thread is stuck in a blocking ``read()`` (e.g. stalled RTSP), we give up
        waiting — the thread is a daemon and will be reclaimed at process exit —
        and we skip ``release()`` to avoid racing the still-blocked ``read()``
        on the underlying capture object.
        """
        self._running = False
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=STOP_JOIN_TIMEOUT_SEC)
            if thread.is_alive():
                logger.warning(
                    "Grab thread did not stop within %.1fs (blocked read?); "
                    "skipping source release.",
                    STOP_JOIN_TIMEOUT_SEC,
                )
                with self._lock:
                    self._latest = None
                return
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
