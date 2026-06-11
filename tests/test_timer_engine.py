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


# 測試 3: 提醒中呼叫 start_rest → state == RESTING, WORK_ENDED + REST_STARTED
def test_start_rest_from_reminding() -> None:
    engine = _engine()
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING

    events = engine.start_rest(10.0)
    types = [e.type for e in events]
    # FR-4: WORK_ENDED must appear before REST_STARTED
    assert TimerEventType.WORK_ENDED in types
    assert TimerEventType.REST_STARTED in types
    assert types.index(TimerEventType.WORK_ENDED) < types.index(TimerEventType.REST_STARTED)
    assert engine.state == TimerState.RESTING


# 測試 4: 提醒中直接離座 → state == RESTING, WORK_ENDED + REST_STARTED
def test_absence_during_reminding_starts_rest() -> None:
    engine = _engine()
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING

    events = engine.update(False, 11.0)  # 離座
    types = [e.type for e in events]
    # FR-4: WORK_ENDED must appear before REST_STARTED
    assert TimerEventType.WORK_ENDED in types
    assert TimerEventType.REST_STARTED in types
    assert types.index(TimerEventType.WORK_ENDED) < types.index(TimerEventType.REST_STARTED)
    assert engine.state == TimerState.RESTING


# 測試 5: PRESENCE 模式：離座累計達 required_rest 後回座 → RETURN_PROMPT；中途回座不重來
def test_presence_mode_rest_accumulates_absence_only() -> None:
    engine = _engine(required_rest_sec=5.0, rest_count_mode=RestCountMode.PRESENCE)
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING
    engine.start_rest(10.0)  # → RESTING

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
    engine.start_rest(10.0)  # → RESTING, rest_started_at = 10

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
    engine.start_rest(10.0)  # → RESTING

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
    engine.update(True, 4.0)  # work_elapsed = 4s

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
    engine.update(True, 4.0)  # work_elapsed = 4s

    # 短暫離座（不達 reset_threshold）
    engine.update(False, 5.0)
    engine.update(True, 8.0)  # return before 5s absence → stays WORKING
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


# ──────────────────────────────────────────────────────────────────────────────
# 新增測試（本次需求 FR-1、FR-2、FR-4）
# ──────────────────────────────────────────────────────────────────────────────


# ── FR-1: overtime_sec ───────────────────────────────────────────────────────


def test_overtime_sec_accumulates_in_reminding() -> None:
    """overtime_sec grows linearly with work_elapsed beyond the threshold."""
    engine = _engine(work_threshold_sec=10.0)
    engine.update(True, 0.0)   # WORK_STARTED
    engine.update(True, 10.0)  # → REMINDING (work_elapsed == threshold)

    snap10 = engine.snapshot(10.0)
    assert snap10.overtime_sec == 0.0  # just crossed threshold

    engine.update(True, 13.0)  # 3 more seconds in REMINDING
    snap13 = engine.snapshot(13.0)
    assert abs(snap13.overtime_sec - 3.0) < 0.01

    engine.update(True, 16.0)  # 6 more seconds total overtime
    snap16 = engine.snapshot(16.0)
    assert abs(snap16.overtime_sec - 6.0) < 0.01


def test_overtime_sec_is_zero_in_non_reminding_states() -> None:
    """overtime_sec is 0 in WORKING state (and all non-REMINDING states)."""
    engine = _engine(work_threshold_sec=10.0)
    engine.update(True, 0.0)   # WORKING
    engine.update(True, 4.0)

    snap = engine.snapshot(4.0)
    assert snap.overtime_sec == 0.0
    assert snap.state == TimerState.WORKING


def test_overtime_sec_frozen_during_pause() -> None:
    """In SUSPENDED state, overtime_sec is frozen (work_elapsed doesn't grow)."""
    engine = _engine(work_threshold_sec=10.0)
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING
    engine.update(True, 13.0)  # overtime = 3s

    snap_before = engine.snapshot(13.0)
    assert abs(snap_before.overtime_sec - 3.0) < 0.01

    engine.pause(13.0)
    # Even though real time passes, paused updates return [] and don't accumulate
    engine.update(True, 60.0)
    engine.update(True, 90.0)

    snap_paused = engine.snapshot(90.0)
    assert snap_paused.state == TimerState.SUSPENDED
    # overtime_sec should still reflect the frozen work_elapsed (3s above threshold)
    assert abs(snap_paused.overtime_sec - 3.0) < 0.01


# ── FR-4: WORK_ENDED completeness ───────────────────────────────────────────


def test_work_ended_emitted_by_start_rest_with_correct_duration() -> None:
    """start_rest() path: WORK_ENDED has duration == work_elapsed, ended_by == 'rest'."""
    engine = _engine(work_threshold_sec=10.0)
    engine.update(True, 0.0)   # WORK_STARTED
    engine.update(True, 10.0)  # → REMINDING; work_elapsed = 10
    engine.update(True, 13.0)  # work_elapsed = 13

    events = engine.start_rest(13.0)
    types = [e.type for e in events]
    assert TimerEventType.WORK_ENDED in types

    work_ended = next(e for e in events if e.type == TimerEventType.WORK_ENDED)
    assert abs(work_ended.duration_sec - 13.0) < 0.01
    assert work_ended.ended_by == "rest"

    # work_elapsed resets to 0 after entering rest
    snap = engine.snapshot(13.0)
    assert snap.work_elapsed_sec == 0.0


def test_work_ended_emitted_by_auto_absence_with_correct_duration() -> None:
    """Auto-absence path: WORK_ENDED has duration == work_elapsed, ended_by == 'rest'."""
    engine = _engine(work_threshold_sec=10.0)
    engine.update(True, 0.0)   # WORK_STARTED
    engine.update(True, 10.0)  # → REMINDING; work_elapsed = 10
    engine.update(True, 12.0)  # work_elapsed = 12

    events = engine.update(False, 12.0)  # absence → RESTING
    types = [e.type for e in events]
    assert TimerEventType.WORK_ENDED in types

    work_ended = next(e for e in events if e.type == TimerEventType.WORK_ENDED)
    assert abs(work_ended.duration_sec - 12.0) < 0.01
    assert work_ended.ended_by == "rest"

    snap = engine.snapshot(12.0)
    assert snap.work_elapsed_sec == 0.0


def test_work_ended_emitted_exactly_once_per_cycle() -> None:
    """Full work→remind→rest→confirm cycle: WORK_ENDED fires exactly once."""
    engine = _engine(
        work_threshold_sec=10.0,
        required_rest_sec=5.0,
        rest_count_mode=RestCountMode.FIXED,
    )

    all_events: list = []

    all_events += engine.update(True, 0.0)    # WORK_STARTED
    all_events += engine.update(True, 10.0)   # → REMINDING
    # Manually start rest (WORK_ENDED should appear here)
    all_events += engine.start_rest(10.0)     # WORK_ENDED + REST_STARTED
    all_events += engine.update(True, 15.0)   # rest satisfied → RETURN_PROMPT
    # confirm_return should NOT emit another WORK_ENDED
    all_events += engine.confirm_return(15.0)  # REST_ENDED + WORK_STARTED

    work_ended_events = [e for e in all_events if e.type == TimerEventType.WORK_ENDED]
    assert len(work_ended_events) == 1, (
        f"Expected exactly 1 WORK_ENDED, got {len(work_ended_events)}: {work_ended_events}"
    )
    assert work_ended_events[0].ended_by == "rest"


# ── FR-2: pause/resume freeze contract ───────────────────────────────────────


def test_pause_freeze_work_elapsed_unchanged_during_pause() -> None:
    """work_elapsed does not change during pause regardless of update() calls."""
    engine = _engine(work_threshold_sec=100.0)
    engine.update(True, 0.0)
    engine.update(True, 5.0)  # work_elapsed = 5

    snap_before = engine.snapshot(5.0)
    assert abs(snap_before.work_elapsed_sec - 5.0) < 0.01

    engine.pause(5.0)
    # Multiple updates during pause — all return [] and don't advance time
    engine.update(True, 10.0)
    engine.update(True, 30.0)
    engine.update(True, 100.0)

    snap_paused = engine.snapshot(100.0)
    assert abs(snap_paused.work_elapsed_sec - 5.0) < 0.01, (
        "work_elapsed must be frozen during pause"
    )


def test_resume_first_update_has_near_zero_dt() -> None:
    """After resume(now), the first update at a slightly later time accumulates ≈ dt only."""
    engine = _engine(work_threshold_sec=100.0)
    engine.update(True, 0.0)
    engine.update(True, 5.0)  # work_elapsed = 5

    engine.pause(5.0)
    engine.update(True, 55.0)  # would be 50s if not paused

    engine.resume(55.0)  # resets _last_t = 55
    engine.update(True, 55.1)  # dt = 0.1, not 50.1

    snap = engine.snapshot(55.1)
    assert abs(snap.work_elapsed_sec - 5.1) < 0.01, (
        "Resume must not back-attribute pause interval as work time"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 新增測試（proposal §4.1：resume 不得以過期狀態覆寫指令結果）
# ──────────────────────────────────────────────────────────────────────────────


def test_confirm_return_during_pause_survives_resume() -> None:
    """§4.1 測試 A：AWAITING_RETURN → pause → confirm_return → resume。

    resume 後狀態必須是 WORKING（而非被過期的 _state_before_pause 覆寫回
    AWAITING_RETURN 造成死鎖），且事件不重複。
    """
    engine = _engine(required_rest_sec=5.0, rest_count_mode=RestCountMode.FIXED)
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING
    engine.start_rest(10.0)  # → RESTING, rest_started_at = 10
    engine.update(True, 15.0)  # rest satisfied → AWAITING_RETURN
    assert engine.state == TimerState.AWAITING_RETURN

    engine.pause(16.0)
    # 使用者在暫停期間按下歡迎回來對話框的確認鈕
    events = engine.confirm_return(20.0)
    types = [e.type for e in events]
    assert TimerEventType.REST_ENDED in types
    assert TimerEventType.WORK_STARTED in types
    # 暫停期間（16→20 共 4 秒）不得計入休息時長：實際休息 = 16 - 10 = 6 秒
    rest_ended = next(e for e in events if e.type == TimerEventType.REST_ENDED)
    assert abs(rest_ended.duration_sec - 6.0) < 0.01

    engine.resume(30.0)
    assert engine.state == TimerState.WORKING, (
        "resume must not overwrite state back to stale AWAITING_RETURN"
    )

    # resume 後不得重複發出任何事件（已在 confirm_return 發過）
    follow = engine.update(True, 30.1)
    assert follow == []

    # 再次 confirm_return 應為 no-op（狀態已是 WORKING）
    assert engine.confirm_return(31.0) == []


def test_start_rest_during_pause_survives_resume() -> None:
    """§4.1 測試 B：REMINDING → pause → start_rest → resume。

    resume 後狀態必須是 RESTING，且不得產生第二筆 work session
    （即不得再 emit WORK_ENDED / REST_STARTED）。
    """
    engine = _engine(work_threshold_sec=10.0)
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING
    engine.pause(11.0)

    events = engine.start_rest(12.0)  # 暫停期間按「開始休息」
    types = [e.type for e in events]
    assert types == [TimerEventType.WORK_ENDED, TimerEventType.REST_STARTED]

    engine.resume(60.0)
    assert engine.state == TimerState.RESTING, (
        "resume must not overwrite state back to stale REMINDING"
    )

    # resume 後離座不得重複關閉 work session
    follow = engine.update(False, 60.1)
    follow_types = [e.type for e in follow]
    assert TimerEventType.WORK_ENDED not in follow_types
    assert TimerEventType.REST_STARTED not in follow_types


# ──────────────────────────────────────────────────────────────────────────────
# 新增測試（proposal §4.4：暫停時長不得計入絕對時間戳判斷）
# ──────────────────────────────────────────────────────────────────────────────


def test_pause_during_away_does_not_trigger_reset_on_resume() -> None:
    """§4.4 測試 C-1：AWAY 暫停超過 reset_threshold 再 resume，不得觸發重置。"""
    engine = _engine(work_threshold_sec=100.0, reset_threshold_sec=5.0)
    engine.update(True, 0.0)
    engine.update(True, 4.0)  # WORKING, work_elapsed = 4
    engine.update(False, 5.0)  # → AWAY, away_since = 5
    engine.update(False, 6.0)  # 離席 1 秒
    engine.pause(6.0)
    engine.resume(60.0)  # 暫停 54 秒（遠超 reset_threshold = 5）

    events = engine.update(False, 60.5)  # 等效離席僅 1.5 秒
    assert TimerEventType.WORK_ENDED not in [e.type for e in events], (
        "pause duration must not count toward the away reset threshold"
    )
    assert engine.state == TimerState.AWAY

    # 繼續離席到真正滿足門檻（等效離席 5.5 秒）→ 才重置
    events2 = engine.update(False, 64.5)
    assert TimerEventType.WORK_ENDED in [e.type for e in events2]
    assert engine.state == TimerState.IDLE


def test_pause_during_reminding_does_not_repeat_reminder_on_resume() -> None:
    """§4.4 測試 C-2：REMINDING 暫停超過 repeat_interval 再 resume，不得立即重發提醒。"""
    engine = _engine(work_threshold_sec=10.0, repeat_interval_sec=3.0)
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING, reminder_last_t = 10
    engine.update(True, 11.0)
    engine.pause(11.0)
    engine.resume(60.0)  # 暫停 49 秒（遠超 repeat_interval = 3）

    events = engine.update(True, 60.5)  # 等效僅過 1.5 秒
    assert TimerEventType.REMINDER_REPEATED not in [e.type for e in events], (
        "pause duration must not count toward the reminder repeat interval"
    )

    # 等效過滿 repeat_interval（reminder_last_t 平移至 59 → 62 起可重發）
    events2 = engine.update(True, 62.5)
    assert [e.type for e in events2] == [TimerEventType.REMINDER_REPEATED]


def test_fixed_rest_not_credited_by_pause_and_rest_duration_excludes_pause() -> None:
    """§4.4 測試 D：RESTING（fixed 模式）跨暫停。

    必要休息時長不得被暫停折抵；confirm_return 的 rest_duration 不含暫停時長。
    """
    engine = _engine(required_rest_sec=5.0, rest_count_mode=RestCountMode.FIXED)
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING
    engine.start_rest(10.0)  # → RESTING, rest_started_at = 10
    engine.update(True, 12.0)  # 已休息 2 秒
    engine.pause(12.0)
    engine.resume(112.0)  # 暫停 100 秒

    # 暫停時長不得折抵必要休息（等效僅休息 2.1 秒 < 5 秒）
    events = engine.update(True, 112.1)
    assert TimerEventType.RETURN_PROMPT not in [e.type for e in events], (
        "pause duration must not be credited toward the required rest"
    )
    assert engine.state == TimerState.RESTING

    # rest_started_at 平移至 110 → 115 起滿足
    events2 = engine.update(True, 115.5)
    assert TimerEventType.RETURN_PROMPT in [e.type for e in events2]
    assert engine.state == TimerState.AWAITING_RETURN

    # confirm_return 的休息時長不含暫停：116 - 110 = 6 秒
    events3 = engine.confirm_return(116.0)
    rest_ended = next(e for e in events3 if e.type == TimerEventType.REST_ENDED)
    assert abs(rest_ended.duration_sec - 6.0) < 0.01


def test_start_rest_during_pause_counts_rest_from_resume() -> None:
    """§4.4 補充：暫停期間下達 start_rest，固定休息時間自 resume 起算。

    暫停期間設定的時間戳在 resume 平移時需 clamp 至 resume 時刻，
    不得平移到未來（過度平移）也不得保留暫停中的舊值（折抵休息）。
    """
    engine = _engine(required_rest_sec=5.0, rest_count_mode=RestCountMode.FIXED)
    engine.update(True, 0.0)
    engine.update(True, 10.0)  # → REMINDING
    engine.pause(11.0)
    engine.start_rest(50.0)  # 暫停期間開始休息
    engine.resume(100.0)

    # 休息自 resume（100）起算：103 時僅休息 3 秒 → 未滿足
    events = engine.update(True, 103.0)
    assert TimerEventType.RETURN_PROMPT not in [e.type for e in events]
    assert engine.state == TimerState.RESTING

    # 105.5 時休息 5.5 秒 → 滿足
    events2 = engine.update(True, 105.5)
    assert TimerEventType.RETURN_PROMPT in [e.type for e in events2]
    assert engine.state == TimerState.AWAITING_RETURN
