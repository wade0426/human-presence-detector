from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from src.detection.detector import PersonDetector, _resolve_device
from src.types import Frame


def _frame() -> Frame:
    image = np.zeros((600, 500, 3), dtype=np.uint8)
    return Frame(image=image, width=500, height=600, timestamp=0.0)


def test_detect_normalizes_bounding_boxes() -> None:
    detector = PersonDetector("data/model/yolov8n.pt", confidence=0.4)

    with patch.object(detector, "_infer", return_value=[(100, 50, 300, 400, 0.85)]):
        detections = detector.detect(_frame())

    assert len(detections) == 1
    bbox = detections[0].bbox
    assert bbox.x == pytest.approx(0.2, abs=1e-6)
    assert bbox.y == pytest.approx(50 / 600, abs=1e-6)
    assert bbox.w == pytest.approx(0.4, abs=1e-6)
    assert bbox.h == pytest.approx(350 / 600, abs=1e-6)
    assert detections[0].confidence == pytest.approx(0.85, abs=1e-6)


def test_detect_returns_empty_list_when_no_people_found() -> None:
    detector = PersonDetector("data/model/yolov8n.pt", confidence=0.4)

    with patch.object(detector, "_infer", return_value=[]):
        detections = detector.detect(_frame())

    assert detections == []


def test_resolve_device_cpu_passthrough() -> None:
    assert _resolve_device("cpu") == "cpu"


def test_resolve_device_auto_without_cuda_returns_cpu() -> None:
    with patch("torch.cuda.is_available", return_value=False):
        assert _resolve_device("auto") == "cpu"
