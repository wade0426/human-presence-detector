from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from src.app.clear_data import ClearResult, ClearScope
from src.ui.clear_data_dialog import ClearDataDialog, run_clear_data_flow


class FakeClearDataService:
    def __init__(self) -> None:
        self.calls: list[ClearScope] = []
        self._result = ClearResult(deleted=3, reset_config=False)

    def clear(self, scope: ClearScope) -> ClearResult:
        self.calls.append(scope)
        return self._result


@pytest.mark.qt
def test_dialog_default_scope_is_today(qtbot) -> None:
    dialog = ClearDataDialog()
    qtbot.addWidget(dialog)
    assert dialog.selected_scope() == ClearScope.TODAY


@pytest.mark.qt
def test_dialog_select_all_and_reset(qtbot) -> None:
    dialog = ClearDataDialog()
    qtbot.addWidget(dialog)
    dialog._radio_reset.setChecked(True)
    assert dialog.selected_scope() == ClearScope.ALL_AND_RESET
    assert not dialog._warning_label.isHidden()


@pytest.mark.qt
def test_flow_executes_service_on_confirm(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(ClearDataDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    service = FakeClearDataService()
    results: list[ClearResult] = []

    run_clear_data_flow(None, service, on_done=results.append)

    assert len(service.calls) == 1
    assert service.calls[0] == ClearScope.TODAY
    assert len(results) == 1
    assert results[0].deleted == 3


@pytest.mark.qt
def test_flow_aborts_on_cancel(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(ClearDataDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    service = FakeClearDataService()
    results: list[ClearResult] = []

    run_clear_data_flow(None, service, on_done=results.append)

    assert service.calls == []
    assert results == []
