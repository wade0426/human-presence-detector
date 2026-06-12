"""T10 組裝測試：assemble() 全物件建構＋接線、ConfigError 退出、main 薄轉發。

接線斷言以行為驗證：直接 emit worker 訊號／UI 訊號，觀察對端效果
（全部 QObject slot 接線；worker 執行緒無事件迴圈，GUI→worker 一律經
WorkerCommandBridge 於 GUI 執行緒呼叫 thread-safe request_*）。
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import numpy as np
import pytest
from PySide6.QtWidgets import QMessageBox

import src.infra.screen_lock as screen_lock_module
import src.main
import src.shell.app as app_module
from src.core.escalation import EscalationPolicy
from src.core.events import TimerSnapshot, TimerState
from src.core.state_machine import MachineConfig, RestFlowMachine
from src.infra.config import AppConfig, DetectionConfig, LoggingConfig, TimerConfig
from src.infra.store import RecordStore
from src.presence import PresenceEvaluator
from src.shell import strings
from src.shell.app import AppAssembly, _build_worker, _shutdown_worker_thread, assemble
from src.shell.reminders.context import ReminderContext
from src.shell.reminders.popup import PopupReminder
from src.shell.tray import TrayIcon
from src.shell.worker import DetectionWorker
from src.types import BBox, Detection, Frame

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

_TS_COUNTER = itertools.count()


def _frame() -> Frame:
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    return Frame(image=image, width=10, height=10, timestamp=float(next(_TS_COUNTER)))


class FakeFrames:
    """FrameProvider＋stop()（assemble 的 FrameSource 介面）。"""

    def __init__(self) -> None:
        self.stop_calls = 0

    def latest(self) -> Frame | None:
        return None

    @property
    def is_opened(self) -> bool:
        return False

    def stop(self) -> None:
        self.stop_calls += 1


class FakeDetector:
    def detect(self, frame: Frame) -> list[Detection]:
        del frame
        return []


def _machine() -> RestFlowMachine:
    cfg = MachineConfig(
        work_threshold_sec=10.0,
        reset_threshold_sec=5.0,
        required_rest_sec=5.0,
        repeat_interval_sec=30.0,
    )
    return RestFlowMachine(cfg, EscalationPolicy((60.0, 120.0, 180.0), 3))


def _make_worker(frames: FakeFrames, store: Any) -> DetectionWorker:
    return DetectionWorker(
        frames=frames,
        detector=FakeDetector(),
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        machine=_machine(),
        store=store,
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(50.0, "", "image", ""),
    )


def snap(
    state: TimerState,
    *,
    work: float = 0.0,
    dwell: float = 0.0,
    stage: int = -1,
) -> TimerSnapshot:
    return TimerSnapshot(
        state=state,
        work_elapsed_sec=work,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=state is TimerState.REMINDING,
        rest_remaining_sec=0.0,
        rest_elapsed_sec=0.0,
        overtime_sec=0.0,
        pending_dwell_sec=dwell,
        escalation_stage=stage,
    )


@pytest.fixture
def assembly(qtbot: QtBot, tmp_path: Any) -> AppAssembly:
    store = RecordStore(str(tmp_path / "records.sqlite"))
    store.init_schema()
    frames = FakeFrames()
    worker = _make_worker(frames, store)
    parts = assemble(
        AppConfig(),
        store=store,
        grabber=frames,
        worker=worker,
        config_path=str(tmp_path / "cfg.yaml"),
    )
    qtbot.addWidget(parts.window)
    qtbot.addWidget(parts.overlay)
    qtbot.addWidget(parts.settings)
    qtbot.addWidget(parts.return_prompt)
    if isinstance(parts.reminder, PopupReminder):
        qtbot.addWidget(parts.reminder)
    return parts


# ---------------------------------------------------------------------------
# 組裝 smoke
# ---------------------------------------------------------------------------


def test_assemble_builds_all_parts_without_starting(assembly: AppAssembly) -> None:
    assert assembly.window is not None
    assert assembly.tray is not None
    assert assembly.settings is not None
    assert assembly.overlay is not None
    assert assembly.return_prompt is not None
    assert not assembly.thread.isRunning()
    assert not assembly.preview_timer.isActive()
    assert not assembly.overlay.isVisible()


def test_assemble_popup_uses_presence_button_text(assembly: AppAssembly) -> None:
    """預設 rest_count_mode=presence → popup 按鈕文案為「開始休息（請離席）」。"""
    assert isinstance(assembly.reminder, PopupReminder)
    assert assembly.reminder.dismiss_button.text() == strings.REMIND_START_REST_PRESENCE


# ---------------------------------------------------------------------------
# REST_PENDING snapshot → 狀態列文字＋overlay 顯示
# ---------------------------------------------------------------------------


def test_rest_pending_snapshot_updates_status_and_shows_overlay(
    assembly: AppAssembly,
) -> None:
    assembly.worker.timer_updated.emit(
        snap(TimerState.REST_PENDING, work=3000.0, dwell=42.0, stage=0)
    )

    assert assembly.window._status._state_label.text() == strings.STATUS_REST_PENDING
    assert "00:42" in assembly.window._status._time_label.text()
    assert assembly.overlay.isVisible()

    assembly.worker.timer_updated.emit(snap(TimerState.RESTING))

    assert not assembly.overlay.isVisible()


# ---------------------------------------------------------------------------
# lock_requested → overlay 先隱 → screen_lock.lock_workstation()
# ---------------------------------------------------------------------------


def test_lock_requested_hides_overlay_before_locking(
    assembly: AppAssembly, monkeypatch: pytest.MonkeyPatch
) -> None:
    overlay_visible_at_lock: list[bool] = []

    def fake_lock() -> bool:
        overlay_visible_at_lock.append(assembly.overlay.isVisible())
        return True

    monkeypatch.setattr(screen_lock_module, "lock_workstation", fake_lock)

    assembly.worker.timer_updated.emit(
        snap(TimerState.REST_PENDING, work=3000.0, dwell=42.0, stage=0)
    )
    assert assembly.overlay.isVisible()

    assembly.worker.lock_requested.emit()

    assert overlay_visible_at_lock == [False]  # spec §10：鎖屏前覆蓋層必須先隱藏
    assert not assembly.overlay.isVisible()


# ---------------------------------------------------------------------------
# 暫停雙入口同步（§4.11）
# ---------------------------------------------------------------------------


def test_pause_dual_entry_syncs_window_tray_and_worker(assembly: AppAssembly) -> None:
    # 入口 1：主視窗暫停按鈕（request_pause 訊號）
    assembly.window.request_pause.emit(True)

    assert assembly.worker._pending_pause is True
    assert assembly.window._actions._pause_btn.isChecked() is True
    assert assembly.tray.toggle_action.text() == strings.TRAY_RESUME
    assert not assembly.preview_timer.isActive()

    # 入口 2：托盤切換（無參數 → 反轉目前狀態）
    assembly.tray.toggle_action.trigger()

    assert assembly.worker._pending_resume is True
    assert assembly.window._actions._pause_btn.isChecked() is False
    assert assembly.tray.toggle_action.text() == strings.TRAY_PAUSE
    assert assembly.preview_timer.isActive()
    assembly.preview_timer.stop()


# ---------------------------------------------------------------------------
# GUI → worker 指令橋（thread-safe request_*）
# ---------------------------------------------------------------------------


def test_return_prompt_confirm_requests_confirm_return(assembly: AppAssembly) -> None:
    assembly.worker.return_prompt.emit()
    assert assembly.return_prompt.isVisible()

    assembly.return_prompt._confirm_btn.click()

    assert assembly.worker._pending_confirm_return is True


def test_popup_start_rest_requests_start_rest(assembly: AppAssembly) -> None:
    assert isinstance(assembly.reminder, PopupReminder)

    assembly.reminder.start_rest.emit()

    assert assembly.worker._pending_start_rest is True


def test_overlay_cancel_requests_cancel_pending(assembly: AppAssembly) -> None:
    assembly.overlay.cancel_requested.emit()

    assert assembly.worker._pending_cancel_pending is True


def test_window_roi_changed_requests_set_roi(assembly: AppAssembly) -> None:
    roi = BBox(0.1, 0.2, 0.3, 0.4)

    assembly.window.roi_changed.emit(roi)

    assert assembly.worker._pending_roi == roi


# ---------------------------------------------------------------------------
# 清除資料雙入口（Req 2：單一處理器）
# ---------------------------------------------------------------------------


def test_clear_data_dual_entry_shares_single_handler(
    assembly: AppAssembly, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Any] = []

    def fake_flow(parent: Any, service: Any, on_done: Any) -> None:
        calls.append(service)

    monkeypatch.setattr(app_module, "run_clear_data_flow", fake_flow)

    assembly.window.clear_data_requested.emit()
    assembly.settings.clear_data_requested.emit()

    assert len(calls) == 2
    assert calls[0] is calls[1]  # 兩入口共用同一 ClearDataService


# ---------------------------------------------------------------------------
# device_fallback → 托盤通知（FR-1.6）
# ---------------------------------------------------------------------------


def test_device_fallback_notifies_via_tray(
    assembly: AppAssembly, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[tuple[str, str]] = []

    def fake_show_message(title: str, body: str) -> None:
        messages.append((title, body))

    monkeypatch.setattr(assembly.tray, "showMessage", fake_show_message)

    assembly.worker.device_fallback.emit("cpu")

    assert messages == [(strings.CUDA_CHECK_TITLE, strings.CUDA_FALLBACK_NOTICE)]


# ---------------------------------------------------------------------------
# reminder_show 接線
# ---------------------------------------------------------------------------


def test_reminder_show_displays_popup(assembly: AppAssembly) -> None:
    assert isinstance(assembly.reminder, PopupReminder)
    ctx = ReminderContext(50.0, "", "image", "", work_elapsed_sec=3000.0)

    assembly.worker.reminder_show.emit(ctx)

    assert assembly.reminder.isVisible()
    assembly.reminder.hide()


# ---------------------------------------------------------------------------
# 離開確認（M9 Req 2）
# ---------------------------------------------------------------------------


def test_quit_declined_does_not_quit(
    assembly: AppAssembly, monkeypatch: pytest.MonkeyPatch
) -> None:
    quit_calls: list[bool] = []
    monkeypatch.setattr(
        app_module.QuitController, "_quit", staticmethod(lambda: quit_calls.append(True))
    )

    with patch(
        "PySide6.QtWidgets.QMessageBox.question",
        return_value=QMessageBox.StandardButton.No,
    ) as question:
        assembly.window.request_quit.emit()

    assert question.call_count == 1
    assert quit_calls == []


def test_quit_confirmed_quits(
    assembly: AppAssembly, monkeypatch: pytest.MonkeyPatch
) -> None:
    quit_calls: list[bool] = []
    monkeypatch.setattr(
        app_module.QuitController, "_quit", staticmethod(lambda: quit_calls.append(True))
    )

    with patch(
        "PySide6.QtWidgets.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        assembly.window.request_quit.emit()

    assert quit_calls == [True]


# ---------------------------------------------------------------------------
# 托盤（移植 §4.6 槽方法慣例）
# ---------------------------------------------------------------------------


def test_tray_on_timer_updated_slot_updates_tooltip(qtbot: QtBot) -> None:
    tray = TrayIcon()

    tray.on_timer_updated(snap(TimerState.REMINDING, work=3000.0))

    assert "提醒中" in tray.toolTip()


def test_tray_on_connection_status_slot_updates_tooltip(qtbot: QtBot) -> None:
    tray = TrayIcon()

    tray.on_connection_status("connected")

    assert "已連線" in tray.toolTip()


def test_tray_set_paused_changes_toggle_text(qtbot: QtBot) -> None:
    tray = TrayIcon()

    tray.set_paused(True)
    assert tray.toggle_action.text() == strings.TRAY_RESUME

    tray.set_paused(False)
    assert tray.toggle_action.text() == strings.TRAY_PAUSE


# ---------------------------------------------------------------------------
# _shutdown_worker_thread（移植）
# ---------------------------------------------------------------------------


class FakeWorker:
    def __init__(self) -> None:
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


class FakeThread:
    def __init__(self, *, wait_result: bool) -> None:
        self.quit_calls = 0
        self.wait_calls: list[int] = []
        self.terminate_calls = 0
        self._wait_result = wait_result

    def quit(self) -> None:
        self.quit_calls += 1

    def wait(self, timeout: int) -> bool:
        self.wait_calls.append(timeout)
        return self._wait_result

    def terminate(self) -> None:
        self.terminate_calls += 1


def test_shutdown_worker_thread_stops_worker_and_quits_thread() -> None:
    worker = FakeWorker()
    thread = FakeThread(wait_result=True)

    _shutdown_worker_thread(worker, thread)

    assert worker.stop_calls == 1
    assert thread.quit_calls == 1
    assert thread.wait_calls == [1500]
    assert thread.terminate_calls == 0


def test_shutdown_worker_thread_terminates_when_thread_does_not_exit() -> None:
    worker = FakeWorker()
    thread = FakeThread(wait_result=False)

    _shutdown_worker_thread(worker, thread)

    assert worker.stop_calls == 1
    assert thread.quit_calls == 1
    assert thread.wait_calls == [1500, 500]
    assert thread.terminate_calls == 1


# ---------------------------------------------------------------------------
# _build_worker（§4.8 logging_enabled、§4.14 work_minutes float）
# ---------------------------------------------------------------------------


class BuildStore:
    def init_schema(self) -> None:
        return None

    def close(self) -> None:
        return None


def _cfg_for_build_worker(**overrides: Any) -> AppConfig:
    # device="cpu" 避免 _resolve_device("auto") 匯入 torch 拖慢測試
    return AppConfig(detection=DetectionConfig(device="cpu"), **overrides)


def test_build_worker_passes_logging_enabled_false() -> None:
    cfg = _cfg_for_build_worker(logging=LoggingConfig(enabled=False))

    worker = _build_worker(cfg, BuildStore(), FakeFrames())

    assert worker._logging_enabled is False


def test_build_worker_passes_logging_enabled_true() -> None:
    cfg = _cfg_for_build_worker(logging=LoggingConfig(enabled=True))

    worker = _build_worker(cfg, BuildStore(), FakeFrames())

    assert worker._logging_enabled is True


def test_build_worker_preserves_fractional_work_minutes() -> None:
    """§4.14：work_threshold_min 不得被 int() 截斷（25.5 分需保留 25.5）。"""
    cfg = _cfg_for_build_worker(timer=TimerConfig(work_threshold_min=25.5))

    worker = _build_worker(cfg, BuildStore(), FakeFrames())

    assert worker._reminder_context.work_minutes == pytest.approx(25.5)


# ---------------------------------------------------------------------------
# ConfigError 友善退出（§4.5）＋ main 薄轉發
# ---------------------------------------------------------------------------


def test_main_malformed_config_exits_nonzero_with_config_error_message(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "version: 2\npresence:\n  roi: [bad, 0.2, 0.3, 0.4]\n", encoding="utf-8"
    )

    rc = app_module.main()

    assert rc != 0
    err = capsys.readouterr().err
    assert "presence.roi" in err


def test_main_broken_yaml_exits_nonzero_without_traceback(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "source: [unclosed\n  type: webcam\n", encoding="utf-8"
    )

    rc = app_module.main()

    assert rc != 0
    err = capsys.readouterr().err
    assert "config.yaml" in err


def test_src_main_forwards_to_shell_app() -> None:
    """src/main.py 薄轉發：`python -m src.main` 入口指向 shell.app.main。"""
    assert src.main.main is app_module.main


# ---------------------------------------------------------------------------
# spec §5 階梯音效（quality review #1/#6）：EscalationSoundController
# ---------------------------------------------------------------------------


class FakeSoundPlayer:
    def __init__(self) -> None:
        self.plays: list[str] = []
        self.stops = 0

    def play(self, sound_path: str) -> None:
        self.plays.append(sound_path)

    def stop(self) -> None:
        self.stops += 1


def test_escalation_sound_plays_once_on_rest_pending_entered(qtbot: QtBot) -> None:
    """stage 0（進入等待離席）：提示音一次，不啟動重複。"""
    player = FakeSoundPlayer()
    ctl = app_module.EscalationSoundController("ding.mp3", 120.0, player=player)

    ctl.on_rest_pending_entered()

    assert player.plays == ["ding.mp3"]
    assert not ctl.repeat_timer.isActive()


def test_escalation_sound_repeats_at_stage1_for_rest_pending_only(qtbot: QtBot) -> None:
    """stage>=1 依 repeat_interval 重複；REMINDING 來源不啟動（popup 已負責）。"""
    player = FakeSoundPlayer()
    ctl = app_module.EscalationSoundController("ding.mp3", 0.01, player=player)

    # REMINDING 來源 stage 1：重複提醒由 popup 播音，階梯音效不得疊加
    ctl.on_timer_updated(snap(TimerState.REMINDING, stage=1))
    assert not ctl.repeat_timer.isActive()

    # REST_PENDING stage 0：尚未到重複階段
    ctl.on_timer_updated(snap(TimerState.REST_PENDING, stage=0))
    assert not ctl.repeat_timer.isActive()

    # REST_PENDING stage 1：立即播一次＋啟動重複
    ctl.on_timer_updated(snap(TimerState.REST_PENDING, stage=1))
    assert ctl.repeat_timer.isActive()
    qtbot.waitUntil(lambda: len(player.plays) >= 3, timeout=3000)


def test_escalation_sound_stops_on_leave_and_at_lock_stage(qtbot: QtBot) -> None:
    player = FakeSoundPlayer()
    ctl = app_module.EscalationSoundController("ding.mp3", 120.0, player=player)

    ctl.on_timer_updated(snap(TimerState.REST_PENDING, stage=1))
    assert ctl.repeat_timer.isActive()
    ctl.on_timer_updated(snap(TimerState.RESTING))  # 離席 → 離開觸發狀態
    assert not ctl.repeat_timer.isActive()
    assert player.stops == 1

    ctl.on_timer_updated(snap(TimerState.REST_PENDING, stage=2))
    assert ctl.repeat_timer.isActive()
    ctl.on_timer_updated(snap(TimerState.REST_PENDING, stage=3))  # 鎖屏將至
    assert not ctl.repeat_timer.isActive()

    # 暫停（SUSPENDED）凍結 → 停；恢復回 REST_PENDING stage>=1 → 續播
    ctl.on_timer_updated(snap(TimerState.REST_PENDING, stage=1))
    ctl.on_timer_updated(snap(TimerState.SUSPENDED, stage=1))
    assert not ctl.repeat_timer.isActive()
    ctl.on_timer_updated(snap(TimerState.REST_PENDING, stage=1))
    assert ctl.repeat_timer.isActive()


def test_assembly_wires_escalation_sound(assembly: AppAssembly) -> None:
    """worker 訊號 → EscalationSoundController 接線（snapshot 啟停＋entered 播放）。"""
    fake = FakeSoundPlayer()
    assembly.escalation_sound._player = fake

    assembly.worker.rest_pending_entered.emit()
    assert len(fake.plays) == 1  # stage 0 提示音一次

    assembly.worker.timer_updated.emit(snap(TimerState.REST_PENDING, dwell=70.0, stage=1))
    assert assembly.escalation_sound.repeat_timer.isActive()

    assembly.worker.timer_updated.emit(snap(TimerState.RESTING))
    assert not assembly.escalation_sound.repeat_timer.isActive()


def test_assembly_escalation_sound_uses_popup_sound_and_repeat_interval(
    assembly: AppAssembly,
) -> None:
    cfg = AppConfig()
    expected_ms = int(cfg.reminder.repeat_interval_min * 60.0 * 1000)
    assert assembly.escalation_sound.repeat_timer.interval() == expected_ms


# ---------------------------------------------------------------------------
# 覆蓋層「開始休息（請離席）」→ start_rest（quality review #3）
# ---------------------------------------------------------------------------


def test_overlay_start_rest_requests_start_rest(assembly: AppAssembly) -> None:
    assembly.overlay.start_rest_requested.emit()

    assert assembly.worker._pending_start_rest is True


# ---------------------------------------------------------------------------
# 解鎖回來 → request_notify_unlocked（quality review #2/#7）
# ---------------------------------------------------------------------------


def test_unlock_watcher_requests_notify_unlocked(assembly: AppAssembly) -> None:
    assembly.unlock_watcher.unlocked.emit()

    assert assembly.worker._pending_notify_unlocked is True
