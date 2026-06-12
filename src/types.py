"""共用基礎型別（capture / detection / presence 所需）。

計時器與提醒相關型別已遷移：TimerState/TimerEvent/TimerSnapshot 等見
``src/core/events.py``；ReminderContext 見 ``src/shell/reminders/context.py``。
"""

from __future__ import annotations

from dataclasses import dataclass

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
