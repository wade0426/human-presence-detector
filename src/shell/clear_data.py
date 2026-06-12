"""清除資料：服務（對接 v2 RecordStore）＋選項對話框＋互動流程。

自舊 ``src/app/clear_data.py``＋``src/ui/clear_data_dialog.py`` 合併移植：

- :class:`ClearDataService`：``clear_today``／``clear_all``；重設設定時寫入
  v2 預設 :class:`AppConfig`。
- :class:`ClearDataDialog`／:func:`run_clear_data_flow`：三選項對話框與
  確認→執行→結果通知流程。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from src.infra.config import AppConfig, save_config
from src.infra.store import RecordStore
from src.shell import strings


class ClearScope(Enum):
    TODAY = "today"
    ALL = "all"
    ALL_AND_RESET = "all_and_reset"


@dataclass(frozen=True)
class ClearResult:
    deleted: int
    reset_config: bool


class ClearDataService:
    def __init__(self, store: RecordStore, config_path: str) -> None:
        self._store = store
        self._config_path = config_path

    def clear(self, scope: ClearScope) -> ClearResult:
        if scope is ClearScope.TODAY:
            deleted = self._store.clear_today()
            return ClearResult(deleted=deleted, reset_config=False)

        if scope is ClearScope.ALL:
            deleted = self._store.clear_all()
            return ClearResult(deleted=deleted, reset_config=False)

        # ClearScope.ALL_AND_RESET：清空全部並把設定回復為 v2 預設值。
        deleted = self._store.clear_all()
        save_config(AppConfig(), self._config_path)
        return ClearResult(deleted=deleted, reset_config=True)


class ClearDataDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.CLEAR_DATA_TITLE)

        self._radio_today = QRadioButton(strings.CLEAR_SCOPE_TODAY)
        self._radio_all = QRadioButton(strings.CLEAR_SCOPE_ALL)
        self._radio_reset = QRadioButton(strings.CLEAR_SCOPE_RESET)
        self._radio_today.setChecked(True)  # 預設選取今日

        self._button_group = QButtonGroup(self)
        self._button_group.addButton(self._radio_today)
        self._button_group.addButton(self._radio_all)
        self._button_group.addButton(self._radio_reset)

        self._warning_label = QLabel(strings.CLEAR_RESET_WARNING)
        self._warning_label.setProperty("role", "danger")
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)

        self._radio_reset.toggled.connect(self._warning_label.setVisible)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._radio_today)
        layout.addWidget(self._radio_all)
        layout.addWidget(self._radio_reset)
        layout.addWidget(self._warning_label)
        layout.addWidget(buttons)

    def selected_scope(self) -> ClearScope:
        if self._radio_reset.isChecked():
            return ClearScope.ALL_AND_RESET
        if self._radio_all.isChecked():
            return ClearScope.ALL
        return ClearScope.TODAY


def run_clear_data_flow(
    parent: QWidget | None,
    service: ClearDataService,
    on_done: Callable[[ClearResult], None],
) -> None:
    dialog = ClearDataDialog(parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    scope = dialog.selected_scope()

    confirm = QMessageBox.question(
        parent,
        strings.CLEAR_DATA_TITLE,
        strings.CLEAR_CONFIRM_BODY,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if confirm != QMessageBox.StandardButton.Yes:
        return

    result = service.clear(scope)
    QMessageBox.information(
        parent, strings.CLEAR_DATA_TITLE, strings.CLEAR_DONE.format(count=result.deleted)
    )
    if result.reset_config:
        QMessageBox.information(parent, strings.SETTINGS_TITLE, strings.SETTINGS_SAVED_RESTART)

    on_done(result)
