"""src/types.py 基礎型別測試。

計時器/提醒型別的測試已隨型別遷移：core 型別見 tests/core/，
ReminderContext 見 tests/shell/test_reminders.py（T11 切換）。
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from src.types import BBox, Detection, Frame


def test_bbox_center_for_unit_square() -> None:
    assert BBox(0.0, 0.0, 1.0, 1.0).center == (0.5, 0.5)


def test_bbox_center_for_offset_rectangle() -> None:
    center_x, center_y = BBox(0.1, 0.2, 0.4, 0.6).center
    assert center_x == pytest.approx(0.3, abs=1e-9)
    assert center_y == pytest.approx(0.5, abs=1e-9)


def test_bbox_is_frozen() -> None:
    bbox = BBox(0.0, 0.0, 1.0, 1.0)
    with pytest.raises(FrozenInstanceError):
        bbox.x = 1.0  # type: ignore[misc]


def test_detection_holds_bbox_and_confidence() -> None:
    det = Detection(bbox=BBox(0.1, 0.1, 0.5, 0.5), confidence=0.9)
    assert det.bbox.w == 0.5
    assert det.confidence == pytest.approx(0.9)


def test_detection_is_frozen() -> None:
    det = Detection(bbox=BBox(0.0, 0.0, 1.0, 1.0), confidence=0.5)
    with pytest.raises(FrozenInstanceError):
        det.confidence = 1.0  # type: ignore[misc]


def test_frame_fields() -> None:
    image = np.zeros((4, 6, 3), dtype=np.uint8)
    frame = Frame(image=image, width=6, height=4, timestamp=12.5)
    assert frame.width == 6
    assert frame.height == 4
    assert frame.timestamp == pytest.approx(12.5)
    assert frame.image.shape == (4, 6, 3)
