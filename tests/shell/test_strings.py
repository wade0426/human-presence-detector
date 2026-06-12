from __future__ import annotations

from enum import Enum

from src.shell import strings

# 連線狀態 value 字串（與 ConnectionState enum 的 value 一致；shell 不 import 舊模組）
CONNECTION_STATUS_VALUES = (
    "idle",
    "connecting",
    "connected",
    "reconnecting",
    "no_signal",
    "stream_error",
    "error",
)

# 計時器狀態 value 字串（與 core TimerState 鎖定介面一致，含新增 rest_pending）
TIMER_STATE_VALUES = (
    "idle",
    "working",
    "away",
    "reminding",
    "rest_pending",
    "resting",
    "awaiting_return",
    "suspended",
)


class _StubTimerState(Enum):
    """duck-type 代理：值與 core TimerState 鎖定介面相同。"""

    WORKING = "working"
    REST_PENDING = "rest_pending"


class _StubConnectionState(Enum):
    RECONNECTING = "reconnecting"


def test_conn_text_covers_all_states() -> None:
    for value in CONNECTION_STATUS_VALUES:
        assert value in strings.CONN_TEXT
        assert strings.CONN_TEXT[value]


def test_state_text_covers_all_timer_states() -> None:
    for value in TIMER_STATE_VALUES:
        assert value in strings.STATE_TEXT
        assert strings.STATE_TEXT[value]


def test_timer_state_text_returns_centralized_copy() -> None:
    assert strings.timer_state_text(_StubTimerState.WORKING) == "工作中"


def test_timer_state_text_accepts_plain_value_string() -> None:
    assert strings.timer_state_text("working") == "工作中"


def test_timer_state_text_maps_rest_pending_to_status_constant() -> None:
    assert strings.timer_state_text(_StubTimerState.REST_PENDING) == strings.STATUS_REST_PENDING


def test_connection_state_text_reads_from_connection_mapping() -> None:
    assert strings.connection_state_text(_StubConnectionState.RECONNECTING) == "重新連線中"


def test_connection_state_text_accepts_plain_value_string() -> None:
    assert strings.connection_state_text("reconnecting") == "重新連線中"


def test_remind_body_format() -> None:
    result = strings.REMIND_BODY.format(duration="30 秒")
    assert "30 秒" in result


def test_remind_snooze_format() -> None:
    result = strings.REMIND_SNOOZE.format(minutes=5)
    assert "5" in result


# --- REST_PENDING／覆蓋層／中斷字串（重設計新增，文案鎖定） ---


def test_rest_pending_strings_locked_copy() -> None:
    assert strings.REST_PENDING_TITLE == "請離開座位"
    assert strings.REST_PENDING_BODY == "休息尚未開始——離開座位後才開始計時。"
    assert strings.REST_PENDING_CANCEL == "取消休息"
    assert strings.REST_INTERRUPTED_NOTICE == "休息中斷——你還欠一段休息。"
    assert strings.STATUS_REST_PENDING == "等待離席"


def test_rest_pending_dwell_format() -> None:
    result = strings.REST_PENDING_DWELL.format(duration="1 分 30 秒")
    assert "1 分 30 秒" in result


def test_lock_countdown_format() -> None:
    result = strings.LOCK_COUNTDOWN.format(seconds=30)
    assert "30" in result


def test_force_lock_strings_removed() -> None:
    """舊 force_lock 功能被升級階梯吸收，字串不得殘留。"""
    leftovers = [name for name in vars(strings) if name.startswith("FORCE_LOCK")]
    assert leftovers == []


# --- 防回歸掃描 ---


def test_no_stray_angle_quote_in_strings() -> None:
    for name, value in vars(strings).items():
        if name.startswith("_") or not isinstance(value, str):
            continue
        assert "》" not in value, f"strings.{name}={value!r} contains stray '》'"


def test_no_stray_angle_quote_in_string_mappings() -> None:
    for mapping_name in ("CONN_TEXT", "STATE_TEXT"):
        mapping = getattr(strings, mapping_name)
        for key, value in mapping.items():
            assert "》" not in value, f"{mapping_name}[{key!r}]={value!r} contains stray '》'"
