from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


def _pixmap_cache_key(icon: QIcon, size: int = 64) -> int:
    return icon.pixmap(size, size).cacheKey()


def test_make_app_icon_not_null(qtbot: object) -> None:
    from src.ui.icons import make_app_icon

    icon = make_app_icon()

    assert not icon.isNull()


def test_load_app_icon_fallback_when_missing(qtbot: object, tmp_path: object) -> None:
    from src.ui.icons import load_app_icon

    icon = load_app_icon(asset_path=str(tmp_path / "nonexistent.png"))

    assert not icon.isNull()


def test_load_app_icon_uses_repo_asset_when_cwd_changes(
    qtbot: object, monkeypatch: object, tmp_path: Path
) -> None:
    from src.ui.icons import load_app_icon

    monkeypatch.chdir(tmp_path)

    icon = load_app_icon()
    fallback_icon = load_app_icon(asset_path=str(tmp_path / "nonexistent.png"))

    assert not icon.isNull()
    assert _pixmap_cache_key(icon) != _pixmap_cache_key(fallback_icon)
