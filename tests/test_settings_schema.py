from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import MINUTE_MAX, MINUTE_MIN, AppConfig
from src.detection.cuda_check import CudaCheckResult
from src.ui.settings_schema import CATEGORIES, SCHEMA, fields_for, get_value, set_value, tooltip_for


def test_fields_for_covers_all_categories() -> None:
    for category in CATEGORIES:
        assert len(fields_for(category)) > 0


def test_get_set_roundtrip() -> None:
    config = AppConfig()
    for spec in SCHEMA:
        original = get_value(config, spec.key)
        restored = set_value(config, spec.key, original)
        assert get_value(restored, spec.key) == original


def test_minute_fields_have_correct_constraints() -> None:
    minute_keys = {
        "timer.work_threshold_min",
        "timer.reset_threshold_min",
        "timer.required_rest_min",
        "reminder.repeat_interval_min",
    }
    for spec in SCHEMA:
        if spec.key in minute_keys:
            assert spec.minimum == MINUTE_MIN
            assert spec.maximum == MINUTE_MAX
            assert spec.step == 0.1
            assert spec.decimals == 1


def test_schema_has_no_reset_mode_field() -> None:
    keys = [spec.key for spec in SCHEMA]
    assert "reminder.reset_mode" not in keys
    assert "reminder.snooze_min" not in keys


def test_schema_has_rest_count_mode() -> None:
    """timer.rest_count_mode should appear with choices (presence, fixed)."""
    from src.ui.settings_schema import WidgetKind

    rest_spec = next((spec for spec in SCHEMA if spec.key == "timer.rest_count_mode"), None)
    assert rest_spec is not None, "SCHEMA must contain timer.rest_count_mode"
    assert rest_spec.widget == WidgetKind.CHOICE
    assert rest_spec.choices == ("presence", "fixed")


def test_set_value_rejects_unsupported_key_depth() -> None:
    config = AppConfig()

    try:
        set_value(config, "reminder.popup.media.path", "clip.mp4")
    except ValueError as exc:
        assert "Unsupported key depth" in str(exc)
    else:
        raise AssertionError("expected ValueError for nested key depth > 3")


# ---------------------------------------------------------------------------
# FR-1 tests: reminder.reminding_display_mode in schema
# ---------------------------------------------------------------------------


def test_schema_has_reminding_display_mode_field() -> None:
    """SCHEMA must contain the reminder.reminding_display_mode entry."""
    keys = [spec.key for spec in SCHEMA]
    assert "reminder.reminding_display_mode" in keys


def test_reminding_display_mode_choices() -> None:
    """reminder.reminding_display_mode choices must be ('overtime', 'work_and_reminder')."""
    from src.ui.settings_schema import WidgetKind

    spec = next(
        (s for s in SCHEMA if s.key == "reminder.reminding_display_mode"), None
    )
    assert spec is not None
    assert spec.widget == WidgetKind.CHOICE
    assert spec.choices == ("overtime", "work_and_reminder")


def test_get_set_reminding_display_mode() -> None:
    """get_value / set_value round-trip for reminder.reminding_display_mode."""
    config = AppConfig()
    original = get_value(config, "reminder.reminding_display_mode")
    assert original == "overtime"

    updated = set_value(config, "reminder.reminding_display_mode", "work_and_reminder")
    assert get_value(updated, "reminder.reminding_display_mode") == "work_and_reminder"

    restored = set_value(updated, "reminder.reminding_display_mode", original)
    assert get_value(restored, "reminder.reminding_display_mode") == original


# ---------------------------------------------------------------------------
# M4 Tests — tooltip_for, new categories, new fields
# ---------------------------------------------------------------------------


def test_every_field_has_hint() -> None:
    for spec in SCHEMA:
        assert spec.hint.strip() != "", f"Field {spec.key} has empty hint"


def test_tooltip_for_falls_back_to_hint() -> None:
    sample = next(spec for spec in SCHEMA if spec.tooltip is None)
    assert tooltip_for(sample) == sample.hint


def test_method_tooltip_mentions_floating() -> None:
    spec = next(spec for spec in SCHEMA if spec.key == "reminder.method")
    tooltip = tooltip_for(spec)
    assert "floating" in tooltip
    assert "角落" in tooltip


def test_categories_contains_force_lock() -> None:
    assert "強制休息" in CATEGORIES


def test_force_lock_fields_exist_in_schema() -> None:
    keys = [spec.key for spec in SCHEMA]
    assert "force_lock.enabled" in keys
    assert "force_lock.trigger" in keys
    assert "force_lock.warning_mode" in keys
    assert "force_lock.overtime_threshold_min" in keys
    assert "force_lock.countdown_sec" in keys


def test_return_sound_fields_exist_in_schema() -> None:
    keys = [spec.key for spec in SCHEMA]
    assert "reminder.return_sound.enabled" in keys
    assert "reminder.return_sound.sound_path" in keys


def test_force_lock_fields_in_correct_category() -> None:
    for spec in SCHEMA:
        if spec.key.startswith("force_lock."):
            assert spec.category == "強制休息", (
                f"Expected '強制休息' for {spec.key}, got {spec.category!r}"
            )


def test_return_sound_fields_in_reminder_category() -> None:
    for spec in SCHEMA:
        if spec.key.startswith("reminder.return_sound."):
            assert spec.category == "提醒", (
                f"Expected '提醒' for {spec.key}, got {spec.category!r}"
            )


def test_fields_for_force_lock_category() -> None:
    fields = fields_for("強制休息")
    assert len(fields) > 0


# ---------------------------------------------------------------------------
# FR-2.7 / FR-3.1 — 音檔欄位以 key 清單特判，於此鎖定清單內容
# ---------------------------------------------------------------------------


def test_sound_field_keys_locked() -> None:
    """SOUND_FIELD_KEYS 必須恰為兩個音檔欄位，且皆為 PATH widget。"""
    from src.ui.settings import SOUND_FIELD_KEYS
    from src.ui.settings_schema import WidgetKind

    assert SOUND_FIELD_KEYS == (
        "reminder.popup.sound_path",
        "reminder.return_sound.sound_path",
    )

    specs = {spec.key: spec for spec in SCHEMA}
    for key in SOUND_FIELD_KEYS:
        assert key in specs, f"SCHEMA must contain {key}"
        assert specs[key].widget == WidgetKind.PATH


# ---------------------------------------------------------------------------
# 需求一 FR-1.1～1.5 — 運算裝置欄位的「檢查」按鈕與背景 CUDA 檢查
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


def _make_window(qtbot: pytest.QtBot, tmp_path: Path, **kwargs: object) -> object:
    from src.ui.settings import SettingsWindow

    window = SettingsWindow(
        AppConfig(), config_path=str(tmp_path / "cfg.yaml"), **kwargs
    )
    qtbot.addWidget(window)
    return window


@pytest.mark.qt
def test_device_field_has_check_button(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    """FR-1.1：運算裝置欄位為「下拉選單＋檢查按鈕」複合 widget。"""
    from src.ui import strings
    from src.ui.settings import DeviceField

    window = _make_window(qtbot, tmp_path)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)
    assert field.check_button.text() == strings.CUDA_CHECK_BUTTON
    items = [field.combo.itemText(i) for i in range(field.combo.count())]
    assert items == ["auto", "cpu", "cuda"]


@pytest.mark.qt
def test_device_field_value_roundtrip(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    """複合 widget 仍需支援 populate（讀值）與儲存（取值）。"""
    from src.ui.settings import DeviceField

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
def test_cuda_check_disables_button_then_restores(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    """FR-1.2：背景執行、按鈕停用顯示「檢查中…」、防重入、完成後復原並彈診斷。"""
    from src.ui import strings
    from src.ui.settings import DeviceField

    release = threading.Event()
    calls: list[int] = []

    def checker() -> CudaCheckResult:
        calls.append(1)
        release.wait(5.0)
        return _ok_result()

    window = _make_window(qtbot, tmp_path, cuda_checker=checker)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)

    with patch("src.ui.settings.QMessageBox.information") as mock_info:
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
    """FR-1.3／1.4：不支援狀態的診斷內容含 FAIL 標題與建議 cpu。"""
    from src.ui import strings
    from src.ui.settings import DeviceField

    window = _make_window(qtbot, tmp_path, cuda_checker=_cpu_only_result)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)

    with patch("src.ui.settings.QMessageBox.information") as mock_info:
        field.check_button.click()
        qtbot.waitUntil(lambda: mock_info.called, timeout=5000)

    report = mock_info.call_args.args[2]
    assert strings.CUDA_CHECK_FAIL in report
    assert strings.CUDA_SUGGEST.format(device="cpu") in report


@pytest.mark.qt
def test_close_window_ignores_late_cuda_result(qtbot: pytest.QtBot, tmp_path: Path) -> None:
    """視窗關閉時忽略遲到的結果：不彈對話框、按鈕仍復原。"""
    from src.ui.settings import DeviceField

    release = threading.Event()

    def checker() -> CudaCheckResult:
        release.wait(5.0)
        return _ok_result()

    window = _make_window(qtbot, tmp_path, cuda_checker=checker)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)

    with patch("src.ui.settings.QMessageBox.information") as mock_info:
        field.check_button.click()
        assert not field.check_button.isEnabled()

        window.reject()  # 關閉視窗（done() 路徑）
        release.set()
        qtbot.wait(300)  # 讓遲到結果經 event loop 送達

    assert not mock_info.called
    assert field.check_button.isEnabled()


@pytest.mark.qt
def test_cuda_check_recovers_when_checker_raises(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    """FR-1.5：checker 拋例外 → finished 仍須發出，按鈕復原、對話框呈現錯誤，
    不得永久卡在「檢查中…」。"""
    from src.ui import strings
    from src.ui.settings import DeviceField

    def checker() -> CudaCheckResult:
        raise RuntimeError("torch exploded")

    window = _make_window(qtbot, tmp_path, cuda_checker=checker)
    field = window._widgets["detection.device"]
    assert isinstance(field, DeviceField)

    with patch("src.ui.settings.QMessageBox.information") as mock_info:
        field.check_button.click()
        qtbot.waitUntil(field.check_button.isEnabled, timeout=5000)
        assert field.check_button.text() == strings.CUDA_CHECK_BUTTON

    mock_info.assert_called_once()
    report = mock_info.call_args.args[2]
    assert strings.CUDA_CHECK_FAIL in report
    assert "torch exploded" in report
    assert strings.CUDA_SUGGEST.format(device="cpu") in report
    assert window._cuda_check_running is False


@pytest.mark.qt
def test_late_result_from_cancelled_check_not_misattributed(
    qtbot: pytest.QtBot, tmp_path: Path
) -> None:
    """取消後重啟檢查：第一次檢查的遲到結果不得被當成第二次的結果
    （按鈕不得提前復原、對話框須呈現第二次的結果）。"""
    from src.ui import strings
    from src.ui.settings import DeviceField

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

    with patch("src.ui.settings.QMessageBox.information") as mock_info:
        field.check_button.click()  # 第一次檢查
        window.reject()  # 關閉視窗 → _cancel_cuda_check
        window.show()  # 重開視窗
        field.check_button.click()  # 第二次檢查
        assert not field.check_button.isEnabled()

        release_first.set()  # 第一次的遲到結果抵達
        qtbot.wait(300)
        # 遲到結果不得復原按鈕、不得彈對話框（防重入語意必須維持）
        assert not mock_info.called
        assert not field.check_button.isEnabled()
        assert window._cuda_check_running is True

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
    assert window._cuda_checker is check_cuda


def test_format_cuda_report_covers_four_states() -> None:
    """FR-1.4：四種狀態的報告各含對應說明與建議值。"""
    from src.ui import strings
    from src.ui.settings import format_cuda_report

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


def test_existing_fields_have_tooltips() -> None:
    keys_with_tooltip = {
        "reminder.method",
        "timer.rest_count_mode",
        "reminder.reminding_display_mode",
        "presence.debounce_count",
        "detection.confidence",
        "presence.min_box_height_ratio",
        "detection.device",
    }
    for spec in SCHEMA:
        if spec.key in keys_with_tooltip:
            assert spec.tooltip is not None and spec.tooltip.strip() != "", (
                f"Field {spec.key} should have a non-empty tooltip"
            )
