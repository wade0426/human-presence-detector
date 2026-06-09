"""單元測試：src/duration_format.py"""

from __future__ import annotations

from src.duration_format import format_clock, format_duration_zh

# ---------------------------------------------------------------------------
# format_clock
# ---------------------------------------------------------------------------

class TestFormatClock:
    def test_zero(self) -> None:
        assert format_clock(0) == "00:00"

    def test_59_seconds(self) -> None:
        assert format_clock(59) == "00:59"

    def test_90_seconds(self) -> None:
        assert format_clock(90) == "01:30"

    def test_3661_seconds(self) -> None:
        assert format_clock(3661) == "61:01"

    def test_negative_clamps_to_zero(self) -> None:
        assert format_clock(-5) == "00:00"

    def test_nan_clamps_to_zero(self) -> None:
        assert format_clock(float("nan")) == "00:00"

    def test_inf_clamps_to_zero(self) -> None:
        assert format_clock(float("inf")) == "00:00"

    def test_negative_inf_clamps_to_zero(self) -> None:
        assert format_clock(float("-inf")) == "00:00"

    def test_fractional_truncated(self) -> None:
        # 60.9 → 60 total secs → 01:00
        assert format_clock(60.9) == "01:00"

    def test_exact_one_minute(self) -> None:
        assert format_clock(60) == "01:00"


# ---------------------------------------------------------------------------
# format_duration_zh
# ---------------------------------------------------------------------------

class TestFormatDurationZh:
    def test_zero(self) -> None:
        assert format_duration_zh(0) == "0 秒"

    def test_29_point_9(self) -> None:
        assert format_duration_zh(29.9) == "29 秒"

    def test_30(self) -> None:
        assert format_duration_zh(30) == "30 秒"

    def test_59(self) -> None:
        assert format_duration_zh(59) == "59 秒"

    def test_60(self) -> None:
        assert format_duration_zh(60) == "1 分鐘"

    def test_90(self) -> None:
        assert format_duration_zh(90) == "1 分 30 秒"

    def test_150(self) -> None:
        assert format_duration_zh(150) == "2 分 30 秒"

    def test_120_no_remainder(self) -> None:
        assert format_duration_zh(120) == "2 分鐘"

    def test_negative_clamps_to_zero(self) -> None:
        assert format_duration_zh(-1) == "0 秒"

    def test_nan_clamps_to_zero(self) -> None:
        assert format_duration_zh(float("nan")) == "0 秒"

    def test_inf_clamps_to_zero(self) -> None:
        assert format_duration_zh(float("inf")) == "0 秒"

    def test_negative_inf_clamps_to_zero(self) -> None:
        assert format_duration_zh(float("-inf")) == "0 秒"

    def test_fractional_truncated_below_minute(self) -> None:
        # 59.99 → int → 59 → '59 秒'
        assert format_duration_zh(59.99) == "59 秒"
