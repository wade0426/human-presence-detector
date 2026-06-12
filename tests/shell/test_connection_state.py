"""連線狀態對映（自 tests/test_connection_state.py 移植，改 import shell.widgets）。"""

from __future__ import annotations

from src.shell.widgets.connection_state import (
    ConnectionState,
    from_status,
    icon_key,
    severity,
)


def test_from_status_known() -> None:
    assert from_status("connecting") == ConnectionState.CONNECTING
    assert from_status("connected") == ConnectionState.CONNECTED
    assert from_status("reconnecting") == ConnectionState.RECONNECTING
    assert from_status("no_signal") == ConnectionState.NO_SIGNAL


def test_from_status_unknown_returns_idle() -> None:
    assert from_status("unknown_xyz") == ConnectionState.IDLE
    assert from_status("") == ConnectionState.IDLE


def test_severity_all_states_have_value() -> None:
    for state in ConnectionState:
        result = severity(state)
        assert result in ("muted", "info", "success", "warning", "danger")


def test_idle_severity_is_muted() -> None:
    """§4.16: IDLE uses the unified 'muted' role so the QSS only needs one rule."""
    assert severity(ConnectionState.IDLE) == "muted"


def test_icon_key_all_states_non_empty() -> None:
    for state in ConnectionState:
        key = icon_key(state)
        assert isinstance(key, str)
        assert key


def test_error_not_mapped_via_from_status() -> None:
    assert from_status("error") == ConnectionState.IDLE
