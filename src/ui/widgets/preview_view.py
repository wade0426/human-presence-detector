from __future__ import annotations

import cv2
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import QLabel, QRubberBand, QSizePolicy, QVBoxLayout, QWidget

from src.types import BBox, Frame


class PreviewView(QWidget):
    roi_committed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._edit_mode = False
        self._origin: QPoint | None = None
        self._roi = BBox(0.0, 0.0, 1.0, 1.0)
        self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._label = QLabel(self)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setText("")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    def set_frame(self, frame: Frame) -> None:
        rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format.Format_RGB888)
        self._label.setPixmap(
            QPixmap.fromImage(image.copy()).scaled(
                self._label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def set_roi(self, roi: BBox) -> None:
        self._roi = roi

    def set_edit_mode(self, on: bool) -> None:
        self._edit_mode = on
        self.setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.ArrowCursor)
        if on:
            from src.ui.strings import ROI_HINT
            self._label.setText(ROI_HINT)
        else:
            self._label.setText("")

    def set_overlay_text(self, text: str) -> None:
        self._label.setText(text)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._edit_mode and event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._rubber.setGeometry(QRect(self._origin, QSize()))
            self._rubber.show()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._edit_mode and self._origin is not None:
            self._rubber.setGeometry(QRect(self._origin, event.position().toPoint()).normalized())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            self._edit_mode
            and self._origin is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            rect = QRect(self._origin, event.position().toPoint()).normalized()
            self._rubber.hide()
            self._origin = None
            width = max(self.width(), 1)
            height = max(self.height(), 1)
            roi = BBox(
                x=rect.x() / width,
                y=rect.y() / height,
                w=rect.width() / width,
                h=rect.height() / height,
            )
            self._roi = roi
            self.roi_committed.emit(roi)
        super().mouseReleaseEvent(event)
