from __future__ import annotations

import signal
import sys

from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from src.app.clear_data import ClearDataService
from src.app.connection_state import from_status
from src.app.force_lock_controller import ForceLockController
from src.app.worker import DetectionWorker
from src.capture.frame_grabber import FrameGrabber
from src.capture.video_source import create_source
from src.config import AppConfig, load_config
from src.detection.detector import PersonDetector
from src.logging_setup import setup_logging, suppress_decoder_noise
from src.logging_store import SessionStore
from src.presence import PresenceEvaluator
from src.reminder.factory import create_reminder
from src.reminder.return_prompt import ReturnPromptDialog
from src.timer_engine import TimerEngine
from src.types import ReminderContext, RestCountMode
from src.ui.clear_data_dialog import run_clear_data_flow
from src.ui.main_window import MainWindow
from src.ui.settings import SettingsWindow
from src.ui.strings import QUIT_CONFIRM_BODY, QUIT_CONFIRM_TITLE
from src.ui.theme import ThemeManager
from src.ui.tray import TrayIcon


def _shutdown_worker_thread(worker: DetectionWorker, thread: QThread) -> None:
    worker.stop()
    thread.quit()
    if not thread.wait(1500):
        thread.terminate()
        thread.wait(500)


def _build_worker(cfg: AppConfig, store: SessionStore, grabber: FrameGrabber) -> DetectionWorker:
    detector = PersonDetector(
        cfg.detection.model_path,
        cfg.detection.confidence,
        cfg.detection.device,
    )
    presence = PresenceEvaluator(
        cfg.presence.roi,
        cfg.presence.min_box_height_ratio,
        cfg.presence.debounce_count,
    )
    timer = TimerEngine(
        cfg.timer.work_threshold_min * 60.0,
        cfg.timer.reset_threshold_min * 60.0,
        cfg.timer.required_rest_min * 60.0,
        cfg.reminder.repeat_interval_min * 60.0,
        RestCountMode(cfg.timer.rest_count_mode),
    )
    reminder_context = ReminderContext(
        work_minutes=int(cfg.timer.work_threshold_min),
        media_path=cfg.reminder.popup.media_path,
        media_type=cfg.reminder.popup.media_type,
        sound_path=cfg.reminder.popup.sound_path,
    )
    return DetectionWorker(
        frames=grabber,
        detector=detector,
        presence_evaluator=presence,
        timer_engine=timer,
        store=store,
        detection_interval_sec=cfg.detection.interval_sec,
        reminder_context=reminder_context,
    )


def _maybe_build_force_lock(cfg: AppConfig) -> ForceLockController | None:
    if not cfg.force_lock.enabled:
        return None
    return ForceLockController(cfg.force_lock)


def main() -> int:
    suppress_decoder_noise()
    setup_logging()
    existing_app = QApplication.instance()
    app = existing_app if isinstance(existing_app, QApplication) else QApplication(sys.argv)
    ThemeManager(app).apply()
    cfg = load_config("config.yaml")
    store = SessionStore(cfg.logging.db_path)

    # M3: FrameGrabber (independent high-frequency capture thread)
    source = create_source(cfg.source)
    grabber = FrameGrabber(source)
    grabber.start()

    worker = _build_worker(cfg, store, grabber)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    window = MainWindow(cfg, store, "config.yaml")
    tray = TrayIcon()
    tray.bind_window(window)
    reminder = create_reminder(cfg.reminder, tray)
    return_prompt_dialog = ReturnPromptDialog(return_sound=cfg.reminder.return_sound)  # Req 1
    settings = SettingsWindow(cfg, "config.yaml", window)

    # Req 2: 清除資料（單一處理器，兩入口共用）
    clear_service = ClearDataService(store, "config.yaml")

    def _run_clear_data() -> None:
        run_clear_data_flow(
            window, clear_service, on_done=lambda _result: window._refresh_base()
        )

    window.clear_data_requested.connect(_run_clear_data)
    settings.clear_data_requested.connect(_run_clear_data)

    # Req 3: 強制鎖定（僅在 enabled 時建立並接線，停用時零額外負擔）
    force_lock_controller = _maybe_build_force_lock(cfg)
    if force_lock_controller is not None:
        worker.timer_updated.connect(force_lock_controller.on_timer_updated)

    # M8: Preview rendered by QTimer (~30fps), pulling latest() from grabber
    preview_timer = QTimer()
    preview_timer.setInterval(33)

    def _on_preview_tick() -> None:
        frame = grabber.latest()
        if frame is not None:
            window.on_frame_ready(frame)

    preview_timer.timeout.connect(_on_preview_tick)
    preview_timer.start()

    # Signal wiring
    worker.presence_changed.connect(window.on_presence_changed)           # Req 1
    worker.timer_updated.connect(window.on_timer_updated)
    worker.timer_updated.connect(lambda snapshot: tray.set_timer_state(snapshot.state))
    worker.connection_status.connect(window.on_connection_status)
    worker.connection_status.connect(lambda status: tray.set_connection(from_status(status)))
    worker.failed.connect(window.on_failed)
    worker.reminder_show.connect(reminder.show)                            # Req 4
    worker.return_prompt.connect(return_prompt_dialog.show_prompt)         # Req 3
    if hasattr(reminder, "start_rest"):
        # PopupReminder only: wire start_rest → worker.start_rest (Req 4)
        reminder.start_rest.connect(lambda: worker.request_start_rest())
    return_prompt_dialog.confirmed.connect(lambda: worker.request_confirm_return())  # Req 3
    window.roi_changed.connect(lambda roi: worker.request_set_roi(roi))

    paused = False

    def _toggle_pause(checked: bool) -> None:
        nonlocal paused
        paused = checked
        if paused:
            worker.request_pause()
            preview_timer.stop()   # Req 5: freeze preview
        else:
            worker.request_resume()
            preview_timer.start()  # Req 5: resume preview
        tray.set_paused(paused)

    def _confirm_quit() -> None:
        """M9 Req 2: Two-step confirmation before quitting."""
        result = QMessageBox.question(
            None,
            QUIT_CONFIRM_TITLE,
            QUIT_CONFIRM_BODY,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            app_instance = QApplication.instance()
            if app_instance is not None:
                app_instance.quit()

    window._actions.request_quit.connect(_confirm_quit)                    # Req 2
    window.request_pause.connect(_toggle_pause)

    tray.settings_action.triggered.connect(settings.show)
    window.request_settings.connect(settings.show)
    tray.toggle_action.triggered.connect(lambda: _toggle_pause(not paused))
    tray.quit_action.triggered.connect(app.quit)

    def _on_about_to_quit() -> None:
        preview_timer.stop()
        grabber.stop()                                     # Req 8: join capture thread
        _shutdown_worker_thread(worker, thread)            # worker 執行緒 finally 關自己的連線
        store.close()                                      # FR-5: 主執行緒關閉自己的 DB 連線

    app.aboutToQuit.connect(_on_about_to_quit)

    signal.signal(signal.SIGINT, lambda *_args: app.quit())
    sigint_pump = QTimer()
    sigint_pump.setInterval(200)
    sigint_pump.timeout.connect(lambda: None)
    sigint_pump.start()

    thread.start()
    tray.show()
    if not cfg.ui.start_minimized:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
