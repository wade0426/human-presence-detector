"""應用程式組裝與進入點（自舊 src/main.py 移植接線並改 v2）。

組裝規則（plan T10）：
- worker↔window↔overlay↔reminders↔tray 全部以 QObject slot 接線、禁 lambda
  （§4.6：worker 訊號連到主執行緒 QObject 的 bound method，PySide6 自動以
  queued connection 送回主執行緒）。
- GUI → worker 方向經 :class:`WorkerCommandBridge`：worker 執行緒被 run()
  迴圈佔住、沒有事件迴圈可消化 queued slot，直接把 GUI 訊號連到 worker 的
  bound method 會排進永不執行的佇列；橋接槽在 GUI 執行緒執行，呼叫的
  request_* 以鎖保護、跨執行緒安全。
- ``lock_requested`` → 覆蓋層先隱 → ``screen_lock.lock_workstation()``（spec §10：
  避免解鎖後殘留全螢幕遮罩）。
- ``device_fallback`` → 托盤氣泡通知（FR-1.6）。
- 清除資料雙入口（主視窗按鈕＋設定頁）共用單一 :class:`ClearDataController`。
- ConfigError 於建 UI 之前攔截：stderr 列錯、非零退出（§4.5 fail fast）。
"""

from __future__ import annotations

import signal
import sys
from dataclasses import dataclass
from types import FrameType
from typing import Protocol

from PySide6.QtCore import QObject, QThread, QTimer, Slot
from PySide6.QtWidgets import QApplication, QMessageBox

from src.capture.frame_grabber import FrameGrabber, FrameProvider
from src.capture.video_source import create_source
from src.core.events import TimerSnapshot, TimerState
from src.core.state_machine import RestFlowMachine
from src.detection.detector import PersonDetector
from src.infra import app_identity, frozen, screen_lock
from src.infra.config import (
    AppConfig,
    ConfigError,
    escalation_policy,
    load_config,
    machine_config,
)
from src.infra.store import RecordStore
from src.logging_setup import setup_logging, suppress_decoder_noise
from src.presence import PresenceEvaluator
from src.shell.clear_data import ClearDataService, ClearResult, run_clear_data_flow
from src.shell.icons import load_app_icon
from src.shell.main_window import MainWindow
from src.shell.overlay import RestCoachOverlay
from src.shell.reminders.context import ReminderContext
from src.shell.reminders.factory import create_reminder
from src.shell.reminders.floating import FloatingReminder
from src.shell.reminders.popup import PopupReminder
from src.shell.reminders.return_prompt import ReturnPromptDialog
from src.shell.reminders.sound import QtSoundPlayer
from src.shell.reminders.toast import ToastReminder
from src.shell.session_events import SessionUnlockWatcher
from src.shell.settings.window import SettingsWindow
from src.shell.strings import (
    CUDA_CHECK_TITLE,
    CUDA_FALLBACK_NOTICE,
    QUIT_CONFIRM_BODY,
    QUIT_CONFIRM_TITLE,
)
from src.shell.theme import ThemeManager
from src.shell.tray import TrayIcon
from src.shell.worker import DetectionWorker
from src.types import BBox, Frame

CONFIG_PATH = "config.yaml"

PREVIEW_INTERVAL_MS = 33  # M8: preview rendered by QTimer (~30fps)

_LOCK_STAGE = 3  # spec §5：第 3 階＝鎖屏（與 core/_LOCK_STAGE、overlay 同值）


class FrameSource(Protocol):
    """組裝端需要的影格來源介面（latest() ＋ 可停止）。"""

    def latest(self) -> Frame | None: ...
    def stop(self) -> None: ...


class _StoppableWorker(Protocol):
    def stop(self) -> None: ...


class SoundPlayerLike(Protocol):
    """EscalationSoundController 的播放器介面（測試可注入替身）。"""

    def play(self, sound_path: str) -> None: ...
    def stop(self) -> None: ...


class _JoinableThread(Protocol):
    def quit(self) -> None: ...
    def wait(self, timeout: int) -> bool: ...
    def terminate(self) -> None: ...


# ---------------------------------------------------------------------------
# QObject 接線控制器（§4.6：全部 bound-method slot，禁 lambda）
# ---------------------------------------------------------------------------


class DeviceFallbackNotifier(QObject):
    """FR-1.6 ＋ §4.6：以 QObject slot 接收 worker 的 device_fallback 訊號。

    worker 在偵測執行緒發訊號；連到主執行緒 QObject 的 bound method 會自動以
    queued connection 送回主執行緒，托盤 UI 操作不會跑在偵測執行緒。
    """

    def __init__(self, tray: TrayIcon) -> None:
        super().__init__()
        self._tray = tray

    @Slot(str)
    def on_device_fallback(self, _device: str) -> None:
        self._tray.showMessage(CUDA_CHECK_TITLE, CUDA_FALLBACK_NOTICE)


class OverlayController(QObject):
    """timer_updated snapshot → RestCoachOverlay（補上 lock_enabled／階梯參數）。"""

    def __init__(
        self,
        overlay: RestCoachOverlay,
        lock_enabled: bool,
        stage_after_sec: tuple[float, float, float],
    ) -> None:
        super().__init__()
        self._overlay = overlay
        self._lock_enabled = lock_enabled
        self._stage_after_sec = stage_after_sec

    @Slot(object)
    def on_timer_updated(self, snapshot: TimerSnapshot) -> None:
        self._overlay.update_from_snapshot(snapshot, self._lock_enabled, self._stage_after_sec)


class EscalationSoundController(QObject):
    """spec §5 階梯音效——僅 REST_PENDING 來源（quality review #1/#6）。

    - stage 0：worker 的 ``rest_pending_entered``（REST_PENDING_ENTERED 事件）
      → 播提示音一次。
    - stage 1+：snapshot 顯示 REST_PENDING 且 1 <= stage < 3 → 立即播一次並以
      QTimer 依 ``repeat_interval`` 重複；離開觸發狀態（離席/取消）、暫停
      （SUSPENDED）或 stage 3（鎖屏將至）即停。啟停由 ``timer_updated``
      snapshot 驅動——暫停恢復與解鎖歸零都自然收斂。
    - REMINDING 來源刻意不啟用：重複提醒音由 popup 負責，不得疊加。
    """

    def __init__(
        self,
        sound_path: str,
        repeat_interval_sec: float,
        player: SoundPlayerLike | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sound_path = sound_path
        self._player: SoundPlayerLike = player if player is not None else QtSoundPlayer(self)
        self.repeat_timer = QTimer(self)
        self.repeat_timer.setInterval(max(1, int(repeat_interval_sec * 1000)))
        self.repeat_timer.timeout.connect(self._on_repeat)

    @Slot()
    def on_rest_pending_entered(self) -> None:
        self._player.play(self._sound_path)

    @Slot(object)
    def on_timer_updated(self, snapshot: TimerSnapshot) -> None:
        active = (
            snapshot.state is TimerState.REST_PENDING
            and 1 <= snapshot.escalation_stage < _LOCK_STAGE
        )
        if active and not self.repeat_timer.isActive():
            self._player.play(self._sound_path)
            self.repeat_timer.start()
        elif not active and self.repeat_timer.isActive():
            self.repeat_timer.stop()
            self._player.stop()

    @Slot()
    def _on_repeat(self) -> None:
        self._player.play(self._sound_path)


class LockController(QObject):
    """lock_requested → 覆蓋層先隱 → 鎖屏（spec §10：避免解鎖後殘留遮罩）。"""

    def __init__(self, overlay: RestCoachOverlay) -> None:
        super().__init__()
        self._overlay = overlay

    @Slot()
    def on_lock_requested(self) -> None:
        self._overlay.hide()
        screen_lock.lock_workstation()


class WorkerCommandBridge(QObject):
    """GUI 訊號 → worker 的執行緒安全 request_*。

    worker 執行緒沒有事件迴圈（run() 迴圈佔住），queued slot 永不消化；
    本橋的槽在 GUI 執行緒執行，直接呼叫以鎖保護的 request_*（等價移植舊
    main.py 的 lambda 接線，依 §4.6 改為 QObject slot）。
    """

    def __init__(self, worker: DetectionWorker) -> None:
        super().__init__()
        self._worker = worker

    @Slot()
    def on_start_rest(self) -> None:
        self._worker.request_start_rest()

    @Slot()
    def on_cancel_pending(self) -> None:
        self._worker.request_cancel_pending()

    @Slot()
    def on_confirm_return(self) -> None:
        self._worker.request_confirm_return()

    @Slot()
    def on_session_unlocked(self) -> None:
        # spec §5「鎖屏後回來」：解鎖 → 階梯歸零重爬（鎖屏仍單週期一次）
        self._worker.request_notify_unlocked()

    @Slot(object)
    def on_roi_changed(self, roi: BBox) -> None:
        self._worker.request_set_roi(roi)


class PauseController(QObject):
    """§4.11：暫停狀態單一事實來源——任一入口切換後同步主視窗與托盤。"""

    def __init__(
        self,
        worker: DetectionWorker,
        window: MainWindow,
        tray: TrayIcon,
        preview_timer: QTimer,
    ) -> None:
        super().__init__()
        self._worker = worker
        self._window = window
        self._tray = tray
        self._preview_timer = preview_timer
        self._paused = False

    @Slot(bool)
    def on_pause_toggled(self, checked: bool) -> None:
        self._paused = checked
        if checked:
            self._worker.request_pause()
            self._preview_timer.stop()  # Req 5: freeze preview
        else:
            self._worker.request_resume()
            self._preview_timer.start()  # Req 5: resume preview
        self._window.set_paused(checked)
        self._tray.set_paused(checked)

    @Slot()
    def on_tray_toggled(self) -> None:
        self.on_pause_toggled(not self._paused)


class PreviewPump(QObject):
    """M8：QTimer ~30fps 由 grabber.latest() 拉最新影格餵 preview。"""

    def __init__(self, grabber: FrameSource, window: MainWindow) -> None:
        super().__init__()
        self._grabber = grabber
        self._window = window

    @Slot()
    def on_tick(self) -> None:
        frame = self._grabber.latest()
        if frame is not None:
            self._window.on_frame_ready(frame)


class ClearDataController(QObject):
    """Req 2：清除資料單一處理器（主視窗與設定頁雙入口共用）。"""

    def __init__(self, window: MainWindow, service: ClearDataService) -> None:
        super().__init__()
        self._window = window
        self._service = service

    @Slot()
    def on_clear_data_requested(self) -> None:
        run_clear_data_flow(self._window, self._service, on_done=self._on_done)

    def _on_done(self, _result: ClearResult) -> None:
        self._window.refresh_base()


class QuitController(QObject):
    """M9 Req 2：主視窗離開鈕需二段確認；托盤「結束」直接退出。"""

    @Slot()
    def on_quit_requested(self) -> None:
        result = QMessageBox.question(
            None,
            QUIT_CONFIRM_TITLE,
            QUIT_CONFIRM_BODY,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._quit()

    @Slot()
    def on_quit(self) -> None:
        self._quit()

    @staticmethod
    def _quit() -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()


class ShutdownController(QObject):
    """aboutToQuit：停 preview → join 擷取執行緒 → 關 worker 執行緒 → 關主執行緒 DB。"""

    def __init__(
        self,
        preview_timer: QTimer,
        grabber: FrameSource,
        worker: DetectionWorker,
        thread: QThread,
        store: RecordStore,
    ) -> None:
        super().__init__()
        self._preview_timer = preview_timer
        self._grabber = grabber
        self._worker = worker
        self._thread = thread
        self._store = store

    @Slot()
    def on_about_to_quit(self) -> None:
        self._preview_timer.stop()
        self._grabber.stop()  # Req 8: join capture thread
        _shutdown_worker_thread(self._worker, self._thread)  # worker finally 關自己的連線
        self._store.close()  # FR-5: 主執行緒關閉自己的 DB 連線


def _shutdown_worker_thread(worker: _StoppableWorker, thread: _JoinableThread) -> None:
    worker.stop()
    thread.quit()
    if not thread.wait(1500):
        thread.terminate()
        thread.wait(500)


# ---------------------------------------------------------------------------
# 建構與組裝
# ---------------------------------------------------------------------------


def _build_worker(cfg: AppConfig, store: object, frames: FrameProvider) -> DetectionWorker:
    detector = PersonDetector(
        cfg.detection.model_path,
        cfg.detection.confidence,
        cfg.detection.device,
    )
    presence = PresenceEvaluator(
        cfg.presence.roi,
        cfg.detection.min_box_height_ratio,  # v2：min_box_height_ratio 移到 detection 區段
        cfg.presence.debounce_count,
    )
    machine = RestFlowMachine(machine_config(cfg), escalation_policy(cfg))
    reminder_context = ReminderContext(
        # §4.14: keep fractional minutes (no int() truncation).
        work_minutes=cfg.timer.work_threshold_min,
        media_path=cfg.reminder.popup.media_path,
        media_type=cfg.reminder.popup.media_type,
        sound_path=cfg.reminder.popup.sound_path,
    )
    return DetectionWorker(
        frames=frames,
        detector=detector,
        presence_evaluator=presence,
        machine=machine,
        store=store,
        detection_interval_sec=cfg.detection.interval_sec,
        reminder_context=reminder_context,
        logging_enabled=cfg.logging.enabled,  # §4.8: honour the logging.enabled setting
    )


@dataclass
class AppAssembly:
    """組裝完成的全部物件（持有 QObject 引用避免被 GC）。"""

    window: MainWindow
    tray: TrayIcon
    settings: SettingsWindow
    overlay: RestCoachOverlay
    reminder: PopupReminder | ToastReminder | FloatingReminder
    return_prompt: ReturnPromptDialog
    worker: DetectionWorker
    thread: QThread
    preview_timer: QTimer
    overlay_controller: OverlayController
    escalation_sound: EscalationSoundController
    lock_controller: LockController
    unlock_watcher: SessionUnlockWatcher
    command_bridge: WorkerCommandBridge
    pause_controller: PauseController
    preview_pump: PreviewPump
    clear_controller: ClearDataController
    quit_controller: QuitController
    fallback_notifier: DeviceFallbackNotifier
    shutdown: ShutdownController


def assemble(
    cfg: AppConfig,
    *,
    store: RecordStore,
    grabber: FrameSource,
    worker: DetectionWorker,
    config_path: str = CONFIG_PATH,
) -> AppAssembly:
    """建構全部 UI 物件並完成接線；不啟動任何執行緒/計時器、不顯示視窗。"""
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    window = MainWindow(cfg, store, config_path)
    tray = TrayIcon()
    tray.bind_window(window)
    reminder = create_reminder(
        cfg.reminder, tray, rest_count_mode=cfg.timer.rest_count_mode
    )
    return_prompt = ReturnPromptDialog(return_sound=cfg.reminder.return_sound)  # Req 1
    settings = SettingsWindow(cfg, config_path, window)
    overlay = RestCoachOverlay()

    overlay_controller = OverlayController(
        overlay,
        lock_enabled=cfg.rest_flow.escalation.max_stage >= 3,
        stage_after_sec=cfg.rest_flow.escalation.stage_after_sec,
    )
    # spec §5 階梯音效：stage 0 一次＋stage 1+ 重複（REST_PENDING 來源限定）
    escalation_sound = EscalationSoundController(
        sound_path=cfg.reminder.popup.sound_path,
        repeat_interval_sec=cfg.reminder.repeat_interval_min * 60.0,
    )
    lock_controller = LockController(overlay)
    # spec §5「鎖屏後回來」：解鎖偵測（非 Windows / 註冊失敗時安靜降級）
    unlock_watcher = SessionUnlockWatcher()
    command_bridge = WorkerCommandBridge(worker)
    fallback_notifier = DeviceFallbackNotifier(tray)
    quit_controller = QuitController()

    preview_timer = QTimer()
    preview_timer.setInterval(PREVIEW_INTERVAL_MS)
    preview_pump = PreviewPump(grabber, window)
    preview_timer.timeout.connect(preview_pump.on_tick)

    pause_controller = PauseController(worker, window, tray, preview_timer)

    # Req 2: 清除資料（單一處理器，兩入口共用）
    clear_controller = ClearDataController(window, ClearDataService(store, config_path))
    window.clear_data_requested.connect(clear_controller.on_clear_data_requested)
    settings.clear_data_requested.connect(clear_controller.on_clear_data_requested)

    # worker → 主執行緒 QObject slots（§4.6：自動 queued 回 GUI 執行緒）
    worker.presence_changed.connect(window.on_presence_changed)  # Req 1
    worker.timer_updated.connect(window.on_timer_updated)
    worker.timer_updated.connect(tray.on_timer_updated)
    worker.timer_updated.connect(overlay_controller.on_timer_updated)
    worker.timer_updated.connect(escalation_sound.on_timer_updated)
    worker.rest_pending_entered.connect(escalation_sound.on_rest_pending_entered)
    worker.connection_status.connect(window.on_connection_status)
    worker.connection_status.connect(tray.on_connection_status)
    worker.failed.connect(window.on_failed)
    # FR-1.6: CUDA fallback 通知（偵測執行緒 → queued → 主執行緒 → 托盤氣泡）。
    worker.device_fallback.connect(fallback_notifier.on_device_fallback)
    worker.reminder_show.connect(reminder.show)  # Req 4
    worker.return_prompt.connect(return_prompt.show_prompt)  # Req 3
    worker.lock_requested.connect(lock_controller.on_lock_requested)  # spec §5 stage 3

    # GUI → worker（經 bridge 呼叫 thread-safe request_*）
    if isinstance(reminder, PopupReminder):
        reminder.start_rest.connect(command_bridge.on_start_rest)  # Req 4
    return_prompt.confirmed.connect(command_bridge.on_confirm_return)  # Req 3
    overlay.cancel_requested.connect(command_bridge.on_cancel_pending)
    # quality review #3：全螢幕遮罩擋住 popup 的開始休息鈕——覆蓋層自備出口，
    # 與 popup.start_rest 走同一路徑（按下即進 REST_PENDING、階梯歸零）
    overlay.start_rest_requested.connect(command_bridge.on_start_rest)
    window.roi_changed.connect(command_bridge.on_roi_changed)
    # 解鎖回來 → core 階梯歸零（spec §5/§10，quality review #2/#7）
    unlock_watcher.unlocked.connect(command_bridge.on_session_unlocked)

    # 暫停雙入口（§4.11）與視窗開啟
    window.request_pause.connect(pause_controller.on_pause_toggled)
    tray.toggle_action.triggered.connect(pause_controller.on_tray_toggled)
    window.request_settings.connect(settings.show)
    tray.settings_action.triggered.connect(settings.show)
    window.request_quit.connect(quit_controller.on_quit_requested)  # Req 2 二段確認
    tray.quit_action.triggered.connect(quit_controller.on_quit)

    shutdown = ShutdownController(preview_timer, grabber, worker, thread, store)

    return AppAssembly(
        window=window,
        tray=tray,
        settings=settings,
        overlay=overlay,
        reminder=reminder,
        return_prompt=return_prompt,
        worker=worker,
        thread=thread,
        preview_timer=preview_timer,
        overlay_controller=overlay_controller,
        escalation_sound=escalation_sound,
        lock_controller=lock_controller,
        unlock_watcher=unlock_watcher,
        command_bridge=command_bridge,
        pause_controller=pause_controller,
        preview_pump=preview_pump,
        clear_controller=clear_controller,
        quit_controller=quit_controller,
        fallback_notifier=fallback_notifier,
        shutdown=shutdown,
    )


# ---------------------------------------------------------------------------
# 進入點
# ---------------------------------------------------------------------------


def _noop() -> None:
    """SIGINT pump：讓 Python 直譯器每 200ms 醒來一次以處理訊號。"""


def _install_sigint(app: QApplication) -> None:
    def _handle(_signum: int, _frame: FrameType | None) -> None:
        app.quit()

    signal.signal(signal.SIGINT, _handle)
    pump = QTimer(app)  # 以 app 為 parent 保活
    pump.setInterval(200)
    pump.timeout.connect(_noop)
    pump.start()


def main() -> int:
    # 凍結(PyInstaller)後先把工作目錄切到 exe 資料夾,確保 config.yaml、
    # data/model、data/records.sqlite 等 CWD 相對路徑無論從何處啟動都能解析
    # （開發模式 no-op）。必須早於 load_config 與任何相對路徑存取。
    frozen.chdir_to_bundle()
    suppress_decoder_noise()
    setup_logging()
    # §4.5: 設定錯誤一律以清楚的 ConfigError 訊息呈現並以非零碼退出，
    # 不得讓原始 traceback 外洩；在建 UI 之前先驗證（fail fast）。
    try:
        cfg = load_config(CONFIG_PATH)
    except ConfigError as exc:
        print(f"設定檔錯誤，請修正 {CONFIG_PATH} 後重新啟動：\n{exc}", file=sys.stderr)
        return 1
    # Windows 工作列圖示：在建立 QApplication（與任何視窗）之前設定明確的
    # AppUserModelID，工作列按鈕才會改用下方 setWindowIcon 的圖示，而非沿用
    # python.exe 的預設圖示（非 Windows no-op）。
    app_identity.set_app_user_model_id()
    existing_app = QApplication.instance()
    app = existing_app if isinstance(existing_app, QApplication) else QApplication(sys.argv)
    # §4.15 資產 icon.png：套用到標題列、Alt-Tab、工作列與所有視窗／對話框／
    # 覆蓋層（先前僅托盤設過圖示，主視窗等沿用 Windows 預設）。
    app.setWindowIcon(load_app_icon())
    ThemeManager(app).apply()

    store = RecordStore(cfg.logging.db_path)

    # M3: FrameGrabber (independent high-frequency capture thread)
    source = create_source(cfg.source)
    grabber = FrameGrabber(source)
    grabber.start()

    worker = _build_worker(cfg, store, grabber)
    assembly = assemble(
        cfg, store=store, grabber=grabber, worker=worker, config_path=CONFIG_PATH
    )

    app.aboutToQuit.connect(assembly.shutdown.on_about_to_quit)
    app.aboutToQuit.connect(assembly.unlock_watcher.stop)
    _install_sigint(app)

    assembly.unlock_watcher.start()  # spec §5：解鎖回來 → 階梯歸零（非 Windows no-op）
    assembly.preview_timer.start()
    assembly.thread.start()
    assembly.tray.show()
    if not cfg.ui.start_minimized:
        assembly.window.show()
    return app.exec()
