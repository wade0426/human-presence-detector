"""Windows 工作階段解鎖偵測（spec §5「鎖屏後回來」階梯歸零的輸入源）。

stage 3 鎖屏後使用者解鎖續坐時，core 需要一個「回來了」的輸入把升級階梯
歸零重爬（spec §10：解鎖回來視同仍在原狀態繼續判定；spec §5：鎖屏仍受
單一工作週期至多一次限制）。Windows 以 ``WTSRegisterSessionNotification``
訂閱工作階段通知，``WM_WTSSESSION_CHANGE(wParam=WTS_SESSION_UNLOCK)`` 經
``QAbstractNativeEventFilter`` 攔截後轉成 Qt signal（GUI 執行緒）；非
Windows 平台 ``start()`` 回傳 False、全程 no-op（與 ``src/infra/screen_lock``
同慣例）。

訊息接收視窗：watcher 自建一個永不顯示的 QWidget（``WA_DontShowOnScreen``）
取得原生 HWND——session 通知是投遞給特定視窗的訊息，不依附主視窗、避免
其 native handle 重建時通知失聯。
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable

from PySide6.QtCore import (
    QAbstractNativeEventFilter,
    QByteArray,
    QCoreApplication,
    QObject,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QWidget

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_UNLOCK = 0x8
_NOTIFY_FOR_THIS_SESSION = 0


class _UnlockEventFilter(QAbstractNativeEventFilter):
    """攔截 WM_WTSSESSION_CHANGE(WTS_SESSION_UNLOCK) 轉呼叫 callback；不攔截事件。"""

    def __init__(self, on_unlock: Callable[[], None]) -> None:
        super().__init__()
        self._on_unlock = on_unlock

    def nativeEventFilter(
        self,
        eventType: QByteArray | bytes | bytearray | memoryview,
        message: int,
    ) -> tuple[bool, int]:
        if eventType == b"windows_generic_MSG" and sys.platform == "win32":
            import ctypes.wintypes

            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_WTSSESSION_CHANGE and msg.wParam == WTS_SESSION_UNLOCK:
                self._on_unlock()
        return (False, 0)


class SessionUnlockWatcher(QObject):
    """工作階段解鎖 → ``unlocked`` signal（GUI 執行緒）。"""

    unlocked = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._filter: _UnlockEventFilter | None = None
        self._receiver: QWidget | None = None
        self._hwnd: int | None = None

    @property
    def watching(self) -> bool:
        return self._filter is not None

    def start(self) -> bool:
        """註冊 session 通知；成功（或已在監看）回 True，非 Windows 回 False。"""
        if self._filter is not None:
            return True
        if sys.platform != "win32":
            return False
        app = QCoreApplication.instance()
        if app is None:
            return False
        receiver = QWidget()
        receiver.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        hwnd = int(receiver.winId())
        registered = ctypes.windll.wtsapi32.WTSRegisterSessionNotification(
            hwnd, _NOTIFY_FOR_THIS_SESSION
        )
        if not registered:
            # offscreen／非原生視窗等註冊失敗情境：安靜降級（無解鎖偵測）。
            receiver.deleteLater()
            return False
        self._receiver = receiver
        self._hwnd = hwnd
        self._filter = _UnlockEventFilter(self._emit_unlocked)
        app.installNativeEventFilter(self._filter)
        return True

    @Slot()
    def stop(self) -> None:
        app = QCoreApplication.instance()
        if self._filter is not None and app is not None:
            app.removeNativeEventFilter(self._filter)
        self._filter = None
        if self._hwnd is not None and sys.platform == "win32":
            ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(self._hwnd)
        self._hwnd = None
        if self._receiver is not None:
            self._receiver.deleteLater()
            self._receiver = None

    def _emit_unlocked(self) -> None:
        self.unlocked.emit()
