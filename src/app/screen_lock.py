from __future__ import annotations

import ctypes
import logging
import sys

logger = logging.getLogger(__name__)


def is_supported() -> bool:
    return sys.platform == "win32"


def lock_screen() -> bool:
    if not is_supported():
        logger.info("screen_lock: lock_screen no-op (unsupported platform: %s)", sys.platform)
        return False
    return bool(ctypes.windll.user32.LockWorkStation())  # type: ignore[attr-defined, unused-ignore]
