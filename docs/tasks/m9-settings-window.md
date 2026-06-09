# M9 `src/ui/settings.py` — 設定視窗重構

**目標**：以側邊欄分類 + 資料驅動表單實作完整設定頁（FR-1 全項）。

**涉及檔案**：
- 重構：`src/ui/settings.py`（刪除 `SettingsDialog`，新增 `SettingsWindow`）
- 修改：`tests/test_ui.py`（更新對應測試）

**相依**：M1（validate/save）、M2（schema/讀寫）、M3（文案）、M8（主題繼承）。

**前置條件**：M1、M2、M3 需先完成。

---

## 任務清單

- [ ] **1. 清理 `settings.py`：移除舊的 `SettingsDialog`**

  保留 import 區塊的必要項目，刪除整個 `SettingsDialog` 類別。

- [ ] **2. 實作 `SettingsWindow` 骨架（版面結構）**

  ```python
  from __future__ import annotations
  from PySide6.QtWidgets import (
      QDialog, QHBoxLayout, QVBoxLayout, QListWidget,
      QStackedWidget, QDialogButtonBox, QWidget,
  )
  from PySide6.QtCore import Qt
  from src.config import AppConfig, validate, save_config
  from src.ui.settings_schema import CATEGORIES, fields_for, get_value, set_value
  from src.ui import strings

  class SettingsWindow(QDialog):
      def __init__(
          self,
          config: AppConfig,
          config_path: str = "config.yaml",
          parent: QWidget | None = None,
      ) -> None:
          super().__init__(parent)
          self._config = config
          self._config_path = config_path
          self.setWindowTitle(strings.SETTINGS_TITLE)
          self.setMinimumSize(640, 480)
          self._widgets: dict[str, object] = {}   # key → Qt 控制項
          self._hint_labels: dict[str, object] = {}  # key → QLabel
          self._build_ui()
          self._populate()
  ```

- [ ] **3. 實作 `_build_ui()`：左右分割版面**

  ```python
  def _build_ui(self) -> None:
      layout = QHBoxLayout(self)
      self._category_list = QListWidget()
      self._category_list.setFixedWidth(120)
      for cat in CATEGORIES:
          self._category_list.addItem(cat)
      self._stack = QStackedWidget()
      for cat in CATEGORIES:
          page = self._build_category_page(cat)
          self._stack.addWidget(page)
      self._category_list.currentRowChanged.connect(self._stack.setCurrentIndex)
      self._category_list.setCurrentRow(0)
      left_panel = QVBoxLayout()
      left_panel.addWidget(self._category_list)
      content_layout = QHBoxLayout()
      content_layout.addLayout(left_panel)
      content_layout.addWidget(self._stack, stretch=1)
      buttons = QDialogButtonBox(
          QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
      )
      buttons.button(QDialogButtonBox.StandardButton.Save).setText(strings.SETTINGS_SAVE)
      buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(strings.SETTINGS_CANCEL)
      buttons.accepted.connect(self._on_save)
      buttons.rejected.connect(self.reject)
      main_layout = QVBoxLayout()
      main_layout.addLayout(content_layout)
      main_layout.addWidget(buttons)
      self.setLayout(main_layout)
  ```

- [ ] **4. 實作 `_build_category_page()`：為每個欄位建立控制項**

  ```python
  from PySide6.QtWidgets import (
      QFormLayout, QScrollArea, QDoubleSpinBox, QSpinBox,
      QLineEdit, QComboBox, QCheckBox, QLabel, QPushButton,
      QFileDialog,
  )
  from src.ui.settings_schema import WidgetKind, FieldSpec

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
          w = QDoubleSpinBox()
          if spec.minimum is not None:
              w.setMinimum(spec.minimum)
          if spec.maximum is not None:
              w.setMaximum(spec.maximum)
          if spec.step is not None:
              w.setSingleStep(spec.step)
          if spec.decimals is not None:
              w.setDecimals(spec.decimals)
          return w
      elif spec.widget == WidgetKind.INT:
          w = QSpinBox()
          if spec.minimum is not None:
              w.setMinimum(int(spec.minimum))
          return w
      elif spec.widget == WidgetKind.CHOICE:
          w = QComboBox()
          if spec.choices:
              w.addItems(spec.choices)
          return w
      elif spec.widget == WidgetKind.BOOL:
          return QCheckBox()
      elif spec.widget == WidgetKind.PATH:
          container = QWidget()
          h = __import__("PySide6.QtWidgets", fromlist=["QHBoxLayout"]).QHBoxLayout(container)
          h.setContentsMargins(0, 0, 0, 0)
          line = QLineEdit()
          btn = QPushButton("瀏覽")
          btn.clicked.connect(lambda _, l=line: l.setText(
              QFileDialog.getOpenFileName(self, "選擇檔案")[0] or l.text()
          ))
          h.addWidget(line)
          h.addWidget(btn)
          return container
      else:
          return QLineEdit()
  ```

- [ ] **5. 實作 `_populate()`：依 config 填入初始值**

  ```python
  from src.types import ResetMode

  def _populate(self) -> None:
      for spec in SCHEMA:
          widget = self._widgets.get(spec.key)
          if widget is None:
              continue
          val = get_value(self._config, spec.key)
          # ResetMode → 字串
          if isinstance(val, ResetMode):
              val = val.value
          self._set_widget_value(widget, spec, val)

  def _set_widget_value(self, widget: object, spec: FieldSpec, val: object) -> None:
      from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QLineEdit
      if isinstance(widget, QDoubleSpinBox):
          widget.setValue(float(val))
      elif isinstance(widget, QSpinBox):
          widget.setValue(int(val))
      elif isinstance(widget, QComboBox):
          idx = widget.findText(str(val))
          if idx >= 0:
              widget.setCurrentIndex(idx)
      elif isinstance(widget, QCheckBox):
          widget.setChecked(bool(val))
      elif isinstance(widget, QLineEdit):
          widget.setText(str(val))
  ```

- [ ] **6. 實作來源型別切換（FR-1.7）**

  在 `_build_ui()` 完成後呼叫：
  ```python
  def _wire_source_type_toggle(self) -> None:
      source_combo = self._widgets.get("source.type")
      if source_combo is None:
          return
      from PySide6.QtWidgets import QComboBox
      if isinstance(source_combo, QComboBox):
          source_combo.currentTextChanged.connect(self._on_source_type_changed)
          self._on_source_type_changed(source_combo.currentText())

  def _on_source_type_changed(self, source_type: str) -> None:
      is_rtsp = source_type == "rtsp"
      for key, enabled in [("source.rtsp_url", is_rtsp), ("source.webcam_index", not is_rtsp)]:
          w = self._widgets.get(key)
          if w is not None:
              from PySide6.QtWidgets import QWidget
              if isinstance(w, QWidget):
                  w.setEnabled(enabled)
  ```

  在 `_build_ui()` 最後加 `self._wire_source_type_toggle()`。

- [ ] **7. 實作 `_on_save()`：驗證 + 儲存 + 提示**

  ```python
  from src.config import validate, save_config, _serialize_app_config
  from PySide6.QtWidgets import QMessageBox
  import dataclasses

  def _on_save(self) -> None:
      candidate = self._read_widgets_to_config()
      raw = _serialize_app_config(candidate)
      errors = validate(raw)
      if errors:
          self._show_validation_errors(errors)
          return
      save_config(candidate, self._config_path)
      QMessageBox.information(self, strings.SETTINGS_TITLE, strings.SETTINGS_SAVED_RESTART)
      self.accept()

  def _read_widgets_to_config(self) -> AppConfig:
      cfg = self._config
      from src.ui.settings_schema import SCHEMA
      for spec in SCHEMA:
          w = self._widgets.get(spec.key)
          if w is None:
              continue
          val = self._get_widget_value(w, spec)
          if val is not None:
              cfg = set_value(cfg, spec.key, val)
      return cfg

  def _get_widget_value(self, widget: object, spec: FieldSpec) -> object | None:
      from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QLineEdit
      from src.ui.settings_schema import WidgetKind
      if isinstance(widget, QDoubleSpinBox):
          return widget.value()
      elif isinstance(widget, QSpinBox):
          return widget.value()
      elif isinstance(widget, QComboBox):
          val = widget.currentText()
          if spec.key == "reminder.reset_mode":
              from src.types import ResetMode
              return ResetMode(val)
          return val
      elif isinstance(widget, QCheckBox):
          return widget.isChecked()
      elif isinstance(widget, QLineEdit):
          return widget.text()
      return None

  def _show_validation_errors(self, errors: list[str]) -> None:
      # 重置所有 hint 標籤
      for hint in self._hint_labels.values():
          hint.setProperty("role", "secondary")
          hint.style().unpolish(hint)
          hint.style().polish(hint)
      # 依錯誤訊息前綴標記對應欄位
      for error in errors:
          key = error.split(" ")[0]  # 取 dotted key 前綴
          for field_key in self._hint_labels:
              if field_key.startswith(key):
                  hint = self._hint_labels[field_key]
                  hint.setText(error)
                  hint.setProperty("role", "danger")
                  hint.style().unpolish(hint)
                  hint.style().polish(hint)
  ```

- [ ] **8. 新增 / 更新 `tests/test_ui.py` 的 SettingsWindow 測試**

  ```python
  import pytest
  from unittest.mock import patch
  from src.config import AppConfig
  from src.ui.settings import SettingsWindow

  def test_settings_window_initial_values(qtbot, tmp_path):
      cfg = AppConfig()
      win = SettingsWindow(cfg, config_path=str(tmp_path / "cfg.yaml"))
      qtbot.addWidget(win)
      from src.ui.settings_schema import SCHEMA, get_value
      from PySide6.QtWidgets import QDoubleSpinBox
      for spec in SCHEMA:
          w = win._widgets.get(spec.key)
          if w is not None and isinstance(w, QDoubleSpinBox):
              assert w.minimum() == (spec.minimum or 0)

  def test_settings_window_save_invalid_blocks(qtbot, tmp_path):
      cfg = AppConfig()
      cfg_path = str(tmp_path / "cfg.yaml")
      win = SettingsWindow(cfg, config_path=cfg_path)
      qtbot.addWidget(win)
      from PySide6.QtWidgets import QDoubleSpinBox
      w = win._widgets.get("timer.work_threshold_min")
      if isinstance(w, QDoubleSpinBox):
          w.setValue(0.0)   # 無效值（< 0.1）
      win._on_save()
      import os
      assert not os.path.exists(cfg_path)   # 不應寫檔

  def test_settings_window_save_valid_writes_file(qtbot, tmp_path):
      cfg = AppConfig()
      cfg_path = str(tmp_path / "cfg.yaml")
      win = SettingsWindow(cfg, config_path=cfg_path)
      qtbot.addWidget(win)
      with patch("PySide6.QtWidgets.QMessageBox.information"):
          win._on_save()
      import os
      assert os.path.exists(cfg_path)

  def test_source_type_toggle(qtbot, tmp_path):
      cfg = AppConfig()
      win = SettingsWindow(cfg, config_path=str(tmp_path / "cfg.yaml"))
      qtbot.addWidget(win)
      from PySide6.QtWidgets import QComboBox
      combo = win._widgets.get("source.type")
      if isinstance(combo, QComboBox):
          combo.setCurrentText("webcam")
          rtsp_w = win._widgets.get("source.rtsp_url")
          from PySide6.QtWidgets import QWidget
          if isinstance(rtsp_w, QWidget):
              assert not rtsp_w.isEnabled()
  ```

- [ ] **9. 執行測試確認通過**

  ```bash
  rtk pytest tests/test_ui.py -k "settings" -v
  ```

- [ ] **10. Commit**

  ```bash
  rtk git add src/ui/settings.py tests/test_ui.py
  rtk git commit -m "feat(M9): 重構設定視窗為側邊欄分類 + 資料驅動表單"
  ```
