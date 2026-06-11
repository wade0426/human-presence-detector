from __future__ import annotations

import dataclasses
import inspect
import itertools

import numpy as np
import pytest
from PySide6.QtCore import Qt, QThread

import src.main
from src.app.worker import DetectionWorker
from src.main import _shutdown_worker_thread
from src.presence import PresenceEvaluator
from src.reminder.popup import PopupReminder
from src.reminder.return_prompt import ReturnPromptDialog
from src.timer_engine import TimerEngine
from src.types import BBox, Detection, Frame, ReminderContext, RestCountMode, TimerState


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


class FakeFrames:
    """Live-stream fake：佇列影格各服務一次；耗盡後持續以「新 timestamp」
    重供最後一幀，使串流永不顯得凍結（worker 依 §4.2 以 timestamp 新鮮度
    判斷影格，凍結 timestamp 會被視為過期而跳過偵測）。
    """

    def __init__(self, frames: list[Frame | None], is_opened: bool = True) -> None:
        self._frames = list(frames)
        self._index = 0
        self._is_opened = is_opened

    def latest(self) -> Frame | None:
        if not self._frames:
            return None
        if self._index >= len(self._frames):
            last = self._frames[-1]
            if last is None:
                return None
            return dataclasses.replace(last, timestamp=float(next(_TS_COUNTER)))
        frame = self._frames[self._index]
        self._index += 1
        return frame

    @property
    def is_opened(self) -> bool:
        return self._is_opened


class FakeDetector:
    def __init__(self, detections: list[list[Detection]]) -> None:
        self._detections = list(detections)
        self._index = 0

    def detect(self, frame: Frame) -> list[Detection]:
        del frame
        if self._index >= len(self._detections):
            return self._detections[-1]
        result = self._detections[self._index]
        self._index += 1
        return result


class FakeStore:
    def init_schema(self) -> None:
        return None

    def log_session(
        self, kind: str, start_ts: object, end_ts: object, duration_sec: int, ended_by: str
    ) -> int:
        del kind, start_ts, end_ts, duration_sec, ended_by
        return 1

    def close(self) -> None:
        return None


class FakeClock:
    def __init__(self, start: float = 0.0, step: float = 0.6) -> None:
        self.current = start
        self.step = step

    def __call__(self) -> float:
        value = self.current
        self.current += self.step
        return value


_TS_COUNTER = itertools.count()


def _frame() -> Frame:
    """產生 timestamp 單調遞增的影格（§4.2：凍結 timestamp 視為過期影格）。"""
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    return Frame(image=image, width=10, height=10, timestamp=float(next(_TS_COUNTER)))


def _qualifying_detection() -> Detection:
    return Detection(BBox(0.2, 0.2, 0.3, 0.4), 0.9)


def _make_worker(detector: FakeDetector, *, rest_mode: RestCountMode) -> DetectionWorker:
    return DetectionWorker(
        frames=FakeFrames([_frame() for _ in range(24)]),
        detector=detector,
        presence_evaluator=PresenceEvaluator(BBox(0.0, 0.0, 1.0, 1.0), 0.2, 1),
        timer_engine=TimerEngine(0.5, 5.0, 0.5, 3.0, rest_mode),
        store=FakeStore(),
        detection_interval_sec=0.0,
        reminder_context=ReminderContext(45, "", "image", ""),
        clock=FakeClock(step=0.6),
    )


def _stop_worker_thread(worker: DetectionWorker, thread: QThread) -> None:
    worker.stop()
    thread.quit()
    if not thread.wait(1500):
        thread.terminate()
        thread.wait(500)


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


def test_failed_signal_not_connected_to_quit() -> None:
    source = inspect.getsource(src.main.main)
    assert "worker.failed.connect(lambda _message: app.quit())" not in source


def test_main_imports_new_modules() -> None:
    assert hasattr(src.main, "setup_logging")
    assert hasattr(src.main, "suppress_decoder_noise")
    assert hasattr(src.main, "ThemeManager")


def test_main_uses_request_worker_apis_for_ui_commands() -> None:
    source = inspect.getsource(src.main.main)

    assert "reminder.start_rest.connect(lambda: worker.request_start_rest())" in source
    assert (
        "return_prompt_dialog.confirmed.connect(lambda: worker.request_confirm_return())"
        in source
    )
    assert "window.roi_changed.connect(lambda roi: worker.request_set_roi(roi))" in source
    assert "worker.request_pause()" in source
    assert "worker.request_resume()" in source


@pytest.mark.qt
def test_qthread_return_prompt_confirmed_bridge_starts_new_round(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    no_detect: list[Detection] = []
    detector = FakeDetector([[qd], [qd], no_detect, no_detect, [qd], [qd], [qd], [qd], [qd]])
    worker = _make_worker(detector, rest_mode=RestCountMode.FIXED)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    dialog = ReturnPromptDialog()
    qtbot.addWidget(dialog)
    snapshots: list[object] = []
    worker.timer_updated.connect(snapshots.append)
    worker.return_prompt.connect(dialog.show_prompt)
    dialog.confirmed.connect(lambda: worker.request_confirm_return())

    try:
        thread.start()
        qtbot.waitUntil(dialog.isVisible, timeout=5000)
        marker = len(snapshots)
        qtbot.mouseClick(dialog._confirm_btn, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: any(
                getattr(s, "state", None) == TimerState.WORKING for s in snapshots[marker:]
            ),
            timeout=3000,
        )
        qtbot.waitUntil(
            lambda: any(getattr(s, "work_elapsed_sec", 0.0) > 0 for s in snapshots[marker:]),
            timeout=3000,
        )
    finally:
        _stop_worker_thread(worker, thread)


@pytest.mark.qt
def test_qthread_popup_start_rest_bridge_enters_resting(qtbot: pytest.QtBot) -> None:
    qd = _qualifying_detection()
    detector = FakeDetector([[qd]] * 12)
    worker = _make_worker(detector, rest_mode=RestCountMode.FIXED)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    popup = PopupReminder()
    qtbot.addWidget(popup)
    snapshots: list[object] = []
    worker.timer_updated.connect(snapshots.append)
    worker.reminder_show.connect(popup.show)
    popup.start_rest.connect(lambda: worker.request_start_rest())

    try:
        thread.start()
        qtbot.waitUntil(popup.isVisible, timeout=5000)
        marker = len(snapshots)
        qtbot.mouseClick(popup.dismiss_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: any(
                getattr(s, "state", None) == TimerState.RESTING for s in snapshots[marker:]
            ),
            timeout=3000,
        )
    finally:
        _stop_worker_thread(worker, thread)


# ---------------------------------------------------------------------------
# T8 Tests — §4.6 tray 槽方法接線、§4.11 暫停同步、§4.8 logging_enabled、
#            §4.14 work_minutes float、§4.5 main 端 ConfigError 處理
# ---------------------------------------------------------------------------


def test_worker_signals_connect_to_tray_bound_methods() -> None:
    """§4.6：worker 訊號需連到 TrayIcon 的 QObject bound method，不可用 lambda。"""
    source = inspect.getsource(src.main.main)

    assert "worker.timer_updated.connect(tray.on_timer_updated)" in source
    assert "worker.connection_status.connect(tray.on_connection_status)" in source
    assert "lambda snapshot: tray.set_timer_state" not in source
    assert "lambda status: tray.set_connection" not in source


def test_toggle_pause_syncs_window_and_tray() -> None:
    """§4.11：_toggle_pause 需同步主視窗按鈕與托盤文字（單一事實來源）。"""
    source = inspect.getsource(src.main.main)

    assert "window.set_paused(paused)" in source
    assert "tray.set_paused(paused)" in source


def _cfg_for_build_worker(**overrides: object) -> object:
    from src.config import AppConfig, DetectionConfig

    # device="cpu" 避免 _resolve_device("auto") 匯入 torch 拖慢測試
    return AppConfig(detection=DetectionConfig(device="cpu"), **overrides)


def test_build_worker_passes_logging_enabled_false() -> None:
    """§4.8：_build_worker 需把 cfg.logging.enabled 接到 DetectionWorker。"""
    from src.config import LoggingConfig
    from src.main import _build_worker

    cfg = _cfg_for_build_worker(logging=LoggingConfig(enabled=False))

    worker = _build_worker(cfg, FakeStore(), FakeFrames([]))

    assert worker._logging_enabled is False


def test_build_worker_passes_logging_enabled_true() -> None:
    from src.config import LoggingConfig
    from src.main import _build_worker

    cfg = _cfg_for_build_worker(logging=LoggingConfig(enabled=True))

    worker = _build_worker(cfg, FakeStore(), FakeFrames([]))

    assert worker._logging_enabled is True


def test_build_worker_preserves_fractional_work_minutes() -> None:
    """§4.14：work_threshold_min 不得被 int() 截斷（25.5 分需保留 25.5）。"""
    from src.config import TimerConfig
    from src.main import _build_worker

    cfg = _cfg_for_build_worker(timer=TimerConfig(work_threshold_min=25.5))

    worker = _build_worker(cfg, FakeStore(), FakeFrames([]))

    assert worker._reminder_context.work_minutes == pytest.approx(25.5)


def test_main_malformed_config_exits_nonzero_with_config_error_message(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """§4.5 main 端：畸形 config 啟動需以 stderr 列出錯誤、非零退出、無 traceback。

    結構損壞（非數值）的 roi 仍整檔拒絕；數值越界的 roi 改走 clamp 遷移
    （§4.8 防鎖死，見 tests/test_config.py），不再於啟動時拒絕。
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(  # type: ignore[attr-defined]
        "presence:\n  roi: [bad, 0.2, 0.3, 0.4]\n", encoding="utf-8"
    )

    rc = src.main.main()

    assert rc != 0
    err = capsys.readouterr().err
    assert "presence.roi" in err


def test_main_broken_yaml_exits_nonzero_without_traceback(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """§4.5 審查修正：YAML 語法錯誤也必須以 ConfigError 訊息退出，不得外洩 traceback。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(  # type: ignore[attr-defined]
        "source: [unclosed\n  type: webcam\n", encoding="utf-8"
    )

    rc = src.main.main()

    assert rc != 0
    err = capsys.readouterr().err
    assert "config.yaml" in err


# ---------------------------------------------------------------------------
# INT Tests — _maybe_build_force_lock
# ---------------------------------------------------------------------------


def test_maybe_build_force_lock_returns_none_when_disabled() -> None:
    from src.config import AppConfig, ForceLockConfig
    from src.main import _maybe_build_force_lock

    cfg = AppConfig(force_lock=ForceLockConfig(enabled=False))

    assert _maybe_build_force_lock(cfg) is None


@pytest.mark.qt
def test_maybe_build_force_lock_returns_controller_when_enabled(qtbot: pytest.QtBot) -> None:
    from src.app.force_lock_controller import ForceLockController
    from src.config import AppConfig, ForceLockConfig
    from src.main import _maybe_build_force_lock

    cfg = AppConfig(force_lock=ForceLockConfig(enabled=True))

    controller = _maybe_build_force_lock(cfg)

    assert isinstance(controller, ForceLockController)
