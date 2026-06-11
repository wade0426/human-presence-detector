from __future__ import annotations

import logging
import sys
import types
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


# ---------------------------------------------------------------------------
# FR-1.6：裝置初始化失敗 → 自動退回 CPU 繼續偵測（不終止、記 log）
# ---------------------------------------------------------------------------


class _FakeModel:
    def __init__(self, fail_devices: frozenset[str] = frozenset()) -> None:
        self._fail_devices = fail_devices
        self.to_calls: list[str] = []

    def to(self, device: str) -> None:
        self.to_calls.append(device)
        if device in self._fail_devices:
            raise AssertionError("Torch not compiled with CUDA enabled")


def _patch_ultralytics(monkeypatch: pytest.MonkeyPatch, model: _FakeModel) -> None:
    fake_module = types.SimpleNamespace(YOLO=lambda path: model)
    monkeypatch.setitem(sys.modules, "ultralytics", fake_module)


def test_device_fallback_defaults_to_false() -> None:
    detector = PersonDetector("data/model/yolov8n.pt", confidence=0.4, device="cpu")
    assert detector.device_fallback is False


def test_ensure_model_falls_back_to_cpu_when_device_init_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    model = _FakeModel(fail_devices=frozenset({"cuda"}))
    _patch_ultralytics(monkeypatch, model)
    detector = PersonDetector("data/model/yolov8n.pt", confidence=0.4, device="cuda")

    with caplog.at_level(logging.WARNING, logger="src.detection.detector"):
        result = detector._ensure_model()  # 不得拋例外

    assert result is model
    assert model.to_calls == ["cuda", "cpu"]
    assert detector.device_fallback is True
    assert any("cuda" in record.getMessage().lower() for record in caplog.records)


def test_ensure_model_no_fallback_when_device_init_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _FakeModel()
    _patch_ultralytics(monkeypatch, model)
    detector = PersonDetector("data/model/yolov8n.pt", confidence=0.4, device="cuda")

    result = detector._ensure_model()

    assert result is model
    assert model.to_calls == ["cuda"]
    assert detector.device_fallback is False


def test_ensure_model_reraises_when_cpu_itself_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CPU 本身失敗時沒有可退路，例外照常外洩（由 worker 的 failed 機制處理）。"""
    model = _FakeModel(fail_devices=frozenset({"cpu"}))
    _patch_ultralytics(monkeypatch, model)
    detector = PersonDetector("data/model/yolov8n.pt", confidence=0.4, device="cpu")

    with pytest.raises(AssertionError):
        detector._ensure_model()

    assert detector.device_fallback is False
