from __future__ import annotations

from dataclasses import dataclass

from src.types import TimerSnapshot


@dataclass(frozen=True)
class TodayWorkDisplay:
    """今日工作顯示值與是否需重抓 DB 的旗標。"""

    display_seconds: int  # = base + in_progress（四捨五入）
    base_refresh_needed: bool  # in_progress 由 >0 轉 0 時為 True，需重抓 DB


class TodayWorkModel:
    """合併「資料庫已完成工作秒數（base）」與「目前進行中工作秒數（in-progress）」。

    對應 FR-4 的「即時累加且不重複計算」。純計算類別，不存取外部資源，不丟例外。
    """

    def __init__(self) -> None:
        self._base: int = 0
        self._prev_in_progress: float = 0.0

    def set_base(self, work_seconds: int) -> None:
        """以 today_summary().work_seconds 設定基準（已完成 work session 總和）。"""
        self._base = work_seconds

    def observe(self, snapshot: TimerSnapshot) -> TodayWorkDisplay:
        """輸入最新快照，回傳顯示值與是否需重抓 DB。

        - in_progress = snapshot.work_elapsed_sec
        - display_seconds = round(base + in_progress)
        - base_refresh_needed = (prev_in_progress > 0) and (in_progress == 0)
        """
        in_progress: float = snapshot.work_elapsed_sec
        display_seconds: int = round(self._base + in_progress)
        base_refresh_needed: bool = (self._prev_in_progress > 0) and (in_progress == 0)
        self._prev_in_progress = in_progress
        return TodayWorkDisplay(
            display_seconds=display_seconds,
            base_refresh_needed=base_refresh_needed,
        )
