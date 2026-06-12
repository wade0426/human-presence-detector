"""T9：設定視窗 v2 — 視窗行為/CUDA 檢查移植回歸/儲存/清除資料（RecordStore 對接）。"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
)

from src.core.events import LedgerEvent, SessionRecord
from src.detection.cuda_check import CudaCheckResult
from src.infra.config import AppConfig, load_config, save_config
from src.infra.store import RecordStore
from src.shell import strings
from src.shell.settings.schema import CATEGORIES, SCHEMA
from src.shell.settings.window import SettingsWindow


def _make_window(qtbot: pytest.QtBot, tmp_path: Path, **kwargs: object) -> SettingsWindow:
    window = SettingsWindow(AppConfig(), config_path=str(tmp_path / "cfg.yaml"), **kwargs)
    qtbot.addWidget(window)
    return window


# ---------------------------------------------------------------------------
# 視窗基本行為（移植 tests/test_ui.py 設定視窗段）
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_settings_window_initial_values(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    window = _make_window(qtbot, tmp_path)
    for spec in SCHEMA:
        widget = window._widgets.get(spec.key)
        if isinstance(widget, QDoubleSpinBox):
            assert widget.minimum() == (spec.minimum or 0)


@pytest.mark.qt
def test_settings_window_save_invalid_blocks(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    # 預設 source.type=rtsp 且 rtsp_url 為空 → 驗證失敗 → 不寫檔
    cfg_path = tmp_path / "cfg.yaml"
    window = SettingsWindow(AppConfig(), config_path=str(cfg_path))
    qtbot.addWidget(window)

    window._on_save()

    assert not os.path.exists(cfg_path)
    hint = window._hint_labels["source.rtsp_url"]
    assert hint.property("role") == "danger"


@pytest.mark.qt
def test_settings_window_save_valid_writes_file(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.yaml"
    window = SettingsWindow(AppConfig(), config_path=str(cfg_path))
    qtbot.addWidget(window)

    combo = window._widgets.get("source.type")
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("webcam")

    with patch("src.shell.settings.window.QMessageBox.information"):
        window._on_save()

    assert os.path.exists(cfg_path)
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert raw["version"] == 2


@pytest.mark.qt
def test_source_type_toggle(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    window = _make_window(qtbot, tmp_path)

    combo = window._widgets.get("source.type")
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("webcam")

    rtsp_widget = window._widgets.get("source.rtsp_url")
    assert isinstance(rtsp_widget, QWidget)
    assert not rtsp_widget.isEnabled()


@pytest.mark.qt
def test_settings_widgets_have_tooltip(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    window = _make_window(qtbot, tmp_path)

    for key in ("reminder.method", "rest_flow.pending_accounting", "timer.rest_count_mode"):
        widget = window._widgets[key]
        assert isinstance(widget, QWidget)
        assert widget.toolTip() != "", f"Widget for {key} has no tooltip"


@pytest.mark.qt
def test_settings_has_rest_flow_page_with_stage_spinboxes(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    """新「休息流程」分類頁存在，且 stage 三欄為 QSpinBox 並載入預設值。"""
    window = _make_window(qtbot, tmp_path)

    assert "休息流程" in CATEGORIES
    expected = {"stage1_sec": 60, "stage2_sec": 120, "stage3_sec": 180}
    for suffix, value in expected.items():
        widget = window._widgets[f"rest_flow.escalation.{suffix}"]
        assert isinstance(widget, QSpinBox)
        assert widget.value() == value


@pytest.mark.qt
def test_save_recombines_stage_columns_into_list(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    """stage 三欄存檔時組回 stage_after_sec list（端到端：widget → yaml → load）。"""
    cfg_path = tmp_path / "cfg.yaml"
    window = SettingsWindow(AppConfig(), config_path=str(cfg_path))
    qtbot.addWidget(window)

    combo = window._widgets["source.type"]
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("webcam")

    for suffix, value in (("stage1_sec", 30), ("stage2_sec", 60), ("stage3_sec", 90)):
        widget = window._widgets[f"rest_flow.escalation.{suffix}"]
        assert isinstance(widget, QSpinBox)
        widget.setValue(value)

    max_stage = window._widgets["rest_flow.escalation.max_stage"]
    assert isinstance(max_stage, QComboBox)
    max_stage.setCurrentText("2")

    with patch("src.shell.settings.window.QMessageBox.information"):
        window._on_save()

    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert raw["rest_flow"]["escalation"]["stage_after_sec"] == [30.0, 60.0, 90.0]
    assert raw["rest_flow"]["escalation"]["max_stage"] == 2

    reloaded = load_config(str(cfg_path))
    assert reloaded.rest_flow.escalation.stage_after_sec == (30.0, 60.0, 90.0)
    assert reloaded.rest_flow.escalation.max_stage == 2


@pytest.mark.qt
def test_save_blocks_non_increasing_stage_columns(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    """三欄非嚴格遞增 → validate 擋下、不寫檔、stage 欄位 hint 標錯。"""
    cfg_path = tmp_path / "cfg.yaml"
    window = SettingsWindow(AppConfig(), config_path=str(cfg_path))
    qtbot.addWidget(window)

    combo = window._widgets["source.type"]
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("webcam")

    for suffix, value in (("stage1_sec", 90), ("stage2_sec", 60), ("stage3_sec", 30)):
        widget = window._widgets[f"rest_flow.escalation.{suffix}"]
        assert isinstance(widget, QSpinBox)
        widget.setValue(value)

    window._on_save()

    assert not os.path.exists(cfg_path)
    hint = window._hint_labels["rest_flow.escalation.stage1_sec"]
    assert hint.property("role") == "danger"


@pytest.mark.qt
def test_settings_has_clear_button(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    window = _make_window(qtbot, tmp_path)

    record_index = list(CATEGORIES).index("紀錄")
    page = window._stack.widget(record_index)
    buttons = [
        b for b in page.findChildren(QPushButton) if b.text() == strings.CLEAR_DATA_BUTTON
    ]
    assert len(buttons) == 1

    with qtbot.waitSignal(window.clear_data_requested, timeout=1000):
        qtbot.mouseClick(buttons[0], Qt.MouseButton.LeftButton)


# ---------------------------------------------------------------------------
# CUDA 檢查（移植 tests/test_settings_schema.py 的 FR-1.x 回歸）
# ---------------------------------------------------------------------------


def _ok_result() -> CudaCheckResult:
    return CudaCheckResult(
        state="ok",
        torch_version="2.9.1+cu128",
        cuda_build_version="12.8",
        cuda_available=True,
        device_count=1,
        devices=("NVIDIA GeForce RTX 5060 Laptop GPU (8.0 GB)",),
        cudnn_version=91002,
        suggested_device="auto",
        error=None,
    )


def _cpu_only_result() -> CudaCheckResult:
    return CudaCheckResult(
        state="cpu_only",
        torch_version="2.9.1+cpu",
        cuda_build_version=None,
        cuda_available=False,
        device_count=0,
        devices=(),
        cudnn_version=None,
        suggested_device="cpu",
        error=None,
    )


@pytest.mark.qt
def test_device_field_has_check_button(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    from src.shell.settings.cuda import DeviceField

    window = _make_window(qtbot, tmp_path)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)
    assert field.check_button.text() == strings.CUDA_CHECK_BUTTON
    items = [field.combo.itemText(i) for i in range(field.combo.count())]
    assert items == ["auto", "cpu", "cuda"]


@pytest.mark.qt
def test_device_field_value_roundtrip(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    from src.shell.settings.cuda import DeviceField

    window = _make_window(qtbot, tmp_path)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)
    assert field.combo.currentText() == AppConfig().detection.device

    spec = next(s for s in SCHEMA if s.key == "detection.device")
    field.combo.setCurrentText("cpu")
    assert window._get_widget_value(field, spec) == "cpu"

    window._set_widget_value(field, "cuda")
    assert field.combo.currentText() == "cuda"


@pytest.mark.qt
def test_cuda_check_disables_button_then_restores(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    from src.shell.settings.cuda import DeviceField

    release = threading.Event()
    calls: list[int] = []

    def checker() -> CudaCheckResult:
        calls.append(1)
        release.wait(5.0)
        return _ok_result()

    window = _make_window(qtbot, tmp_path, cuda_checker=checker)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)

    with patch("src.shell.settings.window.QMessageBox.information") as mock_info:
        field.check_button.click()
        assert not field.check_button.isEnabled()
        assert field.check_button.text() == strings.CUDA_CHECK_RUNNING

        window._on_cuda_check_clicked()  # 防重入：執行中再觸發無效

        release.set()
        qtbot.waitUntil(field.check_button.isEnabled, timeout=5000)
        assert field.check_button.text() == strings.CUDA_CHECK_BUTTON

    assert calls == [1]
    mock_info.assert_called_once()
    args = mock_info.call_args.args
    assert args[1] == strings.CUDA_CHECK_TITLE
    report = args[2]
    assert strings.CUDA_CHECK_OK in report
    assert "RTX 5060" in report
    assert strings.CUDA_SUGGEST.format(device="auto") in report


@pytest.mark.qt
def test_cuda_check_dialog_shows_fail_message(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    from src.shell.settings.cuda import DeviceField

    window = _make_window(qtbot, tmp_path, cuda_checker=_cpu_only_result)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)

    with patch("src.shell.settings.window.QMessageBox.information") as mock_info:
        field.check_button.click()
        qtbot.waitUntil(lambda: mock_info.called, timeout=5000)

    report = mock_info.call_args.args[2]
    assert strings.CUDA_CHECK_FAIL in report
    assert strings.CUDA_SUGGEST.format(device="cpu") in report


@pytest.mark.qt
def test_close_window_ignores_late_cuda_result(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    from src.shell.settings.cuda import DeviceField

    release = threading.Event()

    def checker() -> CudaCheckResult:
        release.wait(5.0)
        return _ok_result()

    window = _make_window(qtbot, tmp_path, cuda_checker=checker)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)

    with patch("src.shell.settings.window.QMessageBox.information") as mock_info:
        field.check_button.click()
        assert not field.check_button.isEnabled()

        window.reject()  # 關閉視窗（done() 路徑）
        release.set()
        qtbot.wait(300)  # 讓遲到結果經 event loop 送達

    assert not mock_info.called
    assert field.check_button.isEnabled()


@pytest.mark.qt
def test_cuda_check_recovers_when_checker_raises(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    from src.shell.settings.cuda import DeviceField

    def checker() -> CudaCheckResult:
        raise RuntimeError("torch exploded")

    window = _make_window(qtbot, tmp_path, cuda_checker=checker)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)

    with patch("src.shell.settings.window.QMessageBox.information") as mock_info:
        field.check_button.click()
        qtbot.waitUntil(field.check_button.isEnabled, timeout=5000)
        assert field.check_button.text() == strings.CUDA_CHECK_BUTTON

    mock_info.assert_called_once()
    report = mock_info.call_args.args[2]
    assert strings.CUDA_CHECK_FAIL in report
    assert "torch exploded" in report
    assert strings.CUDA_SUGGEST.format(device="cpu") in report
    assert window._cuda.running is False


@pytest.mark.qt
def test_late_result_from_cancelled_check_not_misattributed(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    from src.shell.settings.cuda import DeviceField

    lock = threading.Lock()
    calls: list[int] = []
    release_first = threading.Event()
    release_second = threading.Event()

    def checker() -> CudaCheckResult:
        with lock:
            index = len(calls)
            calls.append(index)
        if index == 0:
            release_first.wait(5.0)
            return _ok_result()
        release_second.wait(5.0)
        return _cpu_only_result()

    window = _make_window(qtbot, tmp_path, cuda_checker=checker)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)

    with patch("src.shell.settings.window.QMessageBox.information") as mock_info:
        field.check_button.click()  # 第一次檢查
        window.reject()  # 關閉視窗 → 取消檢查
        window.show()  # 重開視窗
        field.check_button.click()  # 第二次檢查
        assert not field.check_button.isEnabled()

        release_first.set()  # 第一次的遲到結果抵達
        qtbot.wait(300)
        assert not mock_info.called
        assert not field.check_button.isEnabled()
        assert window._cuda.running is True

        release_second.set()
        qtbot.waitUntil(field.check_button.isEnabled, timeout=5000)

    mock_info.assert_called_once()
    report = mock_info.call_args.args[2]
    assert strings.CUDA_CHECK_FAIL in report  # 第二次（cpu_only）的結果
    assert calls == [0, 1]


@pytest.mark.qt
def test_default_cuda_checker_is_check_cuda(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    from src.detection.cuda_check import check_cuda

    window = _make_window(qtbot, tmp_path)
    assert window._cuda.checker is check_cuda


def test_format_cuda_report_covers_four_states() -> None:
    from src.shell.settings.cuda import format_cuda_report

    no_torch = CudaCheckResult(
        state="no_torch",
        torch_version=None,
        cuda_build_version=None,
        cuda_available=False,
        device_count=0,
        devices=(),
        cudnn_version=None,
        suggested_device="cpu",
        error="No module named 'torch'",
    )
    cuda_unavailable = CudaCheckResult(
        state="cuda_unavailable",
        torch_version="2.9.1+cu128",
        cuda_build_version="12.8",
        cuda_available=False,
        device_count=0,
        devices=(),
        cudnn_version=None,
        suggested_device="cpu",
        error=None,
    )

    report_no_torch = format_cuda_report(no_torch)
    assert strings.CUDA_STATE_NO_TORCH in report_no_torch
    assert "No module named 'torch'" in report_no_torch

    report_cpu_only = format_cuda_report(_cpu_only_result())
    assert strings.CUDA_STATE_CPU_ONLY in report_cpu_only
    assert strings.CUDA_BUILD_NONE in report_cpu_only

    report_unavailable = format_cuda_report(cuda_unavailable)
    assert strings.CUDA_STATE_CUDA_UNAVAILABLE in report_unavailable
    assert "12.8" in report_unavailable

    report_ok = format_cuda_report(_ok_result())
    assert strings.CUDA_STATE_OK in report_ok
    assert strings.CUDA_CHECK_OK in report_ok
    assert "NVIDIA GeForce RTX 5060 Laptop GPU (8.0 GB)" in report_ok
    assert strings.CUDA_SUGGEST.format(device="auto") in report_ok


# ---------------------------------------------------------------------------
# 清除資料：服務對接 RecordStore（移植 tests/test_clear_data.py）
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> RecordStore:
    store = RecordStore(str(tmp_path / "records.sqlite"))
    store.init_schema()
    return store


def _work_record(now_ts: float, duration: float = 100.0) -> SessionRecord:
    return SessionRecord(
        kind="work",
        start_ts=now_ts - duration,
        end_ts=now_ts,
        duration_sec=duration,
        ended_by="rest",
    )


def test_clear_today_scope(tmp_path: Path) -> None:
    from src.shell.clear_data import ClearDataService, ClearScope

    store = _make_store(tmp_path)
    service = ClearDataService(store, str(tmp_path / "config.yaml"))

    now_ts = datetime.now().timestamp()
    store.log_session(_work_record(now_ts))
    # 2020-01-01 的舊紀錄（非今日）
    store.log_session(
        SessionRecord(
            kind="work",
            start_ts=1577872800.0,
            end_ts=1577872860.0,
            duration_sec=60.0,
            ended_by="reset",
        )
    )

    result = service.clear(ClearScope.TODAY)

    assert result.deleted == 1
    assert result.reset_config is False
    conn = store._get_connection()
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_clear_all_scope(tmp_path: Path) -> None:
    from src.shell.clear_data import ClearDataService, ClearScope

    store = _make_store(tmp_path)
    service = ClearDataService(store, str(tmp_path / "config.yaml"))

    now_ts = datetime.now().timestamp()
    store.log_session(_work_record(now_ts))
    store.log_session(
        SessionRecord(
            kind="rest", start_ts=now_ts, end_ts=now_ts + 60, duration_sec=60.0, ended_by=""
        )
    )
    store.log_event(LedgerEvent(ts=now_ts, type="escalated", payload={"stage": 1}))

    result = service.clear(ClearScope.ALL)

    assert result.deleted == 3  # sessions + events 合計
    assert result.reset_config is False
    assert store.today_work_seconds() == 0
    assert store.today_rest_count() == 0


def test_clear_all_and_reset_writes_default_v2_config(tmp_path: Path) -> None:
    from src.shell.clear_data import ClearDataService, ClearScope

    store = _make_store(tmp_path)
    config_path = str(tmp_path / "config.yaml")

    custom = AppConfig()
    custom.source.type = "webcam"
    custom.timer.work_threshold_min = 99.0
    save_config(custom, config_path)

    now_ts = datetime.now().timestamp()
    store.log_session(_work_record(now_ts))

    service = ClearDataService(store, config_path)
    result = service.clear(ClearScope.ALL_AND_RESET)

    assert result.reset_config is True
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    assert raw["version"] == 2
    assert raw["timer"]["work_threshold_min"] == AppConfig().timer.work_threshold_min
    assert raw["source"]["type"] == "rtsp"
    assert raw["rest_flow"]["escalation"]["stage_after_sec"] == [60.0, 120.0, 180.0]


# ---------------------------------------------------------------------------
# 清除資料：對話框與互動流程（移植 tests/test_clear_data_dialog.py）
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_dialog_default_scope_is_today(qtbot: pytest.QtBot) -> None:
    from src.shell.clear_data import ClearDataDialog, ClearScope

    dialog = ClearDataDialog()
    qtbot.addWidget(dialog)
    assert dialog.selected_scope() == ClearScope.TODAY


@pytest.mark.qt
def test_dialog_select_all_and_reset(qtbot: pytest.QtBot) -> None:
    from src.shell.clear_data import ClearDataDialog, ClearScope

    dialog = ClearDataDialog()
    qtbot.addWidget(dialog)
    dialog._radio_reset.setChecked(True)
    assert dialog.selected_scope() == ClearScope.ALL_AND_RESET
    assert not dialog._warning_label.isHidden()


@pytest.mark.qt
def test_flow_executes_service_on_confirm(
    qtbot: pytest.QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.shell.clear_data import (
        ClearDataDialog,
        ClearResult,
        ClearScope,
        run_clear_data_flow,
    )

    monkeypatch.setattr(ClearDataDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    class FakeService:
        def __init__(self) -> None:
            self.calls: list[ClearScope] = []

        def clear(self, scope: ClearScope) -> ClearResult:
            self.calls.append(scope)
            return ClearResult(deleted=3, reset_config=False)

    service = FakeService()
    results: list[ClearResult] = []

    run_clear_data_flow(None, service, on_done=results.append)

    assert service.calls == [ClearScope.TODAY]
    assert len(results) == 1
    assert results[0].deleted == 3


@pytest.mark.qt
def test_flow_aborts_on_cancel(qtbot: pytest.QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.shell.clear_data import ClearDataDialog, ClearResult, ClearScope, run_clear_data_flow

    monkeypatch.setattr(ClearDataDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    class FakeService:
        def __init__(self) -> None:
            self.calls: list[ClearScope] = []

        def clear(self, scope: ClearScope) -> ClearResult:
            self.calls.append(scope)
            return ClearResult(deleted=0, reset_config=False)

    service = FakeService()
    results: list[ClearResult] = []

    run_clear_data_flow(None, service, on_done=results.append)

    assert service.calls == []
    assert results == []


# ---------------------------------------------------------------------------
# CudaCheckController._stale_bridges 釋放（quality review #4）
# ---------------------------------------------------------------------------


@pytest.mark.qt
def test_cancelled_check_releases_stale_bridge_when_late_result_arrives(
    qtbot: pytest.QtBot,
) -> None:
    """取消後保活的舊 bridge：遲到結果送達時必須自 _stale_bridges 釋放，
    且不得發出 result_ready（quality review #4：清理分支原為不可達死碼）。"""
    from src.shell.settings.cuda import CudaCheckController

    release = threading.Event()

    def checker() -> CudaCheckResult:
        release.wait(5.0)
        return _ok_result()

    controller = CudaCheckController(checker)
    results: list[object] = []
    controller.result_ready.connect(results.append)

    assert controller.start()
    controller.cancel()
    assert len(controller._stale_bridges) == 1  # 保活引用：等待遲到結果

    release.set()
    qtbot.waitUntil(lambda: not controller._stale_bridges, timeout=5000)

    assert results == []  # 遲到結果被忽略
    assert controller.running is False
