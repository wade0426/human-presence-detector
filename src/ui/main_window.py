from __future__ import annotations

from dataclasses import replace

import cv2
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QCloseEvent, QImage, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from src.app.connection_state import ConnectionState, from_status
from src.config import AppConfig
from src.types import BBox, Frame, TimerSnapshot, TimerState
from src.ui import strings


def _state_text(state: TimerState) -> str:
    return strings.timer_state_text(state)


class PreviewLabel(QLabel):
    roi_selected = Signal(object)

    def __init__(self, roi: BBox, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._roi = roi
        self._drag_start: QPoint | None = None
        self._drag_end: QPoint | None = None
        self.setMinimumSize(500, 400)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)

    def set_roi(self, roi: BBox) -> None:
        self._roi = roi
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self._drag_end = self._drag_start
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None:
            self._drag_end = event.position().toPoint()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None and self._drag_end is not None:
            self._drag_end = event.position().toPoint()
            roi = self._normalized_bbox(self._drag_start, self._drag_end)
            self._roi = roi
            self.roi_selected.emit(roi)
        self._drag_start = None
        self._drag_end = None
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.blue, 2))
        painter.drawRect(self._roi_rect())
        if self._drag_start is not None and self._drag_end is not None:
            painter.setPen(QPen(Qt.GlobalColor.yellow, 2, Qt.PenStyle.DashLine))
            painter.drawRect(QRect(self._drag_start, self._drag_end).normalized())
        painter.end()

    def _roi_rect(self) -> QRect:
        return QRect(
            int(self._roi.x * self.width()),
            int(self._roi.y * self.height()),
            int(self._roi.w * self.width()),
            int(self._roi.h * self.height()),
        )

    def _normalized_bbox(self, start: QPoint, end: QPoint) -> BBox:
        rect = QRect(start, end).normalized()
        width = max(self.width(), 1)
        height = max(self.height(), 1)
        return BBox(
            x=rect.x() / width,
            y=rect.y() / height,
            w=rect.width() / width,
            h=rect.height() / height,
        )


class MainWindow(QMainWindow):
    roi_changed = Signal(object)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._latest_frame: Frame | None = None
        self._status_text = "待機"
        self._timer_text = "00:00"
        self.setWindowTitle("人體辨識休息提醒系統")

        self.preview_label = PreviewLabel(config.presence.roi)
        self.preview_label.roi_selected.connect(self._on_roi_selected)
        self.status_label = QLabel("狀態：待機")
        self.timer_label = QLabel("計時：00:00")
        self.connection_label = QLabel("連線：未連線")

        layout = QVBoxLayout()
        layout.addWidget(self.preview_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.timer_label)
        layout.addWidget(self.connection_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def on_frame_ready(self, frame: Frame) -> None:
        self._latest_frame = frame
        rgb_image = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
        image = QImage(
            rgb_image.data,
            frame.width,
            frame.height,
            rgb_image.strides[0],
            QImage.Format.Format_RGB888,
        )
        pixmap = QPixmap.fromImage(image.copy())
        painter = QPainter(pixmap)
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.drawText(10, 20, f"{self._status_text} {self._timer_text}")
        painter.end()
        self.preview_label.setPixmap(
            pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def on_presence_changed(self, present: bool) -> None:
        if present and self._status_text == "待機":
            self._status_text = "工作中"
            self.status_label.setText("狀態：工作中")

    def on_timer_updated(self, snapshot: TimerSnapshot) -> None:
        self._status_text = _state_text(snapshot.state)
        minutes = int(snapshot.work_elapsed_sec) // 60
        seconds = int(snapshot.work_elapsed_sec) % 60
        self._timer_text = f"{minutes:02d}:{seconds:02d}"
        self.status_label.setText(f"狀態：{self._status_text}")
        self.timer_label.setText(f"計時：{self._timer_text}")

    def on_connection_status(self, status: str | ConnectionState) -> None:
        state = from_status(status) if isinstance(status, str) else status
        text = strings.connection_state_text(state)
        self.connection_label.setText(f"連線：{text}")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.hide()
        event.ignore()

    def _on_roi_selected(self, roi: BBox) -> None:
        self._config = replace(
            self._config,
            presence=replace(self._config.presence, roi=roi),
        )
        self.preview_label.set_roi(roi)
        self.roi_changed.emit(roi)
