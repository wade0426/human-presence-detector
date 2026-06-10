from __future__ import annotations

import sys

from src.app import screen_lock


def test_is_supported_matches_platform() -> None:
    assert screen_lock.is_supported() == (sys.platform == "win32")


def test_lock_screen_noop_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(screen_lock, "is_supported", lambda: False)
    result = screen_lock.lock_screen()
    assert result is False  # 不丟例外、回傳 False
