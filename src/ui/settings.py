from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
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

from src import config as config_module
from src.config import AppConfig, save_config, validate
from src.ui import strings
from src.ui.settings_schema import (
    CATEGORIES,
    SCHEMA,
    FieldSpec,
    WidgetKind,
    fields_for,
    get_value,
    set_value,
)


class PathField(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.line_edit = QLineEdit()
        self.browse_button = QPushButton("瀏覽")
        self.browse_button.clicked.connect(self._browse)

        layout.addWidget(self.line_edit)
        layout.addWidget(self.browse_button)

    def _browse(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(self, "選擇檔案")
        if chosen:
            self.line_edit.setText(chosen)


class SettingsWindow(QDialog):
    def __init__(
        self,
        config: AppConfig,
        config_path: str | QWidget = "config.yaml",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        resolved_parent = parent
        resolved_path = config_path
        if isinstance(config_path, QWidget):
            resolved_parent = config_path
            resolved_path = "config.yaml"
            super().setParent(resolved_parent)
        self._config = config
        self._config_path = str(resolved_path)
        self._widgets: dict[str, object] = {}
        self._hint_labels: dict[str, QLabel] = {}
        self._hint_texts: dict[str, str] = {}

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
            form.addRow(spec.label, field_container)

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
            combo_widget = QComboBox()
            if spec.choices is not None:
                combo_widget.addItems(spec.choices)
            return combo_widget

        if spec.widget == WidgetKind.BOOL:
            return QCheckBox()

        if spec.widget == WidgetKind.PATH:
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
            widget.setValue(int(str(value)))
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
            value = widget.currentText()
            return value
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, PathField):
            return widget.line_edit.text()
        return None

    def _show_validation_errors(self, errors: list[str]) -> None:
        for key, hint in self._hint_labels.items():
            hint.setText(self._hint_texts[key])
            hint.setProperty("role", "secondary")
            hint.style().unpolish(hint)
            hint.style().polish(hint)

        for error in errors:
            key_prefix = error.split(" ")[0]
            for field_key, hint in self._hint_labels.items():
                if field_key.startswith(key_prefix):
                    hint.setText(error)
                    hint.setProperty("role", "danger")
                    hint.style().unpolish(hint)
                    hint.style().polish(hint)


SettingsDialog = SettingsWindow
