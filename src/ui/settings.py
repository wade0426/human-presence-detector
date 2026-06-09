from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.config import AppConfig, save_config


class SettingsDialog(QDialog):
    config_changed = Signal(object)

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("設定")

        self.source_type = QComboBox()
        self.source_type.addItems(["rtsp", "webcam"])
        self.source_type.setCurrentText(config.source.type)
        self.rtsp_url = QLineEdit(config.source.rtsp_url)
        self.webcam_index = QSpinBox()
        self.webcam_index.setValue(config.source.webcam_index)
        self.work_threshold = QDoubleSpinBox()
        self.work_threshold.setValue(config.timer.work_threshold_min)
        self.reset_threshold = QDoubleSpinBox()
        self.reset_threshold.setValue(config.timer.reset_threshold_min)
        self.required_rest = QDoubleSpinBox()
        self.required_rest.setValue(config.timer.required_rest_min)
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.0, 1.0)
        self.confidence.setSingleStep(0.05)
        self.confidence.setValue(config.detection.confidence)
        self.min_box_height_ratio = QDoubleSpinBox()
        self.min_box_height_ratio.setRange(0.0, 1.0)
        self.min_box_height_ratio.setSingleStep(0.05)
        self.min_box_height_ratio.setValue(config.presence.min_box_height_ratio)
        self.debounce_count = QSpinBox()
        self.debounce_count.setMinimum(1)
        self.debounce_count.setValue(config.presence.debounce_count)
        self.reminder_method = QComboBox()
        self.reminder_method.addItems(["popup", "toast", "floating"])
        self.reminder_method.setCurrentText(config.reminder.method)
        self.reset_mode = QComboBox()
        self.reset_mode.addItems(["detection", "dismiss", "snooze"])
        self.reset_mode.setCurrentText(config.reminder.reset_mode.value)
        self.media_path = QLineEdit(config.reminder.popup.media_path)

        form = QFormLayout()
        form.addRow("來源", self.source_type)
        form.addRow("RTSP URL", self.rtsp_url)
        form.addRow("Webcam Index", self.webcam_index)
        form.addRow("工作門檻（分）", self.work_threshold)
        form.addRow("重置門檻（分）", self.reset_threshold)
        form.addRow("休息門檻（分）", self.required_rest)
        form.addRow("信心門檻", self.confidence)
        form.addRow("大小門檻", self.min_box_height_ratio)
        form.addRow("去抖動次數", self.debounce_count)
        form.addRow("提醒方式", self.reminder_method)
        form.addRow("重置模式", self.reset_mode)
        form.addRow("媒體路徑", self.media_path)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _save(self) -> None:
        if self.source_type.currentText() == "rtsp" and not self.rtsp_url.text().strip():
            QMessageBox.warning(self, "設定錯誤", "RTSP 模式需要 URL。")
            return

        updated = replace(
            self._config,
            source=replace(
                self._config.source,
                type=self.source_type.currentText(),
                rtsp_url=self.rtsp_url.text().strip(),
                webcam_index=self.webcam_index.value(),
            ),
            detection=replace(self._config.detection, confidence=self.confidence.value()),
            presence=replace(
                self._config.presence,
                min_box_height_ratio=self.min_box_height_ratio.value(),
                debounce_count=self.debounce_count.value(),
            ),
            timer=replace(
                self._config.timer,
                work_threshold_min=self.work_threshold.value(),
                reset_threshold_min=self.reset_threshold.value(),
                required_rest_min=self.required_rest.value(),
            ),
            reminder=replace(
                self._config.reminder,
                method=self.reminder_method.currentText(),
                reset_mode=self._config.reminder.reset_mode.__class__(self.reset_mode.currentText()),
                popup=replace(
                    self._config.reminder.popup,
                    media_path=self.media_path.text().strip(),
                ),
            ),
        )
        save_config(updated, "config.yaml")
        self.config_changed.emit(updated)
        self.accept()
