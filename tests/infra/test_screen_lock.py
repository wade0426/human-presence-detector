"""src/infra/screen_lock.py 測試 — 自 tests/test_screen_lock.py 移植。

函式名依 spec §9 契約為 ``lock_workstation()``（T10 以此接線）。
"""

from __future__ import annotations

import sys
import types

import pytest

from src.infra import screen_lock


def test_is_supported_matches_platform() -> None:
    assert screen_lock.is_supported() == (sys.platform == "win32")


def test_lock_workstation_noop_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(screen_lock, "is_supported", lambda: False)
    result = screen_lock.lock_workstation()
    assert result is False  # 不丟例外、回傳 False


def test_lock_workstation_calls_winapi_when_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_lock() -> int:
        calls.append("lock")
        return 1

    fake_windll = types.SimpleNamespace(user32=types.SimpleNamespace(LockWorkStation=fake_lock))
    monkeypatch.setattr(screen_lock, "is_supported", lambda: True)
    monkeypatch.setattr(screen_lock.ctypes, "windll", fake_windll, raising=False)

    assert screen_lock.lock_workstation() is True
    assert calls == ["lock"]
