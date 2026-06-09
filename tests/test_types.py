from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.types import (
    BBox,
    ReminderContext,
    RestCountMode,
    TimerEventType,
    TimerSnapshot,
    TimerState,
)


def test_bbox_center_for_unit_square() -> None:
    assert BBox(0.0, 0.0, 1.0, 1.0).center == (0.5, 0.5)


def test_bbox_center_for_offset_rectangle() -> None:
    center_x, center_y = BBox(0.1, 0.2, 0.4, 0.6).center
    assert center_x == pytest.approx(0.3, abs=1e-9)
    assert center_y == pytest.approx(0.5, abs=1e-9)


def test_bbox_is_frozen() -> None:
    bbox = BBox(0.0, 0.0, 1.0, 1.0)
    with pytest.raises(FrozenInstanceError):
        bbox.x = 1.0  # type: ignore[misc]


def test_timer_state_has_away_not_paused() -> None:
    """TimerState.AWAY replaces old PAUSED."""
    states = {s.value for s in TimerState}
    assert "away" in states
    assert "paused" not in states


def test_timer_state_has_new_members() -> None:
    assert TimerState.AWAY.value == "away"
    assert TimerState.RESTING.value == "resting"
    assert TimerState.AWAITING_RETURN.value == "awaiting_return"
    assert TimerState.SUSPENDED.value == "suspended"


def test_rest_count_mode_values() -> None:
    assert RestCountMode("presence") == RestCountMode.PRESENCE
    assert RestCountMode("fixed") == RestCountMode.FIXED


def test_timer_event_type_has_new_members() -> None:
    assert TimerEventType.REST_STARTED.value == "rest_started"
    assert TimerEventType.RETURN_PROMPT.value == "return_prompt"


def test_reminder_context_has_no_reset_mode_or_snooze() -> None:
    ctx = ReminderContext(work_minutes=45, media_path="", media_type="image", sound_path="")
    assert not hasattr(ctx, "reset_mode")
    assert not hasattr(ctx, "snooze_minutes")


def test_timer_snapshot_has_rest_fields() -> None:
    snap = TimerSnapshot(
        state=TimerState.RESTING,
        work_elapsed_sec=0.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=False,
        rest_remaining_sec=120.0,
        rest_elapsed_sec=60.0,
    )
    assert snap.rest_remaining_sec == 120.0
    assert snap.rest_elapsed_sec == 60.0


def test_timer_snapshot_rest_fields_default_to_zero() -> None:
    snap = TimerSnapshot(
        state=TimerState.WORKING,
        work_elapsed_sec=0.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=False,
    )
    assert snap.rest_remaining_sec == 0.0
    assert snap.rest_elapsed_sec == 0.0
