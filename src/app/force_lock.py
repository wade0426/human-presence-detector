from __future__ import annotations

from src.config import ForceLockConfig
from src.types import TimerSnapshot, TimerState


class ForceLockPolicy:
    def __init__(self, config: ForceLockConfig) -> None:
        self._config = config
        self._fired = False
        self._threshold_sec = config.overtime_threshold_min * 60.0

    def observe(self, snap: TimerSnapshot) -> bool:
        if not self._config.enabled:
            return False

        if snap.state == TimerState.SUSPENDED:
            # 暫停期間凍結 _fired，避免暫停／恢復造成重複或漏觸發
            return False

        if self._config.trigger == "overtime":
            if snap.state != TimerState.REMINDING:
                self._fired = False
                return False
            if self._fired:
                return False
            if snap.overtime_sec >= self._threshold_sec:
                self._fired = True
                return True
            return False

        # trigger == "on_rest"
        if snap.state != TimerState.RESTING:
            self._fired = False
            return False
        if self._fired:
            return False
        self._fired = True
        return True
