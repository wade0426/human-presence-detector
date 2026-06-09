from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.types import BBox


def test_bbox_center_for_unit_square() -> None:
    assert BBox(0.0, 0.0, 1.0, 1.0).center == (0.5, 0.5)


def test_bbox_center_for_offset_rectangle() -> None:
    center_x, center_y = BBox(0.1, 0.2, 0.4, 0.6).center
    assert center_x == pytest.approx(0.3, abs=1e-9)
    assert center_y == pytest.approx(0.5, abs=1e-9)


def test_bbox_is_frozen() -> None:
    bbox = BBox(0.0, 0.0, 1.0, 1.0)
    with pytest.raises(FrozenInstanceError):
        bbox.x = 1.0
