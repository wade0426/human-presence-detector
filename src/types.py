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
    PAUSED = "paused"
    REMINDING = "reminding"


class ResetMode(Enum):
    DETECTION = "detection"
    DISMISS = "dismiss"
    SNOOZE = "snooze"


class TimerEventType(Enum):
    WORK_STARTED = "work_started"
    WORK_ENDED = "work_ended"
    REST_ENDED = "rest_ended"
    REMINDER_TRIGGERED = "reminder_triggered"
    REMINDER_REPEATED = "reminder_repeated"


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


@dataclass(frozen=True)
class ReminderContext:
    work_minutes: int
    media_path: str
    media_type: str
    sound_path: str
    reset_mode: str = "detection"
    snooze_minutes: int = 5
