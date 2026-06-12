"""資料驅動升級階梯：以連續滯留時長決定升級階段（純函式、無狀態）。"""

from __future__ import annotations


class EscalationPolicy:
    """升級階梯政策。

    輸入「連續滯留秒數」，輸出當前階段 0..3，並以 ``max_stage`` 封頂。
    本類別不保存任何呼叫間狀態；階段變化的偵測與事件發送由狀態機負責。
    """

    def __init__(self, stage_after_sec: tuple[float, float, float], max_stage: int) -> None:
        s1, s2, s3 = stage_after_sec
        if s1 <= 0:
            raise ValueError(f"stage_after_sec 必須為正數，收到 {stage_after_sec!r}")
        if not (s1 < s2 < s3):
            raise ValueError(f"stage_after_sec 必須嚴格遞增，收到 {stage_after_sec!r}")
        if not 0 <= max_stage <= 3:
            raise ValueError(f"max_stage 必須介於 0..3，收到 {max_stage!r}")
        self._thresholds: tuple[float, float, float] = (s1, s2, s3)
        self._max_stage = max_stage

    @property
    def max_stage(self) -> int:
        return self._max_stage

    def stage_for(self, dwell_sec: float) -> int:
        """dwell<s1→0；≥s1→1；≥s2→2；≥s3→3；回傳值以 max_stage 封頂。"""
        stage = 0
        for threshold in self._thresholds:
            if dwell_sec >= threshold:
                stage += 1
        return min(stage, self._max_stage)
