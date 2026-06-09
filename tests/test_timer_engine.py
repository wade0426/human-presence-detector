from __future__ import annotations

from src.timer_engine import TimerEngine
from src.types import RestCountMode, TimerEventType, TimerState


def _engine(
    work_threshold_sec: float = 10.0,
    reset_threshold_sec: float = 5.0,
    required_rest_sec: float = 5.0,
    repeat_interval_sec: float = 3.0,
    rest_count_mode: RestCountMode = RestCountMode.PRESENCE,
) -> TimerEngine:
    return TimerEngine(
        work_threshold_sec=work_threshold_sec,
        reset_threshold_sec=reset_threshold_sec,
        required_rest_sec=required_rest_sec,
        repeat_interval_sec=repeat_interval_sec,
        rest_count_mode=rest_count_mode,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 原有測試（向後相容）
# ──────────────────────────────────────────────────────────────────────────────


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


def test_reminding_repeats_after_interval() -> None:
    engine = _engine()
    engine.update(True, 0.0)
    engine.update(True, 10.0)

    repeat_events = engine.update(True, 13.0)
    assert [event.type for event in repeat_events] == [TimerEventType.REMINDER_REPEATED]


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


# ──────────────────────────────────────────────────────────────────────────────
# 新增測試（M2 要求）
# ──────────────────────────────────────────────────────────────────────────────


# 測試 1: 工作達門檻 → REMINDER_TRIGGERED, state == REMINDING
def test_work_threshold_triggers_reminder() -> None:
    engine = _engine(work_threshold_sec=10.0)
    engine.update(True, 0.0)  # WORK_STARTED
    events = engine.update(True, 10.0)

    types = [e.type for e in events]
    assert TimerEventType.REMINDER_TRIGGERED in types
    assert engine.state == TimerState.REMINDING


# 測試 2: 提醒中持續在場 → 每 repeat_interval 送 REMINDER_REPEATED
def test_reminding_repeated_every_interval() -> None:
    engine = _engine(work_threshold_sec=10.0, repeat_interval_sec=3.0)
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING

    ev1 = engine.update(True, 13.0)
    assert [e.type for e in ev1] == [TimerEventType.REMINDER_REPEATED]

    ev2 = engine.update(True, 16.0)
    assert [e.type for e in ev2] == [TimerEventType.REMINDER_REPEATED]


# 測試 3: 提醒中呼叫 start_rest → state == RESTING, REST_STARTED
def test_start_rest_from_reminding() -> None:
    engine = _engine()
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING

    events = engine.start_rest(10.0)
    assert [e.type for e in events] == [TimerEventType.REST_STARTED]
    assert engine.state == TimerState.RESTING


# 測試 4: 提醒中直接離座 → state == RESTING, REST_STARTED
def test_absence_during_reminding_starts_rest() -> None:
    engine = _engine()
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING

    events = engine.update(False, 11.0)  # 離座
    assert [e.type for e in events] == [TimerEventType.REST_STARTED]
    assert engine.state == TimerState.RESTING


# 測試 5: PRESENCE 模式：離座累計達 required_rest 後回座 → RETURN_PROMPT；中途回座不重來
def test_presence_mode_rest_accumulates_absence_only() -> None:
    engine = _engine(required_rest_sec=5.0, rest_count_mode=RestCountMode.PRESENCE)
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING
    engine.start_rest(10.0)     # → RESTING

    # 離座 3 秒
    engine.update(False, 11.0)
    engine.update(False, 13.0)  # accumulated = 2s

    # 中途回座 2 秒（不累計）
    engine.update(True, 15.0)
    engine.update(True, 17.0)

    # 再離座 3 秒（累計共 5s）
    engine.update(False, 18.0)
    engine.update(False, 20.0)  # accumulated = 4s
    engine.update(False, 21.0)  # accumulated = 5s

    # 回座 → should emit RETURN_PROMPT
    events = engine.update(True, 22.0)
    assert TimerEventType.RETURN_PROMPT in [e.type for e in events]
    assert engine.state == TimerState.AWAITING_RETURN


# 測試 6: FIXED 模式：start_rest 後經 required_rest → 滿足；回座 → RETURN_PROMPT
def test_fixed_mode_rest_satisfied_regardless_of_presence() -> None:
    engine = _engine(required_rest_sec=5.0, rest_count_mode=RestCountMode.FIXED)
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING
    engine.start_rest(10.0)    # → RESTING, rest_started_at = 10

    # 在場期間過 5 秒（FIXED 模式不管 presence）
    engine.update(True, 12.0)
    engine.update(True, 14.0)

    # 到 15 秒：滿 5 秒，且 present → RETURN_PROMPT
    events = engine.update(True, 15.0)
    assert TimerEventType.RETURN_PROMPT in [e.type for e in events]
    assert engine.state == TimerState.AWAITING_RETURN


# 測試 7: AWAITING_RETURN update 不改狀態；confirm_return → REST_ENDED+WORK_STARTED, work_elapsed=0
def test_awaiting_return_update_noop_and_confirm_return() -> None:
    engine = _engine(required_rest_sec=5.0, rest_count_mode=RestCountMode.FIXED)
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING
    engine.start_rest(10.0)    # → RESTING

    engine.update(True, 15.0)  # satisfied → AWAITING_RETURN

    # AWAITING_RETURN: update should not change state
    engine.update(True, 16.0)
    engine.update(False, 17.0)
    assert engine.state == TimerState.AWAITING_RETURN

    # confirm_return
    events = engine.confirm_return(20.0)
    types = [e.type for e in events]
    assert TimerEventType.REST_ENDED in types
    assert TimerEventType.WORK_STARTED in types
    assert engine.state == TimerState.WORKING

    snap = engine.snapshot(20.0)
    assert snap.work_elapsed_sec == 0.0


# 測試 8 (需求5): 暫停凍結 — work_elapsed 不含暫停期間
def test_pause_freeze_does_not_accumulate_elapsed() -> None:
    engine = _engine(work_threshold_sec=100.0)
    engine.update(True, 0.0)
    engine.update(True, 4.0)   # work_elapsed = 4s

    # 暫停期間 snapshot.state == SUSPENDED
    engine.pause(5.0)
    assert engine.state == TimerState.SUSPENDED
    snap_paused = engine.snapshot(30.0)
    assert snap_paused.state == TimerState.SUSPENDED

    # 暫停中 update 無效
    engine.update(True, 30.0)
    engine.update(True, 59.0)

    # resume，重設基準
    engine.resume(60.0)
    assert engine.state == TimerState.WORKING

    # 小步 update 後 work_elapsed 應仍 ≈ 4s（未含 55s 暫停）
    engine.update(True, 60.1)
    snap = engine.snapshot(60.1)
    assert abs(snap.work_elapsed_sec - 4.1) < 0.01


# 測試 9: AWAY 未達 reset_threshold 回座續計；達門檻 → WORK_ENDED(reset), IDLE
def test_away_resume_and_reset() -> None:
    engine = _engine(work_threshold_sec=100.0, reset_threshold_sec=5.0)
    engine.update(True, 0.0)
    engine.update(True, 4.0)   # work_elapsed = 4s

    # 短暫離座（不達 reset_threshold）
    engine.update(False, 5.0)
    engine.update(True, 8.0)   # return before 5s absence → stays WORKING
    assert engine.state == TimerState.WORKING
    snap = engine.snapshot(8.0)
    assert snap.work_elapsed_sec == 4.0  # preserved

    # 離座超過 reset_threshold
    engine.update(False, 9.0)
    events = engine.update(False, 14.0)  # 5s absence → reset

    types = [e.type for e in events]
    assert TimerEventType.WORK_ENDED in types
    ended_event = next(e for e in events if e.type == TimerEventType.WORK_ENDED)
    assert ended_event.ended_by == "reset"
    assert engine.state == TimerState.IDLE


# 測試 10: RESTING 時 snapshot 回報 rest_remaining_sec / rest_elapsed_sec
def test_snapshot_resting_rest_remaining_and_elapsed() -> None:
    # FIXED 模式: rest_remaining_sec 正確
    engine_fixed = _engine(required_rest_sec=10.0, rest_count_mode=RestCountMode.FIXED)
    engine_fixed.update(True, 0.0)
    engine_fixed.update(True, 10.0)
    engine_fixed.start_rest(10.0)  # rest_started_at = 10

    snap = engine_fixed.snapshot(13.0)
    assert snap.state == TimerState.RESTING
    assert abs(snap.rest_remaining_sec - 7.0) < 0.01  # 10 - 3 = 7

    # PRESENCE 模式: rest_elapsed_sec 正確
    engine_pres = _engine(required_rest_sec=10.0, rest_count_mode=RestCountMode.PRESENCE)
    engine_pres.update(True, 0.0)
    engine_pres.update(True, 10.0)
    engine_pres.start_rest(10.0)

    engine_pres.update(False, 11.0)  # dt = 1s (from start_rest at 10)
    engine_pres.update(False, 14.0)  # dt = 3s

    snap2 = engine_pres.snapshot(14.0)
    assert snap2.state == TimerState.RESTING
    assert abs(snap2.rest_elapsed_sec - 4.0) < 0.01  # 1 + 3 = 4s absence
