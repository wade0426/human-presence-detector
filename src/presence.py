from __future__ import annotations

from src.types import BBox, Detection


class PresenceEvaluator:
    def __init__(self, roi: BBox, min_box_height_ratio: float, debounce_count: int) -> None:
        self._roi = roi
        self._min_box_height_ratio = min_box_height_ratio
        self._debounce_count = debounce_count
        self._stable_present = False
        self._pending: bool | None = None
        self._count = 0

    def update(self, detections: list[Detection]) -> bool:
        raw = any(self._qualifies(detection) for detection in detections)
        if raw == self._stable_present:
            self._pending = None
            self._count = 0
            return self._stable_present

        if raw == self._pending:
            self._count += 1
        else:
            self._pending = raw
            self._count = 1

        if self._count >= self._debounce_count:
            self._stable_present = raw
            self._pending = None
            self._count = 0

        return self._stable_present

    def set_roi(self, roi: BBox) -> None:
        self._roi = roi

    @property
    def stable_present(self) -> bool:
        return self._stable_present

    def _qualifies(self, detection: Detection) -> bool:
        center_x, center_y = detection.bbox.center
        in_roi = (
            self._roi.x <= center_x <= (self._roi.x + self._roi.w)
            and self._roi.y <= center_y <= (self._roi.y + self._roi.h)
        )
        return in_roi and detection.bbox.h >= self._min_box_height_ratio
