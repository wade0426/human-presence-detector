from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TimerState(Enum):
    IDLE = "idle"
    WORKING = "working"
    AWAY = "away"
    REMINDING = "reminding"
    REST_PENDING = "rest_pending"
    RESTING = "resting"
    AWAITING_RETURN = "awaiting_return"
    SUSPENDED = "suspended"  # 僅 snapshot 對外呈現；內部為正交旗標


class TimerEventType(Enum):
    WORK_STARTED = "work_started"
    WORK_ENDED = "work_ended"            # ended_by: reset|rest|rest_pending|interrupted
    REMINDER_TRIGGERED = "reminder_triggered"
    REMINDER_REPEATED = "reminder_repeated"
    REST_PENDING_ENTERED = "rest_pending_entered"
    REST_PENDING_CANCELLED = "rest_pending_cancelled"
    ESCALATED = "escalated"              # stage 1..3，每階升級發一次
    LOCK_REQUESTED = "lock_requested"    # 隨 stage==3 發出，單一工作週期至多一次
    REST_STARTED = "rest_started"
    REST_ENDED = "rest_ended"            # ended_by: ""|interrupted
    REST_INTERRUPTED = "rest_interrupted"
    RETURN_PROMPT = "return_prompt"


class Command(Enum):
    START_REST = "start_rest"
    CANCEL_PENDING = "cancel_pending"
    CONFIRM_RETURN = "confirm_return"


@dataclass(frozen=True)
class TimerEvent:
    type: TimerEventType
    at: float
    duration_sec: float = 0.0
    ended_by: str = ""
    stage: int = -1


@dataclass(frozen=True)
class TimerSnapshot:
    state: TimerState
    work_elapsed_sec: float
    away_elapsed_sec: float
    remaining_to_reminder_sec: float
    reminder_active: bool
    rest_remaining_sec: float
    rest_elapsed_sec: float
    overtime_sec: float
    pending_dwell_sec: float    # REST_PENDING 滯留秒數（非該態為 0）
    escalation_stage: int       # 目前階段 0..3；無階梯情境為 -1
    # 階梯 dwell（秒）：REST_PENDING 滯留與 REMINDING 超時兩來源共用同一計算
    # （錨點起算、暫停凍結）；無階梯錨點時為 0。審查修正新增（quality review #8）。
    escalation_dwell_sec: float = 0.0


@dataclass(frozen=True)
class SessionRecord:            # 持久化型別（T4 store / T5 translator 共用）
    kind: str                   # work | rest
    start_ts: float             # = event.at - duration_sec
    end_ts: float
    duration_sec: float
    ended_by: str


@dataclass(frozen=True)
class LedgerEvent:
    ts: float
    type: str                   # TimerEventType.value
    payload: dict[str, object]
