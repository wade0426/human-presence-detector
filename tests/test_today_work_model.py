from __future__ import annotations

import dataclasses

import pytest

from src.today_work_model import TodayWorkDisplay, TodayWorkModel
from src.types import TimerSnapshot, TimerState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snap(work_elapsed: float, state: TimerState = TimerState.WORKING) -> TimerSnapshot:
    """Build a minimal TimerSnapshot with the given work_elapsed_sec."""
    return TimerSnapshot(
        state=state,
        work_elapsed_sec=work_elapsed,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTodayWorkModel:
    def test_base_plus_in_progress(self) -> None:
        """set_base(600) + 快照 work_elapsed=30 → display_seconds=630."""
        model = TodayWorkModel()
        model.set_base(600)
        result = model.observe(_snap(30.0))
        assert result.display_seconds == 630
        assert result.base_refresh_needed is False

    def test_display_increases_with_work_elapsed(self) -> None:
        """連續快照 work_elapsed 30→60，display_seconds 遞增，base_refresh_needed=False."""
        model = TodayWorkModel()
        model.set_base(0)

        r1 = model.observe(_snap(30.0))
        assert r1.display_seconds == 30
        assert r1.base_refresh_needed is False

        r2 = model.observe(_snap(60.0))
        assert r2.display_seconds == 60
        assert r2.base_refresh_needed is False
        assert r2.display_seconds > r1.display_seconds

    def test_base_refresh_needed_when_work_ends(self) -> None:
        """work_elapsed 由 60→0（工作結束）→ base_refresh_needed=True."""
        model = TodayWorkModel()
        model.set_base(0)

        model.observe(_snap(60.0))
        result = model.observe(_snap(0.0))
        assert result.base_refresh_needed is True

    def test_base_refresh_needed_only_once(self) -> None:
        """base_refresh_needed 只在 in_progress 由 >0 轉 0 的那次為 True，其後回 False."""
        model = TodayWorkModel()
        model.set_base(0)

        model.observe(_snap(60.0))
        r1 = model.observe(_snap(0.0))
        assert r1.base_refresh_needed is True

        # 再次觀察 in_progress=0，不應再觸發
        r2 = model.observe(_snap(0.0))
        assert r2.base_refresh_needed is False

    def test_set_base_update_no_double_counting(self) -> None:
        """set_base 更新後 in_progress=0 → display=新 base，無重複累加。"""
        model = TodayWorkModel()
        model.set_base(600)

        # 工作中
        model.observe(_snap(30.0))

        # 工作結束，呼叫端更新 base
        model.observe(_snap(0.0))  # base_refresh_needed=True
        model.set_base(630)        # 模擬重抓 DB 後更新 base（包含那 30 秒）

        result = model.observe(_snap(0.0))
        assert result.display_seconds == 630
        assert result.base_refresh_needed is False

    def test_suspended_display_frozen(self) -> None:
        """SUSPENDED 快照（work_elapsed 凍結不變）→ display_seconds 不變。"""
        model = TodayWorkModel()
        model.set_base(0)

        r1 = model.observe(_snap(45.0, state=TimerState.SUSPENDED))
        r2 = model.observe(_snap(45.0, state=TimerState.SUSPENDED))

        assert r1.display_seconds == 45
        assert r2.display_seconds == 45
        assert r2.base_refresh_needed is False

    def test_rounding(self) -> None:
        """display_seconds 是 round(base + in_progress)，正確四捨五入。"""
        model = TodayWorkModel()
        model.set_base(100)

        result = model.observe(_snap(0.5))
        # round(100.5) = 100 (banker's rounding) or 101 depending on Python version
        # Python uses banker's rounding: round(100.5) == 100
        assert result.display_seconds == round(100.5)

        result2 = model.observe(_snap(1.5))
        assert result2.display_seconds == round(101.5)

    def test_initial_state(self) -> None:
        """初始狀態：base=0, 快照 work_elapsed=0 → display=0, base_refresh_needed=False."""
        model = TodayWorkModel()
        result = model.observe(_snap(0.0))
        assert result.display_seconds == 0
        assert result.base_refresh_needed is False

    def test_base_refresh_needed_false_when_starting_from_zero(self) -> None:
        """若 prev_in_progress 從未大於 0，in_progress=0 時不觸發 base_refresh_needed。"""
        model = TodayWorkModel()
        model.set_base(300)
        result = model.observe(_snap(0.0))
        assert result.base_refresh_needed is False


class TestTodayWorkDisplay:
    def test_dataclass_is_frozen(self) -> None:
        """TodayWorkDisplay 是 frozen dataclass，不可修改。"""
        display = TodayWorkDisplay(display_seconds=100, base_refresh_needed=False)
        with pytest.raises(dataclasses.FrozenInstanceError):
            display.display_seconds = 200  # type: ignore[misc]

    def test_fields(self) -> None:
        """欄位型別與值正確。"""
        display = TodayWorkDisplay(display_seconds=42, base_refresh_needed=True)
        assert display.display_seconds == 42
        assert display.base_refresh_needed is True
