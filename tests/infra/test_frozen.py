"""src/infra/frozen.py 測試 — PyInstaller 凍結後的工作目錄/資源根目錄處理。

凍結(onedir)後從開始功能表/釘選啟動時,CWD 可能是 System32 之類,導致
``config.yaml`` 與 ``data/model`` 等 CWD 相對路徑讀不到。進入點先把工作目錄
切到 exe 所在資料夾即可穩定解析;開發模式(未凍結)為 no-op。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infra import frozen


def test_is_frozen_reflects_sys_attr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(frozen.sys, "frozen", True, raising=False)
    assert frozen.is_frozen() is True
    monkeypatch.setattr(frozen.sys, "frozen", False, raising=False)
    assert frozen.is_frozen() is False


def test_bundle_dir_is_project_root_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(frozen, "is_frozen", lambda: False)
    # frozen.py 位於 src/infra/,parents[2] 為專案根。
    assert frozen.bundle_dir() == Path(frozen.__file__).resolve().parents[2]


def test_bundle_dir_is_exe_parent_when_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "app" / "HumanPresenceDetector.exe"
    monkeypatch.setattr(frozen, "is_frozen", lambda: True)
    monkeypatch.setattr(frozen.sys, "executable", str(exe))
    assert frozen.bundle_dir() == Path(str(exe)).resolve().parent


def test_chdir_noop_when_not_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(frozen, "is_frozen", lambda: False)
    monkeypatch.setattr(frozen.os, "chdir", lambda p: calls.append(p))
    assert frozen.chdir_to_bundle() is False
    assert calls == []  # 未凍結不得切換工作目錄


def test_chdir_to_exe_dir_when_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Path] = []
    exe = tmp_path / "app" / "HumanPresenceDetector.exe"
    monkeypatch.setattr(frozen, "is_frozen", lambda: True)
    monkeypatch.setattr(frozen.sys, "executable", str(exe))
    monkeypatch.setattr(frozen.os, "chdir", lambda p: calls.append(Path(p)))
    assert frozen.chdir_to_bundle() is True
    assert calls == [Path(str(exe)).resolve().parent]
