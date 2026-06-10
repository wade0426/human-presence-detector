from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from src.app.clear_data import ClearDataService, ClearResult, ClearScope
from src.ui import strings


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
    parent: QWidget,
    service: ClearDataService,
    on_done: Callable[[ClearResult], None],
) -> None:
    from PySide6.QtWidgets import QMessageBox

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
