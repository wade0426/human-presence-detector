from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


@dataclass(frozen=True)
class BBox:
    x: float
    y: float
    w: float
    h: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + (self.w / 2.0), self.y + (self.h / 2.0))


@dataclass(frozen=True)
class Detection:
    bbox: BBox
    confidence: float


@dataclass(frozen=True)
class Frame:
    image: np.ndarray
    width: int
    height: int
    timestamp: float


class TimerState(Enum):
    IDLE = "idle"
    WORKING = "working"
    AWAY = "away"
    REMINDING = "reminding"
    RESTING = "resting"
    AWAITING_RETURN = "awaiting_return"
    SUSPENDED = "suspended"


class RestCountMode(Enum):
    PRESENCE = "presence"
    FIXED = "fixed"


class TimerEventType(Enum):
    WORK_STARTED = "work_started"
    WORK_ENDED = "work_ended"
    REST_STARTED = "rest_started"
    REST_ENDED = "rest_ended"
    REMINDER_TRIGGERED = "reminder_triggered"
    REMINDER_REPEATED = "reminder_repeated"
    RETURN_PROMPT = "return_prompt"


@dataclass(frozen=True)
class TimerEvent:
    type: TimerEventType
    at: float
    duration_sec: float = 0.0
    ended_by: str = ""


@dataclass(frozen=True)
class TimerSnapshot:
    state: TimerState
    work_elapsed_sec: float
    away_elapsed_sec: float
    remaining_to_reminder_sec: float
    reminder_active: bool
    rest_remaining_sec: float = 0.0
    rest_elapsed_sec: float = 0.0
    overtime_sec: float = 0.0  # REMINDING: max(0, work_elapsed - work_threshold)


@dataclass(frozen=True)
class ReminderContext:
    work_minutes: int
    media_path: str
    media_type: str
    sound_path: str
    work_elapsed_sec: float = 0.0  # actual continuous work seconds at reminder trigger
