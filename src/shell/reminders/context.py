from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReminderContext:
    # §4.14: float — keep fractional minutes (e.g. 0.1 or 25.5) intact for countdowns.
    work_minutes: float
    media_path: str
    media_type: str
    sound_path: str
    work_elapsed_sec: float = 0.0  # actual continuous work seconds at reminder trigger
