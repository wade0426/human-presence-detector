"""設定視窗 v2（自舊 ``src/ui/settings.py`` 移植；CUDA／試聽元件抽至同套件）。

保留舊行為：PathField／SoundPathField／DeviceField 複合欄位、試聽、瀏覽過濾、
§4.7 磁碟基底儲存、驗證錯誤逐欄顯示；改用 v2 schema（含「休息流程」分類與
stage 三欄虛擬鍵）。
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.detection.cuda_check import CudaCheckResult
from src.infra import config as config_module
from src.infra.config import AppConfig, ConfigError, load_config, save_config, validate
from src.shell import strings
from src.shell.reminders.sound import LoopingSoundPlayer
from src.shell.settings.cuda import CudaCheckController, DeviceField, format_cuda_report
from src.shell.settings.preview import PathField, SoundPathField, SoundPreviewController
from src.shell.settings.schema import (
    CATEGORIES,
    SCHEMA,
    STAGE_FIELD_KEYS,
    FieldSpec,
    WidgetKind,
    fields_for,
    get_value,
    set_value,
    tooltip_for,
)

# FR-2.7 / FR-3.1：音檔欄位以 key 清單特判（清單內容由 tests 鎖定）。
SOUND_FIELD_KEYS: tuple[str, ...] = (
    "reminder.popup.sound_path",
    "reminder.return_sound.sound_path",
)

# FR-1.1：運算裝置欄位（下拉選單＋「檢查」按鈕複合 widget）。
DEVICE_FIELD_KEY = "detection.device"

# 驗證錯誤鍵 → 設定頁欄位鍵的別名：stage_after_sec 在 UI 上拆成三個虛擬欄位。
_ERROR_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "rest_flow.escalation.stage_after_sec": tuple(STAGE_FIELD_KEYS),
}


class SettingsWindow(QDialog):
    clear_data_requested = Signal()

    def __init__(
        self,
        config: AppConfig,
        config_path: str = "config.yaml",
        parent: QWidget | None = None,
        *,
        preview_player: LoopingSoundPlayer | None = None,
        cuda_checker: Callable[[], CudaCheckResult] | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._widgets: dict[str, object] = {}
        self._hint_labels: dict[str, QLabel] = {}
        self._hint_texts: dict[str, str] = {}

        # 試聽（FR-3.4、FR-3.7）：單一共享控制器，同時僅允許一個試聽。
        self._preview = SoundPreviewController(player=preview_player, parent=self)
        self._preview.error_occurred.connect(self._set_preview_hint_error)
        self._preview.started.connect(self._clear_preview_hint)

        # CUDA 檢查（FR-1.2、FR-1.5）：純函式 checker 可注入替身測試。
        self._cuda = CudaCheckController(checker=cuda_checker, parent=self)
        self._cuda.result_ready.connect(self._on_cuda_check_finished)

        self.setWindowTitle(strings.SETTINGS_TITLE)
        self.setMinimumSize(640, 480)

        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        self._category_list = QListWidget()
        self._category_list.setFixedWidth(120)
        for category in CATEGORIES:
            self._category_list.addItem(category)

        self._stack = QStackedWidget()
        for category in CATEGORIES:
            self._stack.addWidget(self._build_category_page(category))

        self._category_list.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._category_list.setCurrentRow(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText(strings.SETTINGS_SAVE)
            save_button.setDefault(True)
        if cancel_button is not None:
            cancel_button.setText(strings.SETTINGS_CANCEL)

        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        content_layout = QHBoxLayout()
        content_layout.addWidget(self._category_list)
        content_layout.addWidget(self._stack, stretch=1)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(content_layout)
        main_layout.addWidget(buttons)

        self._wire_source_type_toggle()

    def _build_category_page(self, category: str) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        form = QFormLayout(container)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        for spec in fields_for(category):
            widget = self._make_widget(spec)
            self._widgets[spec.key] = widget

            tooltip = tooltip_for(spec)
            if isinstance(widget, QWidget):
                widget.setToolTip(tooltip)

            hint = QLabel(spec.hint)
            hint.setProperty("role", "secondary")
            hint.setWordWrap(True)
            self._hint_labels[spec.key] = hint
            self._hint_texts[spec.key] = spec.hint

            field_layout = QVBoxLayout()
            field_layout.setSpacing(2)
            if isinstance(widget, QWidget):
                field_layout.addWidget(widget)
            field_layout.addWidget(hint)

            field_container = QWidget()
            field_container.setLayout(field_layout)

            label = QLabel(spec.label)
            label.setToolTip(tooltip)
            form.addRow(label, field_container)

        if category == "紀錄":
            clear_button = QPushButton(strings.CLEAR_DATA_BUTTON)
            clear_button.clicked.connect(self.clear_data_requested.emit)
            form.addRow(clear_button)

        scroll.setWidget(container)
        return scroll

    def _make_widget(self, spec: FieldSpec) -> object:
        if spec.widget == WidgetKind.FLOAT:
            float_widget = QDoubleSpinBox()
            if spec.minimum is not None:
                float_widget.setMinimum(spec.minimum)
            if spec.maximum is not None:
                float_widget.setMaximum(spec.maximum)
            if spec.step is not None:
                float_widget.setSingleStep(spec.step)
            if spec.decimals is not None:
                float_widget.setDecimals(spec.decimals)
            return float_widget

        if spec.widget == WidgetKind.INT:
            int_widget = QSpinBox()
            if spec.minimum is not None:
                int_widget.setMinimum(int(spec.minimum))
            if spec.maximum is not None:
                int_widget.setMaximum(int(spec.maximum))
            return int_widget

        if spec.widget == WidgetKind.CHOICE:
            if spec.key == DEVICE_FIELD_KEY:
                device_field = DeviceField(spec.choices or ())
                device_field.check_requested.connect(self._on_cuda_check_clicked)
                return device_field
            combo_widget = QComboBox()
            if spec.choices is not None:
                combo_widget.addItems(spec.choices)
            return combo_widget

        if spec.widget == WidgetKind.BOOL:
            return QCheckBox()

        if spec.widget == WidgetKind.PATH:
            if spec.key in SOUND_FIELD_KEYS:
                sound_field = SoundPathField()
                self._preview.register(spec.key, sound_field)
                return sound_field
            return PathField()

        return QLineEdit()

    def _populate(self) -> None:
        for spec in SCHEMA:
            widget = self._widgets.get(spec.key)
            if widget is None:
                continue

            value = get_value(self._config, spec.key)
            self._set_widget_value(widget, value)

    def _set_widget_value(self, widget: object, value: object) -> None:
        if isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(str(value)))
        elif isinstance(widget, QSpinBox):
            # 設定值可能是 float（如 stage 門檻 60.0）→ 先轉 float 再取整。
            widget.setValue(int(float(str(value))))
        elif isinstance(widget, QComboBox):
            index = widget.findText(str(value))
            if index >= 0:
                widget.setCurrentIndex(index)
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, PathField):
            widget.line_edit.setText(str(value))
        elif isinstance(widget, DeviceField):
            index = widget.combo.findText(str(value))
            if index >= 0:
                widget.combo.setCurrentIndex(index)

    def _wire_source_type_toggle(self) -> None:
        source_combo = self._widgets.get("source.type")
        if isinstance(source_combo, QComboBox):
            source_combo.currentTextChanged.connect(self._on_source_type_changed)
            self._on_source_type_changed(source_combo.currentText())

    def _on_source_type_changed(self, source_type: str) -> None:
        is_rtsp = source_type == "rtsp"
        for key, enabled in (
            ("source.rtsp_url", is_rtsp),
            ("source.webcam_index", not is_rtsp),
        ):
            widget = self._widgets.get(key)
            if isinstance(widget, QWidget):
                widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # 試聽 hint（FR-3.6；播放控制在 SoundPreviewController）
    # ------------------------------------------------------------------

    def _set_preview_hint_error(self, key: str) -> None:
        self._set_hint(key, strings.SOUND_PREVIEW_ERROR, "danger")

    def _clear_preview_hint(self, key: str) -> None:
        self._set_hint(key, self._hint_texts[key], "secondary")

    def _set_hint(self, key: str, text: str, role: str) -> None:
        hint = self._hint_labels.get(key)
        if hint is None:
            return
        hint.setText(text)
        hint.setProperty("role", role)
        style = hint.style()
        style.unpolish(hint)
        style.polish(hint)

    # ------------------------------------------------------------------
    # GPU CUDA 檢查（FR-1.1～1.5；生命週期在 CudaCheckController）
    # ------------------------------------------------------------------

    def _device_field(self) -> DeviceField | None:
        field = self._widgets.get(DEVICE_FIELD_KEY)
        return field if isinstance(field, DeviceField) else None

    def _on_cuda_check_clicked(self) -> None:
        field = self._device_field()
        if field is None:
            return
        if not self._cuda.start():
            return  # FR-1.2：防重入（檢查進行中再點無效）
        field.set_checking(True)

    def _on_cuda_check_finished(self, result: object) -> None:
        field = self._device_field()
        if field is not None:
            field.set_checking(False)
        if isinstance(result, CudaCheckResult):
            QMessageBox.information(self, strings.CUDA_CHECK_TITLE, format_cuda_report(result))

    def _cancel_cuda_check(self) -> None:
        """視窗關閉時取消進行中的檢查：復原按鈕並使遲到結果被忽略。"""
        if not self._cuda.running:
            return
        self._cuda.cancel()
        field = self._device_field()
        if field is not None:
            field.set_checking(False)

    def done(self, result: int) -> None:
        # FR-3.5：設定視窗關閉（儲存或取消）時自動停止試聽。
        self._preview.stop()
        self._cancel_cuda_check()
        super().done(result)

    # ------------------------------------------------------------------
    # 儲存
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        candidate = self._read_widgets_to_config()
        raw = config_module._serialize_app_config(candidate)
        errors = validate(raw)
        if errors:
            self._show_validation_errors(errors)
            return

        save_config(candidate, self._config_path)
        self._config = candidate
        QMessageBox.information(self, strings.SETTINGS_TITLE, strings.SETTINGS_SAVED_RESTART)
        self.accept()

    def _read_widgets_to_config(self) -> AppConfig:
        # §4.7：以磁碟上的最新 config 為基底，SCHEMA 外的欄位（如 presence.roi）
        # 才不會被啟動時注入的舊值覆寫；磁碟讀取失敗時退回啟動注入值。
        try:
            cfg = load_config(self._config_path)
        except ConfigError:
            cfg = self._config
        for spec in SCHEMA:
            widget = self._widgets.get(spec.key)
            if widget is None:
                continue
            value = self._get_widget_value(widget, spec)
            if value is not None:
                cfg = set_value(cfg, spec.key, value)
        return cfg

    def _get_widget_value(self, widget: object, spec: FieldSpec) -> object | None:
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, PathField):
            return widget.line_edit.text()
        if isinstance(widget, DeviceField):
            return widget.combo.currentText()
        return None

    def _show_validation_errors(self, errors: list[str]) -> None:
        for key in self._hint_labels:
            self._set_hint(key, self._hint_texts[key], "secondary")

        for error in errors:
            key_prefix = error.split(" ")[0]
            for field_key in self._error_field_keys(key_prefix):
                self._set_hint(field_key, error, "danger")

    def _error_field_keys(self, key_prefix: str) -> tuple[str, ...]:
        """驗證錯誤鍵 → 設定頁欄位鍵（stage_after_sec 對映三個虛擬欄位）。"""
        aliases = _ERROR_KEY_ALIASES.get(key_prefix)
        if aliases is not None:
            return tuple(key for key in aliases if key in self._hint_labels)
        return tuple(
            field_key for field_key in self._hint_labels if field_key.startswith(key_prefix)
        )
