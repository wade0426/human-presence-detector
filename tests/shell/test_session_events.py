"""SessionUnlockWatcher／_UnlockEventFilter（spec §5「鎖屏後回來」的輸入源）。

native event filter 以人造 MSG 結構直接呼叫測試（offscreen 下無法觸發真實
WM_WTSSESSION_CHANGE）；註冊路徑僅驗證非啟動狀態的安全行為。
"""

from __future__ import annotations

import ctypes
import sys
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows session messages only"
)

WM_SETTINGCHANGE = 0x001A  # 任意非 session 訊息，作為負例
WTS_SESSION_LOCK = 0x7


def _make_msg(message: int, wparam: int) -> Any:
    import ctypes.wintypes as wintypes

    msg = wintypes.MSG()
    msg.message = message
    msg.wParam = wparam
    return msg


def test_filter_invokes_callback_on_session_unlock() -> None:
    from src.shell.session_events import (
        WM_WTSSESSION_CHANGE,
        WTS_SESSION_UNLOCK,
        _UnlockEventFilter,
    )

    calls: list[bool] = []
    filt = _UnlockEventFilter(lambda: calls.append(True))
    msg = _make_msg(WM_WTSSESSION_CHANGE, WTS_SESSION_UNLOCK)

    result = filt.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))

    assert calls == [True]
    assert result == (False, 0)  # 不攔截，讓 Qt 繼續派發


def test_filter_ignores_lock_and_unrelated_messages() -> None:
    from src.shell.session_events import (
        WM_WTSSESSION_CHANGE,
        WTS_SESSION_UNLOCK,
        _UnlockEventFilter,
    )

    calls: list[bool] = []
    filt = _UnlockEventFilter(lambda: calls.append(True))

    lock_msg = _make_msg(WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK)
    filt.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(lock_msg))
    other_msg = _make_msg(WM_SETTINGCHANGE, WTS_SESSION_UNLOCK)
    filt.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(other_msg))

    assert calls == []


def test_filter_ignores_non_windows_event_type() -> None:
    from src.shell.session_events import (
        WM_WTSSESSION_CHANGE,
        WTS_SESSION_UNLOCK,
        _UnlockEventFilter,
    )

    calls: list[bool] = []
    filt = _UnlockEventFilter(lambda: calls.append(True))
    msg = _make_msg(WM_WTSSESSION_CHANGE, WTS_SESSION_UNLOCK)

    filt.nativeEventFilter(b"xcb_generic_event_t", ctypes.addressof(msg))

    assert calls == []


def test_watcher_emits_unlocked_signal(qtbot: QtBot) -> None:
    from src.shell.session_events import SessionUnlockWatcher

    watcher = SessionUnlockWatcher()

    with qtbot.waitSignal(watcher.unlocked, timeout=1000):
        watcher._emit_unlocked()


def test_watcher_stop_without_start_is_safe(qtbot: QtBot) -> None:
    from src.shell.session_events import SessionUnlockWatcher

    watcher = SessionUnlockWatcher()
    watcher.stop()  # 未註冊先 stop：不得拋例外
    assert watcher.watching is False
