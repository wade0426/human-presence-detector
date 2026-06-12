"""暫停凍結契約（spec §4.3；自舊 tests/test_timer_engine.py 移植到新 API）。

契約：
- 暫停中 tick 一律回 []，所有累計凍結。
- 指令在暫停中直接生效，resume 不還原狀態（§4.1）。
- 絕對時間戳於 resume 平移 pause 時長並 clamp 至 now（§4.4）。
- 暫停中 confirm 的 rest_duration 以 min(now, pause_started_at) 計。
- REST_PENDING 滯留與 REMINDING 超時的階梯 dwell 同樣凍結。
"""

from __future__ import annotations

import pytest

from src.core.events import Command, TimerEvent, TimerEventType, TimerState
from src.core.state_machine import MachineConfig, RestFlowMachine


class StubEscalation:
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
    *,
    work: float = 10.0,
    reset: float = 6.0,
    rest: float = 8.0,
    repeat: float = 12.0,
    acc: str = "work",
    intr: str = "remind",
    apply_rem: bool = True,
    interrupt_after: float = 120.0,
) -> RestFlowMachine:
    cfg = MachineConfig(
        work_threshold_sec=work,
        reset_threshold_sec=reset,
        required_rest_sec=rest,
        repeat_interval_sec=repeat,
        rest_count_mode=mode,
        pending_accounting=acc,
        interrupt_behavior=intr,
        rest_interrupt_after_sec=interrupt_after,
        apply_to_reminding=apply_rem,
    )
    return RestFlowMachine(cfg, StubEscalation())


def types_of(events: list[TimerEvent]) -> list[TimerEventType]:
    return [e.type for e in events]


def stages_of(events: list[TimerEvent]) -> list[int]:
    return [e.stage for e in events if e.type is TimerEventType.ESCALATED]


# ──────────────────────────────────────────────────────────────────────────────
# 基本凍結：tick 無效、計數不動、resume 後 dt ≈ 0
# ──────────────────────────────────────────────────────────────────────────────


def test_paused_tick_returns_empty_and_counters_freeze() -> None:
    m = make(work=100.0)
    m.tick(True, 0.0)
    m.tick(True, 5.0)  # work_elapsed = 5
    m.pause(5.0)
    assert m.snapshot(30.0).state is TimerState.SUSPENDED
    assert m.tick(True, 30.0) == []
    assert m.tick(True, 99.0) == []
    assert m.snapshot(99.0).work_elapsed_sec == pytest.approx(5.0)


def test_resume_first_tick_has_near_zero_dt() -> None:
    m = make(work=100.0)
    m.tick(True, 0.0)
    m.tick(True, 5.0)
    m.pause(5.0)
    m.tick(True, 55.0)  # 暫停中無效
    m.resume(100.0)
    assert m.snapshot(100.0).state is TimerState.WORKING
    m.tick(True, 100.1)
    assert m.snapshot(100.1).work_elapsed_sec == pytest.approx(5.1, abs=0.01)


def test_overtime_frozen_during_pause() -> None:
    m = make()
    m.tick(True, 0.0)
    m.tick(True, 10.0)  # → REMINDING
    m.tick(True, 13.0)  # overtime = 3
    assert m.snapshot(13.0).overtime_sec == pytest.approx(3.0)
    m.pause(13.0)
    m.tick(True, 60.0)
    m.tick(True, 90.0)
    snap = m.snapshot(90.0)
    assert snap.state is TimerState.SUSPENDED
    assert snap.overtime_sec == pytest.approx(3.0)


def test_pause_idempotent_and_resume_without_pause_is_noop() -> None:
    m = make(work=100.0)
    m.tick(True, 0.0)
    m.tick(True, 4.0)
    m.resume(5.0)  # 未暫停 → no-op
    m.tick(True, 6.0)
    assert m.snapshot(6.0).work_elapsed_sec == pytest.approx(6.0)
    m.pause(7.0)
    m.pause(50.0)  # 第二次 pause 不得重設暫停起點
    m.resume(107.0)
    m.tick(True, 107.5)
    assert m.snapshot(107.5).work_elapsed_sec == pytest.approx(6.5, abs=0.01)


def test_paused_snapshot_freezes_away_elapsed() -> None:
    m = make(work=100.0, reset=50.0)
    m.tick(True, 0.0)
    m.tick(False, 5.0)  # → AWAY（自 5 起）
    m.pause(8.0)
    snap = m.snapshot(30.0)
    assert snap.state is TimerState.SUSPENDED
    assert snap.away_elapsed_sec == pytest.approx(3.0)


# ──────────────────────────────────────────────────────────────────────────────
# §4.1：暫停中下達指令直接生效，resume 不得以過期狀態覆寫
# ──────────────────────────────────────────────────────────────────────────────


def test_confirm_return_during_pause_survives_resume() -> None:
    m = make(mode="fixed", rest=5.0)
    m.tick(True, 0.0)
    m.tick(True, 10.0)  # → REMINDING
    m.command(Command.START_REST, 10.0)  # → RESTING（自 10 起）
    m.tick(True, 15.0)  # 滿額 → AWAITING_RETURN
    assert m.snapshot(15.0).state is TimerState.AWAITING_RETURN
    m.pause(16.0)
    events = m.command(Command.CONFIRM_RETURN, 20.0)
    assert types_of(events) == [TimerEventType.REST_ENDED, TimerEventType.WORK_STARTED]
    # 暫停期間（16→20）不得計入休息：實際休息 = 16 - 10 = 6 秒
    assert events[0].duration_sec == pytest.approx(6.0)
    m.resume(30.0)
    assert m.snapshot(30.0).state is TimerState.WORKING
    assert m.tick(True, 30.1) == []  # 不得重複發事件
    assert m.command(Command.CONFIRM_RETURN, 31.0) == []  # 已是 WORKING → no-op


def test_start_rest_during_pause_survives_resume_fixed() -> None:
    m = make(mode="fixed")
    m.tick(True, 0.0)
    m.tick(True, 10.0)  # → REMINDING
    m.pause(11.0)
    events = m.command(Command.START_REST, 12.0)
    assert types_of(events) == [TimerEventType.WORK_ENDED, TimerEventType.REST_STARTED]
    m.resume(60.0)
    assert m.snapshot(60.0).state is TimerState.RESTING
    follow = m.tick(False, 60.1)
    assert TimerEventType.WORK_ENDED not in types_of(follow)
    assert TimerEventType.REST_STARTED not in types_of(follow)


def test_start_rest_during_pause_enters_pending_presence() -> None:
    m = make()  # presence
    m.tick(True, 0.0)
    m.tick(True, 10.0)  # → REMINDING
    m.pause(11.0)
    events = m.command(Command.START_REST, 12.0)
    assert types_of(events) == [TimerEventType.REST_PENDING_ENTERED]
    assert m.tick(True, 50.0) == []  # 仍在暫停
    m.resume(100.0)
    assert m.snapshot(100.0).state is TimerState.REST_PENDING
    # 滯留自 resume 起算（錨點 clamp 至 100）：159 → dwell 59 無升級；160 → 第 1 階
    assert TimerEventType.ESCALATED not in types_of(m.tick(True, 159.0))
    assert stages_of(m.tick(True, 160.0)) == [1]


def test_cancel_pending_during_pause_survives_resume() -> None:
    m = make()
    m.tick(True, 0.0)
    m.tick(True, 10.0)
    m.command(Command.START_REST, 20.0)
    m.pause(30.0)
    events = m.command(Command.CANCEL_PENDING, 35.0)
    assert types_of(events) == [TimerEventType.REST_PENDING_CANCELLED]
    assert m.tick(True, 40.0) == []  # 仍在暫停
    m.resume(60.0)
    assert m.snapshot(60.0).state is TimerState.REMINDING


# ──────────────────────────────────────────────────────────────────────────────
# §4.4：絕對時間戳於 resume 平移並 clamp
# ──────────────────────────────────────────────────────────────────────────────


def test_pause_during_away_does_not_trigger_reset_on_resume() -> None:
    m = make(work=100.0, reset=5.0)
    m.tick(True, 0.0)
    m.tick(True, 4.0)
    m.tick(False, 5.0)  # → AWAY（自 5 起）
    m.tick(False, 6.0)  # 離席 1 秒
    m.pause(6.0)
    m.resume(60.0)  # 暫停 54 秒（遠超 reset=5）
    events = m.tick(False, 60.5)  # 等效離席僅 1.5 秒
    assert TimerEventType.WORK_ENDED not in types_of(events)
    assert m.snapshot(60.5).state is TimerState.AWAY
    events2 = m.tick(False, 64.5)  # 等效離席 5.5 秒 → 重置
    assert TimerEventType.WORK_ENDED in types_of(events2)
    assert m.snapshot(64.5).state is TimerState.IDLE


def test_pause_during_reminding_does_not_repeat_reminder_on_resume() -> None:
    m = make(repeat=3.0)
    m.tick(True, 0.0)
    m.tick(True, 10.0)  # → REMINDING（reminder_last = 10）
    m.tick(True, 11.0)
    m.pause(11.0)
    m.resume(60.0)  # 暫停 49 秒（遠超 repeat=3）
    events = m.tick(True, 60.5)  # 等效僅過 1.5 秒
    assert TimerEventType.REMINDER_REPEATED not in types_of(events)
    events2 = m.tick(True, 62.5)  # 等效過滿 repeat → 可重發
    assert types_of(events2) == [TimerEventType.REMINDER_REPEATED]


def test_fixed_rest_not_credited_by_pause_and_duration_excludes_pause() -> None:
    m = make(mode="fixed", rest=5.0)
    m.tick(True, 0.0)
    m.tick(True, 10.0)
    m.command(Command.START_REST, 10.0)  # RESTING 自 10 起
    m.tick(True, 12.0)  # 已休息 2 秒
    m.pause(12.0)
    m.resume(112.0)  # 暫停 100 秒
    events = m.tick(True, 112.1)  # 等效僅休息 2.1 秒 < 5
    assert TimerEventType.RETURN_PROMPT not in types_of(events)
    assert m.snapshot(112.1).state is TimerState.RESTING
    events2 = m.tick(True, 115.5)  # rest_started 平移至 110 → 滿足
    assert TimerEventType.RETURN_PROMPT in types_of(events2)
    events3 = m.command(Command.CONFIRM_RETURN, 116.0)
    assert events3[0].type is TimerEventType.REST_ENDED
    assert events3[0].duration_sec == pytest.approx(6.0)  # 116 - 110，不含暫停


def test_start_rest_during_pause_counts_rest_from_resume() -> None:
    m = make(mode="fixed", rest=5.0)
    m.tick(True, 0.0)
    m.tick(True, 10.0)
    m.pause(11.0)
    m.command(Command.START_REST, 50.0)  # 暫停期間開始休息
    m.resume(100.0)  # rest_started clamp 至 100
    events = m.tick(True, 103.0)  # 僅休息 3 秒 → 未滿足
    assert TimerEventType.RETURN_PROMPT not in types_of(events)
    assert m.snapshot(103.0).state is TimerState.RESTING
    events2 = m.tick(True, 105.5)  # 休息 5.5 秒 → 滿足
    assert TimerEventType.RETURN_PROMPT in types_of(events2)


# ──────────────────────────────────────────────────────────────────────────────
# 階梯 dwell 凍結（REST_PENDING 滯留與 REMINDING 超時）
# ──────────────────────────────────────────────────────────────────────────────


def test_pending_dwell_frozen_during_pause() -> None:
    m = make()
    m.tick(True, 0.0)
    m.tick(True, 10.0)
    m.command(Command.START_REST, 20.0)  # pending 自 20 起
    m.tick(True, 50.0)  # dwell 30
    m.pause(50.0)
    snap = m.snapshot(140.0)
    assert snap.state is TimerState.SUSPENDED
    assert snap.pending_dwell_sec == pytest.approx(30.0)  # 凍結
    m.resume(150.0)  # 錨點平移：min(20+100, 150) = 120
    assert TimerEventType.ESCALATED not in types_of(m.tick(True, 179.0))  # dwell 59
    assert stages_of(m.tick(True, 181.0)) == [1]  # dwell 61 → 第 1 階


def test_reminding_escalation_dwell_frozen_during_pause() -> None:
    m = make()
    m.tick(True, 0.0)
    m.tick(True, 10.0)  # → REMINDING（錨點 10）
    m.tick(True, 40.0)  # dwell 30
    m.pause(40.0)
    m.resume(140.0)  # 錨點平移：min(10+100, 140) = 110
    assert TimerEventType.ESCALATED not in types_of(m.tick(True, 169.0))  # dwell 59
    assert stages_of(m.tick(True, 171.0)) == [1]  # dwell 61
