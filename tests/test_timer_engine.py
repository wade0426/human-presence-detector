from __future__ import annotations

from src.timer_engine import TimerEngine
from src.types import ResetMode, TimerEventType, TimerState


def _engine(reset_mode: ResetMode = ResetMode.DETECTION) -> TimerEngine:
    return TimerEngine(
        work_threshold_sec=10.0,
        reset_threshold_sec=5.0,
        required_rest_sec=5.0,
        reset_mode=reset_mode,
        repeat_interval_sec=3.0,
        snooze_sec=4.0,
    )


def test_timer_triggers_reminder_after_work_threshold() -> None:
    engine = _engine()

    assert [event.type for event in engine.update(True, 0.0)] == [TimerEventType.WORK_STARTED]
    assert engine.update(True, 4.0) == []
    events = engine.update(True, 10.0)

    assert [event.type for event in events] == [TimerEventType.REMINDER_TRIGGERED]
    assert engine.state == TimerState.REMINDING


def test_timer_pauses_without_counting_away_time() -> None:
    engine = _engine()
    engine.update(True, 0.0)
    engine.update(True, 4.0)
    engine.update(False, 5.0)
    engine.update(True, 8.0)
    snapshot = engine.snapshot(8.0)

    assert engine.state == TimerState.WORKING
    assert snapshot.work_elapsed_sec == 4.0


def test_timer_resets_after_long_absence_and_restarts_with_rest_ended() -> None:
    engine = _engine()
    engine.update(True, 0.0)
    engine.update(True, 4.0)
    engine.update(False, 5.0)
    events = engine.update(False, 10.0)

    assert len(events) == 1
    assert events[0].type == TimerEventType.WORK_ENDED
    assert events[0].ended_by == "reset"
    assert engine.state == TimerState.IDLE

    restart_events = engine.update(True, 11.0)

    assert [event.type for event in restart_events] == [
        TimerEventType.REST_ENDED,
        TimerEventType.WORK_STARTED,
    ]


def test_detection_mode_repeats_and_resets_after_required_rest() -> None:
    engine = _engine(ResetMode.DETECTION)
    engine.update(True, 0.0)
    engine.update(True, 10.0)

    repeat_events = engine.update(True, 13.0)
    assert [event.type for event in repeat_events] == [TimerEventType.REMINDER_REPEATED]

    engine.update(False, 14.0)
    reset_events = engine.update(False, 19.0)
    assert len(reset_events) == 1
    assert reset_events[0].type == TimerEventType.WORK_ENDED
    assert reset_events[0].ended_by == "rest_done"


def test_dismiss_mode_restarts_immediately_after_dismissal() -> None:
    engine = _engine(ResetMode.DISMISS)
    engine.update(True, 0.0)
    engine.update(True, 10.0)

    dismiss_events = engine.on_reminder_dismissed(10.0)

    assert [event.type for event in dismiss_events] == [
        TimerEventType.WORK_ENDED,
        TimerEventType.WORK_STARTED,
    ]
    assert dismiss_events[0].ended_by == "dismiss"
    assert engine.state == TimerState.WORKING
    assert engine.snapshot(10.0).work_elapsed_sec == 0.0


def test_snooze_mode_suppresses_repeat_until_snooze_expires() -> None:
    engine = _engine(ResetMode.SNOOZE)
    engine.update(True, 0.0)
    engine.update(True, 10.0)

    assert engine.on_reminder_dismissed(10.0) == []
    assert engine.update(True, 12.0) == []

    repeat_events = engine.update(True, 14.0)
    assert [event.type for event in repeat_events] == [TimerEventType.REMINDER_REPEATED]

    engine.update(False, 15.0)
    reset_events = engine.update(False, 20.0)
    assert len(reset_events) == 1
    assert reset_events[0].ended_by == "rest_done"


def test_snapshot_reports_remaining_and_reminder_state() -> None:
    engine = _engine()

    idle_snapshot = engine.snapshot(0.0)
    assert idle_snapshot.remaining_to_reminder_sec == 0.0
    assert idle_snapshot.reminder_active is False

    engine.update(True, 0.0)
    engine.update(True, 4.0)
    working_snapshot = engine.snapshot(4.0)
    assert working_snapshot.remaining_to_reminder_sec == 6.0
    assert working_snapshot.reminder_active is False

    engine.update(False, 5.0)
    paused_snapshot = engine.snapshot(7.0)
    assert paused_snapshot.away_elapsed_sec == 2.0

    engine.update(True, 8.0)
    engine.update(True, 14.0)
    reminding_snapshot = engine.snapshot(14.0)
    assert reminding_snapshot.reminder_active is True
    assert reminding_snapshot.remaining_to_reminder_sec == 0.0
