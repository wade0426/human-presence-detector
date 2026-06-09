"""duration_format – 把秒數格式化為顯示字串的純函式集合。

公開介面：
    format_clock(seconds)       → 'MM:SS'（分鐘可超過 99）
    format_duration_zh(seconds) → 動態中文時長字串
"""

from __future__ import annotations

import math


def format_clock(seconds: float) -> str:
    """秒數 → 'MM:SS'。

    負數、NaN、inf 均截為 0，不丟例外。
    分鐘數可超過 99，例如 3661 → '61:01'。
    """
    if not math.isfinite(seconds) or seconds < 0:
        seconds = 0.0
    total_secs = int(seconds)
    minutes = total_secs // 60
    secs = total_secs % 60
    return f"{minutes:02d}:{secs:02d}"


def format_duration_zh(seconds: float) -> str:
    """秒數 → 動態中文時長字串。

    負數、NaN、inf 均以 0 處理，不丟例外。

    規則：
        - seconds < 60  → 'N 秒'（向下取整，最小 '0 秒'）
        - seconds >= 60 → 餘秒為 0 時 'M 分鐘'，否則 'M 分 S 秒'

    範例：
        30  → '30 秒'
        60  → '1 分鐘'
        90  → '1 分 30 秒'
        150 → '2 分 30 秒'
    """
    if not math.isfinite(seconds) or seconds < 0:
        seconds = 0.0
    total_secs = int(seconds)
    if total_secs < 60:
        return f"{total_secs} 秒"
    minutes = total_secs // 60
    remaining = total_secs % 60
    if remaining == 0:
        return f"{minutes} 分鐘"
    return f"{minutes} 分 {remaining} 秒"
