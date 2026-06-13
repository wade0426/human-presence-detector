"""src/infra/app_identity.py 測試 — Windows AppUserModelID（工作列圖示身分）。

直接以 python.exe 執行時,工作列按鈕的圖示綁在行程的 AppUserModelID,預設
沿用直譯器身分而顯示 python 圖示;設定明確的 AppUserModelID 後,工作列改用
``QApplication.setWindowIcon`` 的圖示。契約對齊 ``screen_lock``:非 Windows
平台為 no-op,副作用函式回傳 bool、失敗時安靜降級不丟例外。
"""

from __future__ import annotations

import sys
import types

import pytest

from src.infra import app_identity


def test_is_supported_matches_platform() -> None:
    assert app_identity.is_supported() == (sys.platform == "win32")


def test_set_app_user_model_id_noop_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_identity, "is_supported", lambda: False)
    assert app_identity.set_app_user_model_id() is False  # 不丟例外、回傳 False


def test_set_app_user_model_id_uses_default_id_when_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_set(app_id: str) -> int:
        calls.append(app_id)
        return 0  # S_OK

    fake_windll = types.SimpleNamespace(
        shell32=types.SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=fake_set)
    )
    monkeypatch.setattr(app_identity, "is_supported", lambda: True)
    monkeypatch.setattr(app_identity.ctypes, "windll", fake_windll, raising=False)

    assert app_identity.set_app_user_model_id() is True
    assert calls == [app_identity.APP_USER_MODEL_ID]


def test_set_app_user_model_id_passes_explicit_id(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_set(app_id: str) -> int:
        calls.append(app_id)
        return 0

    fake_windll = types.SimpleNamespace(
        shell32=types.SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=fake_set)
    )
    monkeypatch.setattr(app_identity, "is_supported", lambda: True)
    monkeypatch.setattr(app_identity.ctypes, "windll", fake_windll, raising=False)

    assert app_identity.set_app_user_model_id("Vendor.MyApp") is True
    assert calls == ["Vendor.MyApp"]


def test_set_app_user_model_id_returns_false_on_winapi_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_set(_app_id: str) -> int:
        return -2147024891  # E_ACCESSDENIED：非 S_OK 的 HRESULT

    fake_windll = types.SimpleNamespace(
        shell32=types.SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=fake_set)
    )
    monkeypatch.setattr(app_identity, "is_supported", lambda: True)
    monkeypatch.setattr(app_identity.ctypes, "windll", fake_windll, raising=False)

    assert app_identity.set_app_user_model_id() is False


def test_set_app_user_model_id_returns_false_when_winapi_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_set(_app_id: str) -> int:
        raise OSError("boom")

    fake_windll = types.SimpleNamespace(
        shell32=types.SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=fake_set)
    )
    monkeypatch.setattr(app_identity, "is_supported", lambda: True)
    monkeypatch.setattr(app_identity.ctypes, "windll", fake_windll, raising=False)

    assert app_identity.set_app_user_model_id() is False  # 安靜降級
