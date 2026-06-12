"""鎖屏（移植自 src/app/screen_lock.py）。

Windows 以 ``LockWorkStation`` WinAPI 鎖定工作站；非 Windows 平台為 no-op。
函式名依 spec §9 契約為 ``lock_workstation()``。
"""

from __future__ import annotations

import ctypes
import logging
import sys

logger = logging.getLogger(__name__)


def is_supported() -> bool:
    return sys.platform == "win32"


def lock_workstation() -> bool:
    if not is_supported():
        logger.info(
            "screen_lock: lock_workstation no-op (unsupported platform: %s)", sys.platform
        )
        return False
    return bool(ctypes.windll.user32.LockWorkStation())  # type: ignore[attr-defined, unused-ignore]
