from __future__ import annotations

from enum import Enum


class ConnectionState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    NO_SIGNAL = "no_signal"
    ERROR = "error"


_STATUS_MAP: dict[str, ConnectionState] = {
    "connecting": ConnectionState.CONNECTING,
    "connected": ConnectionState.CONNECTED,
    "reconnecting": ConnectionState.RECONNECTING,
    "no_signal": ConnectionState.NO_SIGNAL,
}

_SEVERITY: dict[ConnectionState, str] = {
    ConnectionState.IDLE: "neutral",
    ConnectionState.CONNECTING: "info",
    ConnectionState.CONNECTED: "success",
    ConnectionState.RECONNECTING: "warning",
    ConnectionState.NO_SIGNAL: "warning",
    ConnectionState.ERROR: "danger",
}

_ICON_KEY: dict[ConnectionState, str] = {
    ConnectionState.IDLE: "conn-idle",
    ConnectionState.CONNECTING: "conn-connecting",
    ConnectionState.CONNECTED: "conn-connected",
    ConnectionState.RECONNECTING: "conn-reconnecting",
    ConnectionState.NO_SIGNAL: "conn-no-signal",
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
