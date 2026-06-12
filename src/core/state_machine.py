"""等待離席休息流程狀態機（spec §4，純邏輯、零 Qt）。

設計重點：
- tick / command 為唯二輸入；事件以 ``list[TimerEvent]`` 回傳，由外殼轉訊號。
- 每個狀態各有 ``_tick_<state>`` handler，由轉移表字典分派（無大型 if/elif）。
- 升級階梯（spec §5）：REST_PENDING 滯留與 REMINDING 超時（僅
  ``apply_to_reminding``）共用同一政策但各自獨立計時；進入 REST_PENDING 時
  歸零重計（按鈕＝善意）、離開觸發狀態歸零；到第 3 階且本工作週期未鎖過
  才加發 LOCK_REQUESTED（單一工作週期至多一次）。
- 記帳（spec §6）：``pending_accounting="work"`` 時 REST_PENDING 不結算、
  工作與超時續計，真正離席才 WORK_ENDED(rest)；``"none"`` 時按鈕當下
  WORK_ENDED(rest_pending) 結算並凍結工作累計，離席不再發。

暫停凍結契約（spec §4.3，自舊 TimerEngine 移植）：
  pause(now)  : 記錄 _pause_started_at；不動 _last_t 與任何累計值。
  tick()      : 暫停中一律回 []，不累計任何 dt。
  resume(now) : _last_t = now（下個 tick dt ≈ 0）；絕對時間戳平移 pause
                時長並 clamp 至 now——暫停中下達指令所寫入的時間戳視同
                於 resume 當下寫入（§4.4）。
  指令        : 暫停中直接生效；resume 不還原狀態（§4.1）。暫停中
                confirm 的 rest_duration 以 min(now, pause_started_at) 計。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from src.core.events import (
    Command,
    TimerEvent,
    TimerEventType,
    TimerSnapshot,
    TimerState,
)

_REST_COUNT_MODES = ("presence", "fixed")
_PENDING_ACCOUNTING_MODES = ("work", "none")
_INTERRUPT_BEHAVIORS = ("remind", "new_work")

_LOCK_STAGE = 3


@dataclass(frozen=True)
class MachineConfig:
    work_threshold_sec: float
    reset_threshold_sec: float
    required_rest_sec: float
    repeat_interval_sec: float
    rest_count_mode: str = "presence"      # presence | fixed
    pending_accounting: str = "work"       # work | none
    interrupt_behavior: str = "remind"     # remind | new_work
    rest_interrupt_after_sec: float = 120.0
    apply_to_reminding: bool = True

    def __post_init__(self) -> None:
        if self.rest_count_mode not in _REST_COUNT_MODES:
            raise ValueError(f"unknown rest_count_mode: {self.rest_count_mode!r}")
        if self.pending_accounting not in _PENDING_ACCOUNTING_MODES:
            raise ValueError(f"unknown pending_accounting: {self.pending_accounting!r}")
        if self.interrupt_behavior not in _INTERRUPT_BEHAVIORS:
            raise ValueError(f"unknown interrupt_behavior: {self.interrupt_behavior!r}")


class EscalationLike(Protocol):
    @property
    def max_stage(self) -> int: ...

    def stage_for(self, dwell_sec: float) -> int: ...


_TickHandler = Callable[[bool, float, float], list[TimerEvent]]


class RestFlowMachine:
    def __init__(self, cfg: MachineConfig, escalation: EscalationLike) -> None:
        self._cfg = cfg
        self._escalation = escalation

        self._state = TimerState.IDLE
        self._work_elapsed = 0.0
        self._last_t: float | None = None
        self._away_since: float | None = None
        self._implicit_rest_since: float | None = None  # reset 後的隱式休息起點
        self._reminder_last_t: float | None = None
        self._rest_started_at: float | None = None      # 休息起點（牆鐘）
        self._rest_accumulated = 0.0                    # presence 模式離席累計
        self._present_since: float | None = None        # RESTING 連續在席起點
        self._escalation_anchor: float | None = None    # 階梯 dwell 起點
        self._escalation_stage = 0
        self._lock_fired_this_cycle = False
        self._paused = False
        self._pause_started_at: float | None = None

        self._tick_handlers: dict[TimerState, _TickHandler] = {
            TimerState.IDLE: self._tick_idle,
            TimerState.WORKING: self._tick_working,
            TimerState.AWAY: self._tick_away,
            TimerState.REMINDING: self._tick_reminding,
            TimerState.REST_PENDING: self._tick_rest_pending,
            TimerState.RESTING: self._tick_resting,
            TimerState.AWAITING_RETURN: self._tick_awaiting_return,
        }

    # ── 輸入：tick ───────────────────────────────────────────────────────────

    def tick(self, present: bool, now: float) -> list[TimerEvent]:
        if self._paused:
            return []
        if self._last_t is not None and now < self._last_t:
            raise ValueError(f"tick time went backwards: now={now} < last={self._last_t}")
        dt = 0.0 if self._last_t is None else now - self._last_t
        self._last_t = now
        return self._tick_handlers[self._state](present, now, dt)

    # ── per-state tick handlers（spec §4.1 轉移表逐列）────────────────────────

    def _tick_idle(self, present: bool, now: float, dt: float) -> list[TimerEvent]:
        if not present:
            return []
        events: list[TimerEvent] = []
        if self._implicit_rest_since is not None:
            events.append(
                self._event(
                    TimerEventType.REST_ENDED,
                    now,
                    duration_sec=max(0.0, now - self._implicit_rest_since),
                )
            )
            self._implicit_rest_since = None
        self._state = TimerState.WORKING
        self._work_elapsed = 0.0
        self._lock_fired_this_cycle = False
        events.append(self._event(TimerEventType.WORK_STARTED, now))
        return events

    def _tick_working(self, present: bool, now: float, dt: float) -> list[TimerEvent]:
        if present:
            self._work_elapsed += dt
            if self._work_elapsed >= self._cfg.work_threshold_sec:
                return [self._enter_reminding(now)]
            return []
        self._state = TimerState.AWAY
        self._away_since = now
        return []

    def _tick_away(self, present: bool, now: float, dt: float) -> list[TimerEvent]:
        if present:
            self._state = TimerState.WORKING
            self._away_since = None
            return []
        if (
            self._away_since is not None
            and (now - self._away_since) >= self._cfg.reset_threshold_sec
        ):
            event = self._event(
                TimerEventType.WORK_ENDED,
                now,
                duration_sec=self._work_elapsed,
                ended_by="reset",
            )
            self._implicit_rest_since = self._away_since  # 隱式休息自離席起追蹤
            self._state = TimerState.IDLE
            self._work_elapsed = 0.0
            self._away_since = None
            return [event]
        return []

    def _tick_reminding(self, present: bool, now: float, dt: float) -> list[TimerEvent]:
        if not present:
            return self._begin_rest(now, close_session=True)
        events: list[TimerEvent] = []
        self._work_elapsed += dt
        if (
            self._reminder_last_t is not None
            and (now - self._reminder_last_t) >= self._cfg.repeat_interval_sec
        ):
            self._reminder_last_t = now
            events.append(self._event(TimerEventType.REMINDER_REPEATED, now))
        events.extend(self._escalate(now))  # 錨點僅在 apply_to_reminding 時設置
        return events

    def _tick_rest_pending(self, present: bool, now: float, dt: float) -> list[TimerEvent]:
        if not present:
            # work 模式此刻才結算；none 模式已於按鈕當下結算（spec §6）
            close = self._cfg.pending_accounting == "work"
            return self._begin_rest(now, close_session=close)
        if self._cfg.pending_accounting == "work":
            self._work_elapsed += dt  # 工作與超時續計
        return self._escalate(now)

    def _tick_resting(self, present: bool, now: float, dt: float) -> list[TimerEvent]:
        if self._cfg.rest_count_mode == "fixed":
            return self._tick_resting_fixed(present, now)
        return self._tick_resting_presence(present, now, dt)

    def _tick_resting_fixed(self, present: bool, now: float) -> list[TimerEvent]:
        if (
            present
            and self._rest_started_at is not None
            and (now - self._rest_started_at) >= self._cfg.required_rest_sec
        ):
            return [self._enter_awaiting_return(now)]
        return []

    def _tick_resting_presence(self, present: bool, now: float, dt: float) -> list[TimerEvent]:
        if not present:
            self._rest_accumulated += dt
            self._present_since = None
            return []
        if self._rest_accumulated >= self._cfg.required_rest_sec:
            return [self._enter_awaiting_return(now)]
        if self._present_since is None:
            self._present_since = now
            return []
        if (now - self._present_since) >= self._cfg.rest_interrupt_after_sec:
            return self._interrupt_rest(now)
        return []

    def _tick_awaiting_return(self, present: bool, now: float, dt: float) -> list[TimerEvent]:
        return []  # 等待 CONFIRM_RETURN，tick 不改變狀態

    # ── 輸入：command ────────────────────────────────────────────────────────

    def command(self, cmd: Command, now: float) -> list[TimerEvent]:
        if cmd is Command.START_REST:
            return self._cmd_start_rest(now)
        if cmd is Command.CANCEL_PENDING:
            return self._cmd_cancel_pending(now)
        if cmd is Command.CONFIRM_RETURN:
            return self._cmd_confirm_return(now)
        raise ValueError(f"unknown command: {cmd!r}")

    def _cmd_start_rest(self, now: float) -> list[TimerEvent]:
        if self._state is not TimerState.REMINDING:
            return []
        self._last_t = now
        if self._cfg.rest_count_mode == "fixed":
            # fixed 模式直進 RESTING（spec §4.1）
            return self._begin_rest(now, close_session=True)
        events: list[TimerEvent] = []
        if self._cfg.pending_accounting == "none":
            # 按鈕當下結算；其後滯留為灰色時段，工作累計凍結（spec §6）
            events.append(
                self._event(
                    TimerEventType.WORK_ENDED,
                    now,
                    duration_sec=self._work_elapsed,
                    ended_by="rest_pending",
                )
            )
        self._state = TimerState.REST_PENDING
        self._reminder_last_t = None
        self._escalation_anchor = now  # 階梯歸零重計（按鈕＝善意）
        self._escalation_stage = 0
        events.append(self._event(TimerEventType.REST_PENDING_ENTERED, now))
        return events

    def _cmd_cancel_pending(self, now: float) -> list[TimerEvent]:
        if self._state is not TimerState.REST_PENDING:
            return []
        self._last_t = now
        events = [self._event(TimerEventType.REST_PENDING_CANCELLED, now)]
        self._state = TimerState.REMINDING
        self._reminder_last_t = now
        self._escalation_anchor = now if self._cfg.apply_to_reminding else None
        self._escalation_stage = 0
        if self._cfg.pending_accounting == "none":
            # 進 pending 時已結算 → 自取消起開新 session（灰色時段不計工作）
            self._work_elapsed = 0.0
            events.append(self._event(TimerEventType.WORK_STARTED, now))
        return events

    def _cmd_confirm_return(self, now: float) -> list[TimerEvent]:
        if self._state is not TimerState.AWAITING_RETURN:
            return []
        # 暫停中時間凍結於 _pause_started_at——暫停期間不得計入休息時長
        effective_now = now
        if self._paused and self._pause_started_at is not None:
            effective_now = min(now, self._pause_started_at)
        rest_duration = 0.0
        if self._rest_started_at is not None:
            rest_duration = max(0.0, effective_now - self._rest_started_at)
        events = [
            self._event(TimerEventType.REST_ENDED, now, duration_sec=rest_duration),
            self._event(TimerEventType.WORK_STARTED, now),
        ]
        self._state = TimerState.WORKING
        self._work_elapsed = 0.0
        self._lock_fired_this_cycle = False
        self._last_t = now
        self._rest_started_at = None
        self._rest_accumulated = 0.0
        self._present_since = None
        return events

    # ── 暫停 / 恢復（凍結契約見模組 docstring）───────────────────────────────

    def pause(self, now: float) -> None:
        if not self._paused:
            self._paused = True
            self._pause_started_at = now
            # 刻意不動 _last_t：resume 會重設基準，暫停期間不產生 dt。

    def resume(self, now: float) -> None:
        if not self._paused:
            return
        self._paused = False
        self._last_t = now  # 下個 tick dt ≈ 0，不回填暫停時長
        pause_duration = 0.0
        if self._pause_started_at is not None:
            pause_duration = max(0.0, now - self._pause_started_at)
        self._pause_started_at = None
        if pause_duration <= 0.0:
            return
        self._away_since = self._shifted(self._away_since, pause_duration, now)
        self._implicit_rest_since = self._shifted(self._implicit_rest_since, pause_duration, now)
        self._reminder_last_t = self._shifted(self._reminder_last_t, pause_duration, now)
        self._rest_started_at = self._shifted(self._rest_started_at, pause_duration, now)
        self._present_since = self._shifted(self._present_since, pause_duration, now)
        self._escalation_anchor = self._shifted(self._escalation_anchor, pause_duration, now)

    @staticmethod
    def _shifted(timestamp: float | None, pause_duration: float, now: float) -> float | None:
        """絕對時間戳平移 pause 時長並 clamp 至 now（§4.4）。

        clamp：暫停期間由指令寫入的時間戳（如 start_rest 的休息起點）
        視同於 resume 當下寫入——暫停中沒有時間流逝。
        """
        if timestamp is None:
            return None
        return min(timestamp + pause_duration, now)

    # ── 解鎖回來（spec §5「鎖屏後回來」＋ §10）──────────────────────────────

    def notify_unlocked(self, now: float) -> None:
        """工作階段解鎖：階梯歸零重計，狀態不變（§10：視同仍在原狀態）。

        僅在階梯計時中（REST_PENDING 滯留或 REMINDING 超時）生效；
        ``_lock_fired_this_cycle`` 刻意保留——鎖屏每工作週期至多一次
        （spec §5），解鎖後階梯自 0 重爬、到第 3 階不再加發 LOCK_REQUESTED。
        """
        if self._escalation_anchor is None:
            return
        self._escalation_anchor = now
        self._escalation_stage = 0

    # ── snapshot ─────────────────────────────────────────────────────────────

    def snapshot(self, now: float) -> TimerSnapshot:
        # 暫停中以暫停起點為有效時間，凍結所有由絕對時間戳推導的欄位
        effective_now = now
        if self._paused and self._pause_started_at is not None:
            effective_now = min(now, self._pause_started_at)

        state = TimerState.SUSPENDED if self._paused else self._state

        remaining = (
            max(0.0, self._cfg.work_threshold_sec - self._work_elapsed)
            if self._state is TimerState.WORKING
            else 0.0
        )

        away_elapsed = 0.0
        if self._away_since is not None:
            away_elapsed = max(0.0, effective_now - self._away_since)

        rest_remaining = 0.0
        rest_elapsed = 0.0
        if self._state is TimerState.RESTING:
            if self._cfg.rest_count_mode == "fixed" and self._rest_started_at is not None:
                rest_remaining = max(
                    0.0, self._cfg.required_rest_sec - (effective_now - self._rest_started_at)
                )
            else:
                rest_elapsed = self._rest_accumulated

        # REMINDING 超時；REST_PENDING（work 記帳）超時續計（spec §6）
        overtime = 0.0
        if self._state in (TimerState.REMINDING, TimerState.REST_PENDING):
            overtime = max(0.0, self._work_elapsed - self._cfg.work_threshold_sec)

        escalation_dwell = 0.0
        if self._escalation_anchor is not None:
            escalation_dwell = max(0.0, effective_now - self._escalation_anchor)

        pending_dwell = (
            escalation_dwell if self._state is TimerState.REST_PENDING else 0.0
        )

        stage = self._escalation_stage if self._escalation_anchor is not None else -1

        return TimerSnapshot(
            state=state,
            work_elapsed_sec=self._work_elapsed,
            away_elapsed_sec=away_elapsed,
            remaining_to_reminder_sec=remaining,
            reminder_active=self._state is TimerState.REMINDING,
            rest_remaining_sec=rest_remaining,
            rest_elapsed_sec=rest_elapsed,
            overtime_sec=overtime,
            pending_dwell_sec=pending_dwell,
            escalation_stage=stage,
            escalation_dwell_sec=escalation_dwell,
        )

    # ── 內部轉移輔助 ─────────────────────────────────────────────────────────

    def _enter_reminding(self, now: float) -> TimerEvent:
        self._state = TimerState.REMINDING
        self._reminder_last_t = now
        self._away_since = None
        self._escalation_anchor = now if self._cfg.apply_to_reminding else None
        self._escalation_stage = 0
        return self._event(TimerEventType.REMINDER_TRIGGERED, now)

    def _begin_rest(self, now: float, *, close_session: bool) -> list[TimerEvent]:
        events: list[TimerEvent] = []
        if close_session:
            events.append(
                self._event(
                    TimerEventType.WORK_ENDED,
                    now,
                    duration_sec=self._work_elapsed,
                    ended_by="rest",
                )
            )
        self._state = TimerState.RESTING
        self._work_elapsed = 0.0
        self._rest_started_at = now
        self._rest_accumulated = 0.0
        self._present_since = None
        self._away_since = None
        self._reminder_last_t = None
        self._escalation_anchor = None  # 離開觸發狀態 → 階梯歸零
        self._escalation_stage = 0
        events.append(self._event(TimerEventType.REST_STARTED, now))
        return events

    def _enter_awaiting_return(self, now: float) -> TimerEvent:
        self._state = TimerState.AWAITING_RETURN
        self._present_since = None
        return self._event(TimerEventType.RETURN_PROMPT, now)

    def _interrupt_rest(self, now: float) -> list[TimerEvent]:
        """休息中斷（spec §4.2，presence 限定）：結算中斷休息、開新工作 session。"""
        seated_sec = 0.0 if self._present_since is None else now - self._present_since
        events = [
            self._event(
                TimerEventType.REST_ENDED,
                now,
                duration_sec=self._rest_accumulated,
                ended_by="interrupted",
            ),
            self._event(
                TimerEventType.REST_INTERRUPTED,
                now,
                duration_sec=self._rest_accumulated,
            ),
        ]
        self._rest_started_at = None
        self._rest_accumulated = 0.0
        self._present_since = None
        self._state = TimerState.WORKING
        self._work_elapsed = seated_sec  # 自「已連續在席時長」起算
        self._lock_fired_this_cycle = False
        events.append(self._event(TimerEventType.WORK_STARTED, now))
        if self._cfg.interrupt_behavior == "remind":
            events.append(self._enter_reminding(now))  # 你還欠休息 → 直接施壓
        return events

    def _escalate(self, now: float) -> list[TimerEvent]:
        """依滯留時長升階；跨多階時每階各發一次 ESCALATED（spec §5）。"""
        if self._escalation_anchor is None:
            return []
        target = self._escalation.stage_for(now - self._escalation_anchor)
        events: list[TimerEvent] = []
        while self._escalation_stage < target:
            self._escalation_stage += 1
            events.append(
                self._event(TimerEventType.ESCALATED, now, stage=self._escalation_stage)
            )
            if self._escalation_stage == _LOCK_STAGE and not self._lock_fired_this_cycle:
                self._lock_fired_this_cycle = True
                events.append(self._event(TimerEventType.LOCK_REQUESTED, now, stage=_LOCK_STAGE))
        return events

    @staticmethod
    def _event(
        event_type: TimerEventType,
        at: float,
        *,
        duration_sec: float = 0.0,
        ended_by: str = "",
        stage: int = -1,
    ) -> TimerEvent:
        return TimerEvent(
            type=event_type,
            at=at,
            duration_sec=duration_sec,
            ended_by=ended_by,
            stage=stage,
        )
