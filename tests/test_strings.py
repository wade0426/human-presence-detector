from __future__ import annotations

from src.app.connection_state import ConnectionState
from src.types import TimerState
from src.ui import strings
from src.ui.settings_schema import SCHEMA


def test_conn_text_covers_all_states() -> None:
    for state in ConnectionState:
        assert state in strings.CONN_TEXT


def test_state_text_covers_all_timer_states() -> None:
    for state in TimerState:
        assert state in strings.STATE_TEXT
        assert strings.STATE_TEXT[state]


def test_timer_state_text_returns_centralized_copy() -> None:
    assert strings.timer_state_text(TimerState.WORKING) == "工作中"


def test_connection_state_text_reads_from_connection_mapping() -> None:
    assert strings.connection_state_text(ConnectionState.RECONNECTING) == "重新連線中"


def test_remind_body_format() -> None:
    # FR-3: REMIND_BODY 改用 {duration} 格式（由 format_duration_zh 提供）
    result = strings.REMIND_BODY.format(duration="30 秒")
    assert "30 秒" in result


def test_remind_snooze_format() -> None:
    result = strings.REMIND_SNOOZE.format(minutes=5)
    assert "5" in result


# --- M5 防回歸掃描測試 ---


def test_reminding_display_hint_uses_paired_quotes() -> None:
    spec = next(s for s in SCHEMA if s.key == "reminder.reminding_display_mode")
    assert spec.hint == "提醒中要顯示「超時時間」還是「工作時間＋提醒持續時間」。"
    assert "》" not in spec.hint


def test_no_stray_angle_quote_in_schema() -> None:
    for spec in SCHEMA:
        for attr in ("label", "hint"):
            value = getattr(spec, attr)
            assert "》" not in value, (
                f"FieldSpec key={spec.key!r} {attr}={value!r} contains stray '》'"
            )


def test_no_stray_angle_quote_in_strings() -> None:
    for name, value in vars(strings).items():
        if name.startswith("_") or not isinstance(value, str):
            continue
        assert "》" not in value, (
            f"strings.{name}={value!r} contains stray '》'"
        )
