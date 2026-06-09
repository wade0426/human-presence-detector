from __future__ import annotations

import signal
import sys

from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication

from src.app.connection_state import from_status
from src.app.worker import DetectionWorker
from src.capture.video_source import create_source
from src.config import AppConfig, load_config
from src.detection.detector import PersonDetector
from src.logging_setup import setup_logging, suppress_decoder_noise
from src.logging_store import SessionStore
from src.presence import PresenceEvaluator
from src.reminder.factory import create_reminder
from src.timer_engine import TimerEngine
from src.types import ReminderContext
from src.ui.main_window import MainWindow
from src.ui.settings import SettingsWindow
from src.ui.theme import ThemeManager
from src.ui.tray import TrayIcon


def _shutdown_worker_thread(worker: DetectionWorker, thread: QThread) -> None:
    worker.stop()
    thread.quit()
    if not thread.wait(1500):
        thread.terminate()
        thread.wait(500)


def _build_worker(cfg: AppConfig, store: SessionStore) -> DetectionWorker:
    source = create_source(cfg.source)
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
        cfg.reminder.reset_mode,
        cfg.reminder.repeat_interval_min * 60.0,
        cfg.reminder.snooze_min * 60.0,
    )
    reminder_context = ReminderContext(
        work_minutes=int(cfg.timer.work_threshold_min),
        media_path=cfg.reminder.popup.media_path,
        media_type=cfg.reminder.popup.media_type,
        sound_path=cfg.reminder.popup.sound_path,
        reset_mode=cfg.reminder.reset_mode.value,
        snooze_minutes=int(cfg.reminder.snooze_min),
    )
    return DetectionWorker(
        source=source,
        detector=detector,
        presence_evaluator=presence,
        timer_engine=timer,
        store=store,
        detection_interval_sec=cfg.detection.interval_sec,
        reminder_context=reminder_context,
    )


def main() -> int:
    suppress_decoder_noise()
    setup_logging()
    existing_app = QApplication.instance()
    app = existing_app if isinstance(existing_app, QApplication) else QApplication(sys.argv)
    ThemeManager(app).apply()
    cfg = load_config("config.yaml")
    store = SessionStore(cfg.logging.db_path)

    worker = _build_worker(cfg, store)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    window = MainWindow(cfg, store, "config.yaml")
    tray = TrayIcon()
    tray.bind_window(window)
    reminder = create_reminder(cfg.reminder, tray)
    settings = SettingsWindow(cfg, "config.yaml", window)

    worker.frame_ready.connect(window.on_frame_ready)
    worker.presence_changed.connect(window.on_presence_changed)
    worker.timer_updated.connect(window.on_timer_updated)
    worker.timer_updated.connect(lambda snapshot: tray.set_timer_state(snapshot.state))
    worker.connection_status.connect(window.on_connection_status)
    worker.connection_status.connect(lambda status: tray.set_connection(from_status(status)))
    worker.failed.connect(window.on_failed)
    worker.reminder_show.connect(reminder.show)
    worker.reminder_repeat.connect(reminder.show)
    reminder.dismissed.connect(worker.dismiss_reminder)
    window.roi_changed.connect(worker.set_roi)

    paused = False

    def _toggle_pause() -> None:
        nonlocal paused
        paused = not paused
        if paused:
            worker.pause()
        else:
            worker.resume()
        tray.set_paused(paused)

    tray.settings_action.triggered.connect(settings.show)
    window.request_settings.connect(settings.show)
    tray.toggle_action.triggered.connect(_toggle_pause)
    tray.quit_action.triggered.connect(app.quit)
    app.aboutToQuit.connect(lambda: _shutdown_worker_thread(worker, thread))

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
