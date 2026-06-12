"""影像預覽＋ROI 編輯（自 src/ui/widgets/preview_view.py 移植）。"""

from __future__ import annotations

import cv2
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel, QRubberBand, QSizePolicy, QVBoxLayout, QWidget

from src.shell.strings import ROI_HINT
from src.types import BBox, Frame


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


class PreviewView(QWidget):
    roi_committed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._edit_mode = False
        self._origin: QPoint | None = None
        self._roi = BBox(0.0, 0.0, 1.0, 1.0)
        self._frame_size: QSize | None = None
        self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._label = QLabel(self)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        # 文字覆蓋層：與影像 label 分離，影格持續更新不會清除文字（§4.9）。
        self._overlay = QLabel(self)
        self._overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._overlay.setStyleSheet(
            "background-color: rgba(0, 0, 0, 120); color: white; padding: 4px;"
        )
        self._overlay.hide()

    def set_frame(self, frame: Frame) -> None:
        rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        self._frame_size = QSize(width, height)
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
        self._show_overlay(ROI_HINT if on else "")

    def set_overlay_text(self, text: str) -> None:
        self._show_overlay(text)

    def _show_overlay(self, text: str) -> None:
        if text:
            self._overlay.setText(text)
            self._overlay.setGeometry(self.rect())
            self._overlay.raise_()
            self._overlay.show()
        else:
            self._overlay.clear()
            self._overlay.hide()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())

    def _display_rect(self) -> QRect | None:
        """最近影格以 KeepAspectRatio 置中後的實際顯示矩形（widget 座標）。

        尚未收到影格時回傳 None。
        """
        if self._frame_size is None or self._frame_size.isEmpty():
            return None
        target = self._label.geometry()
        scaled = self._frame_size.scaled(
            target.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        x = target.x() + (target.width() - scaled.width()) // 2
        y = target.y() + (target.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())

    def _roi_from_selection(self, rect: QRect) -> BBox | None:
        """把 widget 座標的框選換算為正規化 ROI（補償留邊，§4.3）。

        完全落在留邊內（或空）的框選回傳 None。
        """
        if rect.isEmpty():
            return None
        display = self._display_rect()
        if display is None:
            # 尚無影格：無留邊可補償，以整個 widget 正規化。
            # 滑鼠拖曳因 Qt mouse grab 可超出 widget 邊界，座標可為負或超界，
            # 必須 clamp，否則寫出 x+w>1 的 ROI 會被下次啟動的驗證拒絕（§4.8）。
            width = max(self.width(), 1)
            height = max(self.height(), 1)
            x0 = _clamp01(rect.x() / width)
            y0 = _clamp01(rect.y() / height)
            x1 = _clamp01((rect.x() + rect.width()) / width)
            y1 = _clamp01((rect.y() + rect.height()) / height)
            if x1 - x0 <= 0.0 or y1 - y0 <= 0.0:
                return None
            return BBox(x=x0, y=y0, w=x1 - x0, h=y1 - y0)
        disp_w = max(display.width(), 1)
        disp_h = max(display.height(), 1)
        x0 = _clamp01((rect.x() - display.x()) / disp_w)
        y0 = _clamp01((rect.y() - display.y()) / disp_h)
        x1 = _clamp01((rect.x() + rect.width() - display.x()) / disp_w)
        y1 = _clamp01((rect.y() + rect.height() - display.y()) / disp_h)
        if x1 - x0 <= 0.0 or y1 - y0 <= 0.0:
            return None
        return BBox(x=x0, y=y0, w=x1 - x0, h=y1 - y0)

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
            roi = self._roi_from_selection(rect)
            if roi is not None:
                self._roi = roi
                self.roi_committed.emit(roi)
        super().mouseReleaseEvent(event)
