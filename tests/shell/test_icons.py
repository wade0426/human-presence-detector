from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QIcon, QPixmap

REPO_ROOT = Path(__file__).resolve().parents[2]
ICON_ASSET = REPO_ROOT / "data" / "assets" / "icon.png"
REST_PLACEHOLDER = REPO_ROOT / "data" / "assets" / "rest_placeholder.png"


def test_make_app_icon_not_null(qtbot: object) -> None:
    from src.shell.icons import make_app_icon

    icon = make_app_icon()

    assert not icon.isNull()


def test_load_app_icon_fallback_when_missing(qtbot: object, tmp_path: Path) -> None:
    from src.shell.icons import load_app_icon

    icon = load_app_icon(asset_path=str(tmp_path / "nonexistent.png"))

    assert not icon.isNull()


def test_load_app_icon_loads_explicit_asset(qtbot: object, tmp_path: Path) -> None:
    """A known solid-color png passed explicitly must be loaded pixel-for-pixel."""
    from src.shell.icons import load_app_icon

    source = QPixmap(8, 8)
    source.fill(QColor("#FF0000"))
    asset_path = tmp_path / "red.png"
    assert source.save(str(asset_path))

    icon = load_app_icon(asset_path=str(asset_path))

    image = icon.pixmap(8, 8).toImage()
    assert not image.isNull()
    assert image.pixelColor(4, 4) == QColor("#FF0000")


def test_load_app_icon_uses_repo_asset_when_cwd_changes(
    qtbot: object, monkeypatch: object, tmp_path: Path
) -> None:
    """§4.15: default path is anchored to the module, not the CWD, and points at
    the real shipped asset icon.png. Fails when the asset is missing."""
    from src.shell.icons import load_app_icon

    assert ICON_ASSET.exists(), f"missing shipped asset: {ICON_ASSET}"

    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]

    icon = load_app_icon()
    expected = QIcon(str(ICON_ASSET))

    assert not icon.isNull()
    assert icon.pixmap(64, 64).toImage() == expected.pixmap(64, 64).toImage()


def test_rest_placeholder_decodes_with_qpixmap_and_cv2(qtbot: object) -> None:
    """§4.12: the shipped placeholder must be a valid PNG (no libpng CRC error)."""
    import cv2

    assert REST_PLACEHOLDER.exists(), f"missing shipped asset: {REST_PLACEHOLDER}"

    array = cv2.imread(str(REST_PLACEHOLDER))
    assert array is not None
    assert array.size > 0

    pixmap = QPixmap(str(REST_PLACEHOLDER))
    assert not pixmap.isNull()
    assert pixmap.width() > 0 and pixmap.height() > 0
