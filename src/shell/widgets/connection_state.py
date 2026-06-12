"""連線狀態對映（自 src/app/connection_state.py 移植，無 Qt 依賴）。"""

from __future__ import annotations

from enum import Enum


class ConnectionState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    NO_SIGNAL = "no_signal"
    STREAM_ERROR = "stream_error"  # 影像異常（解碼失敗或逾時）
    ERROR = "error"


_STATUS_MAP: dict[str, ConnectionState] = {
    "connecting": ConnectionState.CONNECTING,
    "connected": ConnectionState.CONNECTED,
    "reconnecting": ConnectionState.RECONNECTING,
    "no_signal": ConnectionState.NO_SIGNAL,
    "stream_error": ConnectionState.STREAM_ERROR,
}

_SEVERITY: dict[ConnectionState, str] = {
    ConnectionState.IDLE: "muted",  # 與 PresenceBadge 的 muted 統一，共用同一條 QSS 規則
    ConnectionState.CONNECTING: "info",
    ConnectionState.CONNECTED: "success",
    ConnectionState.RECONNECTING: "warning",
    ConnectionState.NO_SIGNAL: "warning",
    ConnectionState.STREAM_ERROR: "warning",
    ConnectionState.ERROR: "danger",
}

_ICON_KEY: dict[ConnectionState, str] = {
    ConnectionState.IDLE: "conn-idle",
    ConnectionState.CONNECTING: "conn-connecting",
    ConnectionState.CONNECTED: "conn-connected",
    ConnectionState.RECONNECTING: "conn-reconnecting",
    ConnectionState.NO_SIGNAL: "conn-no-signal",
    ConnectionState.STREAM_ERROR: "conn-stream-error",
    ConnectionState.ERROR: "conn-error",
}


def from_status(status: str) -> ConnectionState:
    """Map a worker status string to a UI connection state."""
    return _STATUS_MAP.get(status, ConnectionState.IDLE)


def severity(state: ConnectionState) -> str:
    """Return the semantic color role for a connection state."""
    return _SEVERITY[state]


def icon_key(state: ConnectionState) -> str:
    """Return the icon key associated with a connection state."""
    return _ICON_KEY[state]
