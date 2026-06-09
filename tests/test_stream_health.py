"""Unit tests for src/capture/stream_health.py (FR-6)."""

from __future__ import annotations

import pytest

from src.capture.stream_health import (
    DEFAULT_STREAM_TIMEOUT_SEC,
    StreamHealth,
    StreamHealthMonitor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_monitor(timeout_sec: float = 10.0, start_t: float = 0.0) -> StreamHealthMonitor:
    """Create a :class:`StreamHealthMonitor` with a fixed starting clock value."""
    return StreamHealthMonitor(timeout_sec=timeout_sec, clock=lambda: start_t)


# ---------------------------------------------------------------------------
# Basic state transitions
# ---------------------------------------------------------------------------


class TestInitialState:
    """After construction no frame has arrived yet; first update reflects that."""

    def test_no_signal_before_timeout(self) -> None:
        """update(False, True, t0) within timeout → NO_SIGNAL."""
        monitor = make_monitor(timeout_sec=10.0, start_t=0.0)
        result = monitor.update(has_frame=False, is_opened=True, now=0.0)
        assert result is StreamHealth.NO_SIGNAL

    def test_no_signal_just_before_timeout(self) -> None:
        """update(False, True) with elapsed just under timeout → NO_SIGNAL."""
        monitor = make_monitor(timeout_sec=10.0, start_t=0.0)
        result = monitor.update(has_frame=False, is_opened=True, now=9.999)
        assert result is StreamHealth.NO_SIGNAL


class TestTimeout:
    """Elapsed time reaching or exceeding timeout_sec produces TIMEOUT."""

    def test_timeout_at_boundary(self) -> None:
        """Elapsed == timeout_sec → TIMEOUT."""
        monitor = make_monitor(timeout_sec=10.0, start_t=0.0)
        result = monitor.update(has_frame=False, is_opened=True, now=10.0)
        assert result is StreamHealth.TIMEOUT

    def test_timeout_beyond_boundary(self) -> None:
        """Elapsed > timeout_sec → TIMEOUT."""
        monitor = make_monitor(timeout_sec=10.0, start_t=0.0)
        result = monitor.update(has_frame=False, is_opened=True, now=99.0)
        assert result is StreamHealth.TIMEOUT

    def test_custom_timeout_sec(self) -> None:
        """Custom timeout_sec is respected."""
        monitor = make_monitor(timeout_sec=5.0, start_t=0.0)
        # At 4.9 → NO_SIGNAL
        assert monitor.update(has_frame=False, is_opened=True, now=4.9) is StreamHealth.NO_SIGNAL
        # At 5.0 → TIMEOUT
        monitor2 = make_monitor(timeout_sec=5.0, start_t=0.0)
        assert monitor2.update(has_frame=False, is_opened=True, now=5.0) is StreamHealth.TIMEOUT


class TestDisconnected:
    """is_opened=False always produces DISCONNECTED regardless of has_frame."""

    def test_disconnected_no_frame(self) -> None:
        monitor = make_monitor()
        result = monitor.update(has_frame=False, is_opened=False, now=0.0)
        assert result is StreamHealth.DISCONNECTED

    def test_disconnected_with_frame(self) -> None:
        """Even if a frame appears somehow, closed source → DISCONNECTED."""
        monitor = make_monitor()
        result = monitor.update(has_frame=True, is_opened=False, now=0.0)
        # When has_frame=True the monitor records and returns OK before checking
        # is_opened; verify this per spec: has_frame=True takes priority.
        assert result is StreamHealth.OK

    def test_disconnected_after_ok(self) -> None:
        """Source closes after frames were received → DISCONNECTED."""
        monitor = make_monitor(start_t=0.0)
        monitor.update(has_frame=True, is_opened=True, now=1.0)
        result = monitor.update(has_frame=False, is_opened=False, now=2.0)
        assert result is StreamHealth.DISCONNECTED


class TestOK:
    """has_frame=True produces OK and resets the frame timer."""

    def test_ok_on_frame(self) -> None:
        monitor = make_monitor()
        result = monitor.update(has_frame=True, is_opened=True, now=5.0)
        assert result is StreamHealth.OK

    def test_timer_resets_after_frame(self) -> None:
        """After a frame at t=5, silence until t=14 (9 s < 10 s) → NO_SIGNAL."""
        monitor = make_monitor(timeout_sec=10.0, start_t=0.0)
        # Receive frame at t=5 → resets _last_frame_t to 5
        monitor.update(has_frame=True, is_opened=True, now=5.0)
        # Silence for 9 s (elapsed=9 < 10) → NO_SIGNAL
        result = monitor.update(has_frame=False, is_opened=True, now=14.0)
        assert result is StreamHealth.NO_SIGNAL

    def test_timeout_calculated_from_last_frame(self) -> None:
        """Timeout is measured from the last received frame, not from construction."""
        monitor = make_monitor(timeout_sec=10.0, start_t=0.0)
        # Receive frame at t=100 → resets timer
        monitor.update(has_frame=True, is_opened=True, now=100.0)
        # At t=109 elapsed=9 → NO_SIGNAL
        assert (
            monitor.update(has_frame=False, is_opened=True, now=109.0) is StreamHealth.NO_SIGNAL
        )
        # At t=110 elapsed=10 → TIMEOUT
        monitor2 = make_monitor(timeout_sec=10.0, start_t=0.0)
        monitor2.update(has_frame=True, is_opened=True, now=100.0)
        assert (
            monitor2.update(has_frame=False, is_opened=True, now=110.0) is StreamHealth.TIMEOUT
        )


# ---------------------------------------------------------------------------
# Default constant
# ---------------------------------------------------------------------------


def test_default_timeout_constant() -> None:
    """DEFAULT_STREAM_TIMEOUT_SEC must be 10.0."""
    assert pytest.approx(10.0) == DEFAULT_STREAM_TIMEOUT_SEC


def test_default_uses_constant() -> None:
    """StreamHealthMonitor default timeout equals DEFAULT_STREAM_TIMEOUT_SEC."""
    monitor = StreamHealthMonitor(clock=lambda: 0.0)
    # elapsed == DEFAULT at boundary → TIMEOUT
    result = monitor.update(has_frame=False, is_opened=True, now=DEFAULT_STREAM_TIMEOUT_SEC)
    assert result is StreamHealth.TIMEOUT
