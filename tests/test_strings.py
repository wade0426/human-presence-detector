from __future__ import annotations

from src.types import TimerState
from src.ui import strings


def test_conn_text_covers_all_states() -> None:
    expected_keys = {
        "idle",
        "connecting",
        "connected",
        "reconnecting",
        "no_signal",
        "error",
    }
    assert set(strings.CONN_TEXT) == expected_keys


def test_state_text_covers_all_timer_states() -> None:
    for state in TimerState:
        assert state in strings.STATE_TEXT
        assert strings.STATE_TEXT[state]


def test_remind_body_format() -> None:
    result = strings.REMIND_BODY.format(minutes=30)
    assert "30" in result


def test_remind_snooze_format() -> None:
    result = strings.REMIND_SNOOZE.format(minutes=5)
    assert "5" in result
