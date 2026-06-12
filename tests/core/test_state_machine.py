"""RestFlowMachine 轉移表逐列測試（spec §4 / §4.2 / §5 / §6）。"""

from __future__ import annotations

import pytest

from src.core.events import Command, TimerEvent, TimerEventType, TimerState
from src.core.state_machine import MachineConfig, RestFlowMachine


class StubEscalation:
    """符合 EscalationLike 的測試替身（語意同 T2 EscalationPolicy）。"""

    def __init__(
        self,
        stage_after_sec: tuple[float, float, float] = (60.0, 120.0, 180.0),
        max_stage: int = 3,
    ) -> None:
        self._stage_after_sec = stage_after_sec
        self._max_stage = max_stage

    @property
    def max_stage(self) -> int:
        return self._max_stage

    def stage_for(self, dwell_sec: float) -> int:
        stage = 0
        for threshold in self._stage_after_sec:
            if dwell_sec >= threshold:
                stage += 1
        return min(stage, self._max_stage)


def make(
    mode: str = "presence",
    acc: str = "work",
    intr: str = "remind",
    apply_rem: bool = True,
    max_stage: int = 3,
    interrupt_after: float = 120.0,
) -> RestFlowMachine:
    cfg = MachineConfig(
        work_threshold_sec=10,
        reset_threshold_sec=6,
        required_rest_sec=8,
        repeat_interval_sec=12,
        rest_count_mode=mode,
        pending_accounting=acc,
        interrupt_behavior=intr,
        rest_interrupt_after_sec=interrupt_after,
        apply_to_reminding=apply_rem,
    )
    return RestFlowMachine(cfg, StubEscalation((60.0, 120.0, 180.0), max_stage))


def types_of(events: list[TimerEvent]) -> list[TimerEventType]:
    return [e.type for e in events]


def stages_of(events: list[TimerEvent]) -> list[int]:
    return [e.stage for e in events if e.type is TimerEventType.ESCALATED]


def drive_to_reminding(machine: RestFlowMachine, t0: float = 0.0) -> None:
    """tick 有人直到超過工作門檻（threshold=10）：t0 起、t0+10 進 REMINDING。"""
    assert types_of(machine.tick(True, t0)) == [TimerEventType.WORK_STARTED]
    assert types_of(machine.tick(True, t0 + 10)) == [TimerEventType.REMINDER_TRIGGERED]


# ──────────────────────────────────────────────────────────────────────────────
# MachineConfig 驗證
# ──────────────────────────────────────────────────────────────────────────────


def test_machine_config_rejects_unknown_enum_values() -> None:
    with pytest.raises(ValueError):
        MachineConfig(10, 6, 8, 12, rest_count_mode="bogus")
    with pytest.raises(ValueError):
        MachineConfig(10, 6, 8, 12, pending_accounting="bogus")
    with pytest.raises(ValueError):
        MachineConfig(10, 6, 8, 12, interrupt_behavior="bogus")


# ──────────────────────────────────────────────────────────────────────────────
# IDLE / WORKING / AWAY 基本流
# ──────────────────────────────────────────────────────────────────────────────


def test_idle_present_starts_working() -> None:
    m = make()
    events = m.tick(True, 0.0)
    assert types_of(events) == [TimerEventType.WORK_STARTED]
    assert m.snapshot(0.0).state is TimerState.WORKING


def test_idle_absent_stays_idle() -> None:
    m = make()
    assert m.tick(False, 0.0) == []
    assert m.snapshot(0.0).state is TimerState.IDLE


def test_working_threshold_triggers_reminder() -> None:
    m = make()
    m.tick(True, 0.0)
    assert m.tick(True, 4.0) == []
    events = m.tick(True, 10.0)
    assert types_of(events) == [TimerEventType.REMINDER_TRIGGERED]
    assert m.snapshot(10.0).state is TimerState.REMINDING


def test_working_brief_absence_preserves_elapsed() -> None:
    m = make()
    m.tick(True, 0.0)
    m.tick(True, 4.0)
    m.tick(False, 5.0)
    assert m.snapshot(5.0).state is TimerState.AWAY
    m.tick(True, 8.0)  # 回座（離席 3s < reset 6s）
    snap = m.snapshot(8.0)
    assert snap.state is TimerState.WORKING
    assert snap.work_elapsed_sec == pytest.approx(4.0)


def test_away_reset_ends_work_and_returns_to_idle() -> None:
    m = make()
    m.tick(True, 0.0)
    m.tick(True, 4.0)
    m.tick(False, 5.0)
    events = m.tick(False, 11.0)  # 離席 6s >= reset 6s
    assert types_of(events) == [TimerEventType.WORK_ENDED]
    assert events[0].ended_by == "reset"
    assert events[0].duration_sec == pytest.approx(4.0)
    assert m.snapshot(11.0).state is TimerState.IDLE


def test_return_after_reset_ends_implicit_rest() -> None:
    m = make()
    m.tick(True, 0.0)
    m.tick(True, 4.0)
    m.tick(False, 5.0)
    m.tick(False, 11.0)  # reset；隱式休息自離席（t=5）起追蹤
    events = m.tick(True, 20.0)
    assert types_of(events) == [TimerEventType.REST_ENDED, TimerEventType.WORK_STARTED]
    assert events[0].duration_sec == pytest.approx(15.0)  # 20 - 5
    assert m.snapshot(20.0).state is TimerState.WORKING


def test_tick_with_time_going_backwards_raises() -> None:
    m = make()
    m.tick(True, 10.0)
    with pytest.raises(ValueError):
        m.tick(True, 9.0)


# ──────────────────────────────────────────────────────────────────────────────
# REMINDING：重複提醒與升級階梯（apply_to_reminding 兩態）
# ──────────────────────────────────────────────────────────────────────────────


def test_reminding_repeats_after_interval() -> None:
    m = make()
    drive_to_reminding(m)  # REMINDING 自 t=10 起
    assert m.tick(True, 21.0) == []  # 11s < 12s
    assert TimerEventType.REMINDER_REPEATED in types_of(m.tick(True, 22.0))
    assert TimerEventType.REMINDER_REPEATED in types_of(m.tick(True, 34.0))


def test_reminding_overtime_escalates_each_stage_and_locks() -> None:
    m = make()
    drive_to_reminding(m)  # 階梯錨點 t=10
    assert stages_of(m.tick(True, 70.0)) == [1]   # dwell 60
    assert stages_of(m.tick(True, 130.0)) == [2]  # dwell 120
    events = m.tick(True, 190.0)                  # dwell 180
    assert stages_of(events) == [3]
    assert TimerEventType.LOCK_REQUESTED in types_of(events)


def test_reminding_stage_jump_emits_each_stage_once() -> None:
    m = make()
    drive_to_reminding(m)
    events = m.tick(True, 140.0)  # dwell 130：一次跨過兩階
    assert stages_of(events) == [1, 2]


def test_reminding_no_escalation_when_apply_to_reminding_false() -> None:
    m = make(apply_rem=False)
    drive_to_reminding(m)
    events = m.tick(True, 400.0)
    assert TimerEventType.ESCALATED not in types_of(events)
    assert TimerEventType.LOCK_REQUESTED not in types_of(events)
    assert m.snapshot(400.0).escalation_stage == -1


def test_reminding_absence_starts_rest() -> None:
    m = make()
    drive_to_reminding(m)
    m.tick(True, 13.0)  # work_elapsed = 13
    events = m.tick(False, 14.0)
    assert types_of(events) == [TimerEventType.WORK_ENDED, TimerEventType.REST_STARTED]
    assert events[0].ended_by == "rest"
    assert events[0].duration_sec == pytest.approx(13.0)
    snap = m.snapshot(14.0)
    assert snap.state is TimerState.RESTING
    assert snap.work_elapsed_sec == 0.0


def test_lock_requested_once_per_work_cycle_across_sources() -> None:
    m = make()
    drive_to_reminding(m)
    events = m.tick(True, 190.0)  # REMINDING dwell 180 → 鎖屏
    assert TimerEventType.LOCK_REQUESTED in types_of(events)
    # 同一工作週期內進 REST_PENDING 再衝到第 3 階 → 不再鎖
    m.command(Command.START_REST, 191.0)
    events2 = m.tick(True, 372.0)  # pending dwell 181
    assert stages_of(events2) == [1, 2, 3]
    assert TimerEventType.LOCK_REQUESTED not in types_of(events2)


# ──────────────────────────────────────────────────────────────────────────────
# REST_PENDING：進入 / 記帳兩模式 / 離席 / 取消 / 滯留升級 / 封頂
# ──────────────────────────────────────────────────────────────────────────────


def test_start_rest_enters_pending_without_closing_work_session() -> None:
    m = make()
    drive_to_reminding(m)
    events = m.command(Command.START_REST, 20.0)
    assert types_of(events) == [TimerEventType.REST_PENDING_ENTERED]
    assert m.snapshot(20.0).state is TimerState.REST_PENDING


def test_pending_work_keeps_accruing_in_work_mode() -> None:
    m = make()
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    m.tick(True, 25.0)
    snap = m.snapshot(25.0)
    assert snap.work_elapsed_sec >= 15.0  # 按鈕後仍續計
    assert snap.overtime_sec == pytest.approx(5.0)  # 超時亦續計


def test_pending_leaves_to_resting_closes_session() -> None:
    m = make()
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    events = m.tick(False, 30.0)
    assert types_of(events) == [TimerEventType.WORK_ENDED, TimerEventType.REST_STARTED]
    assert events[0].ended_by == "rest"
    assert events[0].duration_sec == pytest.approx(10.0)
    assert m.snapshot(30.0).state is TimerState.RESTING


def test_pending_dwell_escalates_and_requests_lock_once() -> None:
    m = make()
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    assert stages_of(m.tick(True, 81.0)) == [1]  # dwell 61
    events = m.tick(True, 201.0)                 # dwell 181 → 2、3 階
    assert stages_of(events) == [2, 3]
    assert TimerEventType.LOCK_REQUESTED in types_of(events)
    assert TimerEventType.LOCK_REQUESTED not in types_of(m.tick(True, 240.0))  # 單週期一次


def test_pending_cancel_returns_to_reminding_with_seamless_session() -> None:
    m = make()
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    m.tick(True, 25.0)  # work_elapsed = 15
    events = m.command(Command.CANCEL_PENDING, 26.0)
    assert types_of(events) == [TimerEventType.REST_PENDING_CANCELLED]
    assert m.snapshot(26.0).state is TimerState.REMINDING
    m.tick(True, 30.0)  # work_elapsed = 19
    events2 = m.tick(False, 31.0)
    assert types_of(events2) == [TimerEventType.WORK_ENDED, TimerEventType.REST_STARTED]
    assert events2[0].duration_sec == pytest.approx(19.0)  # 無縫延續，含 pending 前後


def test_pending_escalation_resets_on_entry_and_cancel() -> None:
    m = make()
    drive_to_reminding(m)
    m.tick(True, 70.0)  # REMINDING dwell 60 → 第 1 階
    assert m.snapshot(70.0).escalation_stage == 1
    m.command(Command.START_REST, 71.0)  # 按鈕＝善意 → 階梯歸零重計
    assert m.snapshot(71.0).escalation_stage == 0
    assert TimerEventType.ESCALATED not in types_of(m.tick(True, 130.0))  # dwell 59
    assert stages_of(m.tick(True, 131.0)) == [1]  # dwell 60 → 重新升到第 1 階
    m.command(Command.CANCEL_PENDING, 132.0)  # 取消 → 回 REMINDING、階梯再歸零
    assert m.snapshot(132.0).escalation_stage == 0
    assert TimerEventType.ESCALATED not in types_of(m.tick(True, 191.0))  # dwell 59


def test_pending_max_stage_caps_and_never_locks() -> None:
    m = make(max_stage=1)
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    events = m.tick(True, 999.0)
    assert stages_of(events) == [1]
    assert TimerEventType.LOCK_REQUESTED not in types_of(events)
    assert m.snapshot(999.0).escalation_stage == 1


def test_max_stage_zero_keeps_stage_zero() -> None:
    m = make(max_stage=0)
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    events = m.tick(True, 999.0)
    assert TimerEventType.ESCALATED not in types_of(events)
    assert m.snapshot(999.0).escalation_stage == 0


def test_pending_none_settles_session_on_entry() -> None:
    m = make(acc="none")
    drive_to_reminding(m)
    events = m.command(Command.START_REST, 20.0)
    assert types_of(events) == [
        TimerEventType.WORK_ENDED,
        TimerEventType.REST_PENDING_ENTERED,
    ]
    assert events[0].ended_by == "rest_pending"
    assert events[0].duration_sec == pytest.approx(10.0)
    assert m.snapshot(20.0).state is TimerState.REST_PENDING


def test_pending_none_freezes_work_accrual() -> None:
    m = make(acc="none")
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    m.tick(True, 40.0)
    assert m.snapshot(40.0).work_elapsed_sec == pytest.approx(10.0)  # 凍結


def test_pending_none_departure_does_not_emit_second_work_ended() -> None:
    m = make(acc="none")
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    events = m.tick(False, 30.0)
    assert types_of(events) == [TimerEventType.REST_STARTED]  # 已結算，不再發 WORK_ENDED
    assert m.snapshot(30.0).state is TimerState.RESTING


def test_pending_none_cancel_opens_new_session() -> None:
    m = make(acc="none")
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    events = m.command(Command.CANCEL_PENDING, 50.0)
    assert types_of(events) == [
        TimerEventType.REST_PENDING_CANCELLED,
        TimerEventType.WORK_STARTED,
    ]
    snap = m.snapshot(50.0)
    assert snap.state is TimerState.REMINDING
    assert snap.work_elapsed_sec == 0.0
    m.tick(True, 55.0)
    events2 = m.tick(False, 56.0)
    work_ended = next(e for e in events2 if e.type is TimerEventType.WORK_ENDED)
    assert work_ended.duration_sec == pytest.approx(5.0)  # 只算取消後的工作


def test_pending_dwell_reported_in_snapshot() -> None:
    m = make()
    drive_to_reminding(m)
    assert m.snapshot(15.0).pending_dwell_sec == 0.0  # 非 REST_PENDING 為 0
    m.command(Command.START_REST, 20.0)
    m.tick(True, 33.0)
    assert m.snapshot(33.0).pending_dwell_sec == pytest.approx(13.0)


# ──────────────────────────────────────────────────────────────────────────────
# fixed 模式 START_REST 直進 RESTING
# ──────────────────────────────────────────────────────────────────────────────


def test_fixed_mode_start_rest_goes_directly_to_resting() -> None:
    m = make(mode="fixed")
    drive_to_reminding(m)
    events = m.command(Command.START_REST, 20.0)
    assert types_of(events) == [TimerEventType.WORK_ENDED, TimerEventType.REST_STARTED]
    assert events[0].ended_by == "rest"
    assert m.snapshot(20.0).state is TimerState.RESTING


def test_commands_in_wrong_states_are_noops() -> None:
    m = make()
    assert m.command(Command.START_REST, 0.0) == []  # IDLE
    assert m.command(Command.CANCEL_PENDING, 0.0) == []
    assert m.command(Command.CONFIRM_RETURN, 0.0) == []
    m.tick(True, 0.0)  # WORKING
    assert m.command(Command.START_REST, 1.0) == []
    assert m.command(Command.CANCEL_PENDING, 1.0) == []
    assert m.command(Command.CONFIRM_RETURN, 1.0) == []
    assert m.snapshot(1.0).state is TimerState.WORKING


# ──────────────────────────────────────────────────────────────────────────────
# RESTING：累計、滿額、snapshot、中斷（remind / new_work）、fixed 無中斷
# ──────────────────────────────────────────────────────────────────────────────


def test_presence_rest_counts_absence_only_then_prompts_return() -> None:
    m = make()  # required_rest = 8
    drive_to_reminding(m)
    m.tick(False, 11.0)  # → RESTING
    m.tick(False, 14.0)  # 累計 3
    m.tick(True, 15.0)   # 中途回座（不累計）
    m.tick(True, 17.0)
    m.tick(False, 18.0)  # 再離席（累計 4）
    m.tick(False, 23.0)  # 累計 9 >= 8 → 滿額
    events = m.tick(True, 24.0)
    assert types_of(events) == [TimerEventType.RETURN_PROMPT]
    assert m.snapshot(24.0).state is TimerState.AWAITING_RETURN


def test_resting_snapshot_reports_elapsed_and_remaining() -> None:
    m = make()
    drive_to_reminding(m)
    m.tick(False, 11.0)
    m.tick(False, 15.0)  # 累計 4
    snap = m.snapshot(15.0)
    assert snap.state is TimerState.RESTING
    assert snap.rest_elapsed_sec == pytest.approx(4.0)
    assert snap.rest_remaining_sec == 0.0

    f = make(mode="fixed")
    drive_to_reminding(f)
    f.command(Command.START_REST, 20.0)
    snap_f = f.snapshot(23.0)
    assert snap_f.state is TimerState.RESTING
    assert snap_f.rest_remaining_sec == pytest.approx(5.0)  # 8 - 3
    assert snap_f.rest_elapsed_sec == 0.0


def test_fixed_rest_satisfied_by_wall_clock_regardless_of_presence() -> None:
    m = make(mode="fixed")
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    assert m.tick(True, 24.0) == []  # 4s < 8s
    events = m.tick(True, 28.0)      # 8s 滿額且有人
    assert types_of(events) == [TimerEventType.RETURN_PROMPT]
    assert m.snapshot(28.0).state is TimerState.AWAITING_RETURN


def test_rest_interrupt_remind_mode_goes_to_reminding() -> None:
    m = make(interrupt_after=5.0)
    drive_to_reminding(m)
    m.tick(False, 11.0)  # → RESTING
    m.tick(False, 13.0)  # 累計 2
    m.tick(True, 14.0)   # 連續在席起點
    events = m.tick(True, 19.0)  # 連續在席 5 >= 5 → 中斷
    assert types_of(events) == [
        TimerEventType.REST_ENDED,
        TimerEventType.REST_INTERRUPTED,
        TimerEventType.WORK_STARTED,
        TimerEventType.REMINDER_TRIGGERED,
    ]
    assert events[0].ended_by == "interrupted"
    assert events[0].duration_sec == pytest.approx(2.0)  # 已累計休息
    snap = m.snapshot(19.0)
    assert snap.state is TimerState.REMINDING
    assert snap.work_elapsed_sec == pytest.approx(5.0)  # 自連續在席時長起算


def test_rest_interrupt_new_work_mode_returns_to_working() -> None:
    m = make(intr="new_work", interrupt_after=5.0)
    drive_to_reminding(m)
    m.tick(False, 11.0)
    m.tick(False, 13.0)  # 累計 2
    m.tick(True, 14.0)
    events = m.tick(True, 19.0)
    assert types_of(events) == [
        TimerEventType.REST_ENDED,
        TimerEventType.REST_INTERRUPTED,
        TimerEventType.WORK_STARTED,
    ]
    snap = m.snapshot(19.0)
    assert snap.state is TimerState.WORKING
    assert snap.work_elapsed_sec == pytest.approx(5.0)
    # 等自然到門檻才再提醒（5 + 5 = 10）
    events2 = m.tick(True, 24.0)
    assert types_of(events2) == [TimerEventType.REMINDER_TRIGGERED]


def test_rest_interrupt_requires_continuous_presence() -> None:
    m = make(interrupt_after=5.0)
    drive_to_reminding(m)
    m.tick(False, 11.0)
    m.tick(True, 12.0)   # 連續在席起點
    m.tick(True, 15.0)   # 連續 3
    m.tick(False, 16.0)  # 斷掉（離席累計 +1）
    m.tick(True, 17.0)   # 重新起算
    events = m.tick(True, 21.0)  # 連續 4 < 5 → 不中斷
    assert events == []
    assert m.snapshot(21.0).state is TimerState.RESTING


def test_rest_interrupt_absent_in_fixed_mode() -> None:
    m = make(mode="fixed", interrupt_after=5.0)
    drive_to_reminding(m)
    m.command(Command.START_REST, 11.0)
    m.tick(True, 12.0)
    events = m.tick(True, 18.0)  # 連續在席 6 >= 5，但 fixed 無中斷；wall 7 < 8 未滿
    assert events == []
    assert m.snapshot(18.0).state is TimerState.RESTING
    events2 = m.tick(True, 19.0)  # wall 8 滿額
    assert types_of(events2) == [TimerEventType.RETURN_PROMPT]


def test_rest_satisfied_wins_over_interrupt() -> None:
    m = make(interrupt_after=5.0)
    drive_to_reminding(m)
    m.tick(False, 11.0)
    m.tick(False, 19.0)  # 累計 8 → 滿額
    events = m.tick(True, 20.0)
    assert types_of(events) == [TimerEventType.RETURN_PROMPT]
    assert TimerEventType.REST_INTERRUPTED not in types_of(events)


# ──────────────────────────────────────────────────────────────────────────────
# AWAITING_RETURN / CONFIRM_RETURN
# ──────────────────────────────────────────────────────────────────────────────


def test_awaiting_return_ignores_ticks_until_confirm() -> None:
    m = make(mode="fixed")
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    m.tick(True, 28.0)  # → AWAITING_RETURN
    assert m.tick(True, 29.0) == []
    assert m.tick(False, 30.0) == []
    assert m.snapshot(30.0).state is TimerState.AWAITING_RETURN
    events = m.command(Command.CONFIRM_RETURN, 31.0)
    assert types_of(events) == [TimerEventType.REST_ENDED, TimerEventType.WORK_STARTED]
    assert events[0].ended_by == ""
    assert events[0].duration_sec == pytest.approx(11.0)  # 31 - 20（牆鐘）
    snap = m.snapshot(31.0)
    assert snap.state is TimerState.WORKING
    assert snap.work_elapsed_sec == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# 跨週期不變量
# ──────────────────────────────────────────────────────────────────────────────


def test_work_ended_exactly_once_through_pending_cycle() -> None:
    m = make()
    all_events: list[TimerEvent] = []
    all_events += m.tick(True, 0.0)
    all_events += m.tick(True, 10.0)
    all_events += m.command(Command.START_REST, 20.0)
    all_events += m.tick(True, 25.0)
    all_events += m.tick(False, 30.0)  # WORK_ENDED + REST_STARTED
    all_events += m.tick(False, 38.0)  # 累計 8 滿額
    all_events += m.tick(True, 39.0)   # RETURN_PROMPT
    all_events += m.command(Command.CONFIRM_RETURN, 40.0)
    ended = [e for e in all_events if e.type is TimerEventType.WORK_ENDED]
    assert len(ended) == 1
    assert ended[0].ended_by == "rest"


def test_lock_flag_resets_on_new_work_cycle_after_confirm() -> None:
    m = make(interrupt_after=999.0)
    drive_to_reminding(m)
    events = m.tick(True, 190.0)  # 第一週期鎖屏
    assert TimerEventType.LOCK_REQUESTED in types_of(events)
    m.tick(False, 191.0)  # → RESTING
    m.tick(False, 199.0)  # 累計 8
    m.tick(True, 200.0)   # RETURN_PROMPT
    m.command(Command.CONFIRM_RETURN, 201.0)  # 新工作週期
    m.tick(True, 211.0)   # work 10 → REMINDING（錨點 211）
    events2 = m.tick(True, 392.0)  # dwell 181 → 第 3 階
    assert TimerEventType.LOCK_REQUESTED in types_of(events2)


# ──────────────────────────────────────────────────────────────────────────────
# snapshot 雜項
# ──────────────────────────────────────────────────────────────────────────────


def test_snapshot_remaining_and_reminder_active() -> None:
    m = make()
    snap0 = m.snapshot(0.0)
    assert snap0.state is TimerState.IDLE
    assert snap0.remaining_to_reminder_sec == 0.0
    assert snap0.reminder_active is False
    assert snap0.escalation_stage == -1
    assert snap0.pending_dwell_sec == 0.0
    m.tick(True, 0.0)
    m.tick(True, 4.0)
    assert m.snapshot(4.0).remaining_to_reminder_sec == pytest.approx(6.0)
    m.tick(False, 5.0)
    assert m.snapshot(7.0).away_elapsed_sec == pytest.approx(2.0)
    m.tick(True, 8.0)
    m.tick(True, 14.0)  # 4 + 6 = 10 → REMINDING
    snap = m.snapshot(14.0)
    assert snap.reminder_active is True
    assert snap.remaining_to_reminder_sec == 0.0


def test_overtime_accrues_in_reminding_and_zero_elsewhere() -> None:
    m = make()
    drive_to_reminding(m)
    assert m.snapshot(10.0).overtime_sec == 0.0
    m.tick(True, 13.0)
    assert m.snapshot(13.0).overtime_sec == pytest.approx(3.0)
    other = make()
    other.tick(True, 0.0)
    other.tick(True, 4.0)
    assert other.snapshot(4.0).overtime_sec == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# escalation_dwell_sec：snapshot 通用階梯 dwell（REST_PENDING / REMINDING 共用）
# ──────────────────────────────────────────────────────────────────────────────


def test_escalation_dwell_zero_without_active_ladder() -> None:
    m = make(apply_rem=False)
    assert m.snapshot(0.0).escalation_dwell_sec == 0.0  # IDLE
    drive_to_reminding(m)
    assert m.snapshot(15.0).escalation_dwell_sec == 0.0  # 無錨點（apply_rem=False）


def test_escalation_dwell_tracks_reminding_overtime_ladder() -> None:
    m = make()
    drive_to_reminding(m)  # 錨點 = 10
    m.tick(True, 33.0)
    assert m.snapshot(33.0).escalation_dwell_sec == pytest.approx(23.0)


def test_escalation_dwell_matches_pending_dwell_in_rest_pending() -> None:
    m = make()
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    m.tick(True, 33.0)
    snap = m.snapshot(33.0)
    assert snap.escalation_dwell_sec == pytest.approx(13.0)
    assert snap.escalation_dwell_sec == pytest.approx(snap.pending_dwell_sec)


# ──────────────────────────────────────────────────────────────────────────────
# spec §5「鎖屏後回來」：notify_unlocked → 階梯歸零重爬，同週期不再鎖屏
# ──────────────────────────────────────────────────────────────────────────────


def test_notify_unlocked_resets_ladder_without_second_lock_in_same_cycle() -> None:
    m = make()
    drive_to_reminding(m)
    m.command(Command.START_REST, 20.0)
    events = m.tick(True, 201.0)  # dwell 181 → 1..3 階＋LOCK_REQUESTED
    assert stages_of(events) == [1, 2, 3]
    assert TimerEventType.LOCK_REQUESTED in types_of(events)

    m.notify_unlocked(210.0)  # 解鎖回來：階梯歸零、自 stage 0 重爬

    snap = m.snapshot(210.0)
    assert snap.state is TimerState.REST_PENDING  # §10：視同仍在原狀態
    assert snap.escalation_stage == 0
    assert snap.pending_dwell_sec == pytest.approx(0.0)
    events2 = m.tick(True, 391.0)  # dwell 181 → 重新爬 1..3 階
    assert stages_of(events2) == [1, 2, 3]
    assert TimerEventType.LOCK_REQUESTED not in types_of(events2)  # 鎖屏單週期一次


def test_notify_unlocked_resets_reminding_ladder_too() -> None:
    m = make()
    drive_to_reminding(m)  # 錨點 = 10
    m.tick(True, 71.0)  # dwell 61 → 第 1 階
    assert m.snapshot(71.0).escalation_stage == 1

    m.notify_unlocked(80.0)

    assert m.snapshot(80.0).escalation_stage == 0
    assert TimerEventType.ESCALATED not in types_of(m.tick(True, 139.0))  # dwell 59
    assert stages_of(m.tick(True, 141.0)) == [1]  # 自 80 重計：dwell 61


def test_notify_unlocked_without_ladder_is_noop() -> None:
    m = make()
    m.tick(True, 0.0)  # WORKING，無階梯錨點
    m.notify_unlocked(5.0)
    snap = m.snapshot(5.0)
    assert snap.state is TimerState.WORKING
    assert snap.escalation_stage == -1
