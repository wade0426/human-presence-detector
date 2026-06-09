from __future__ import annotations

from typing import Any

from src.types import BBox, Detection, Frame


def _resolve_device(device: str) -> str:
    if device in {"cpu", "cuda"}:
        return device
    if device != "auto":
        return device
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


class PersonDetector:
    def __init__(self, model_path: str, confidence: float, device: str = "auto") -> None:
        self._model_path = model_path
        self._confidence = confidence
        self._device = _resolve_device(device)
        self.model: Any | None = None

    def detect(self, frame: Frame) -> list[Detection]:
        detections: list[Detection] = []
        for x1, y1, x2, y2, confidence in self._infer(frame.image):
            bbox = BBox(
                x=x1 / frame.width,
                y=y1 / frame.height,
                w=(x2 - x1) / frame.width,
                h=(y2 - y1) / frame.height,
            )
            detections.append(Detection(bbox=bbox, confidence=confidence))
        return detections

    def _infer(self, image: Any) -> list[tuple[float, float, float, float, float]]:
        model = self._ensure_model()
        results = model(image, classes=[0], conf=self._confidence, verbose=False)
        boxes = results[0].boxes
        output: list[tuple[float, float, float, float, float]] = []
        for xyxy, confidence in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), strict=False):
            x1, y1, x2, y2 = xyxy
            output.append((float(x1), float(y1), float(x2), float(y2), float(confidence)))
        return output

    def _ensure_model(self) -> Any:
        if self.model is None:
            from ultralytics import YOLO

            self.model = YOLO(self._model_path)
            self.model.to(self._device)
        return self.model
