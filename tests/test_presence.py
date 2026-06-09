from __future__ import annotations

from src.presence import PresenceEvaluator
from src.types import BBox, Detection


def _detection(bbox: BBox, confidence: float = 0.9) -> Detection:
    return Detection(bbox=bbox, confidence=confidence)


def test_presence_requires_full_debounce_before_flip() -> None:
    evaluator = PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.25, 3)
    hit = [_detection(BBox(0.25, 0.25, 0.3, 0.3))]

    assert evaluator.update(hit) is False
    assert evaluator.update(hit) is False
    assert evaluator.update(hit) is True


def test_presence_accepts_left_boundary_and_rejects_past_right_boundary() -> None:
    evaluator = PresenceEvaluator(BBox(0.3, 0.2, 0.4, 0.5), 0.25, 1)

    on_left_edge = [_detection(BBox(0.1, 0.3, 0.4, 0.25))]
    past_right_edge = [_detection(BBox(0.5001, 0.3, 0.4, 0.25))]

    assert evaluator.update(on_left_edge) is True
    assert evaluator.update(past_right_edge) is False


def test_presence_checks_min_box_height_ratio() -> None:
    evaluator = PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.25, 1)

    assert evaluator.update([_detection(BBox(0.1, 0.1, 0.2, 0.25))]) is True
    assert evaluator.update([_detection(BBox(0.1, 0.1, 0.2, 0.249))]) is False


def test_presence_empty_detections_require_debounce_to_flip_absent() -> None:
    evaluator = PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.25, 2)
    hit = [_detection(BBox(0.25, 0.25, 0.3, 0.3))]

    assert evaluator.update(hit) is False
    assert evaluator.update(hit) is True
    assert evaluator.update([]) is True
    assert evaluator.update([]) is False


def test_presence_any_qualifying_detection_is_enough() -> None:
    evaluator = PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.25, 1)

    detections = [
        _detection(BBox(1.1, 0.1, 0.2, 0.3)),
        _detection(BBox(0.1, 0.1, 0.2, 0.3)),
    ]

    assert evaluator.update(detections) is True


def test_presence_uses_new_roi_after_set_roi() -> None:
    evaluator = PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.25, 1)
    detection = [_detection(BBox(0.1, 0.1, 0.2, 0.3))]

    assert evaluator.update(detection) is True

    evaluator.set_roi(BBox(0.6, 0.6, 0.2, 0.2))

    assert evaluator.update(detection) is False
