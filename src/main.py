from __future__ import annotations

import signal
import sys

from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication

from src.app.worker import DetectionWorker
from src.capture.video_source import create_source
from src.config import AppConfig, load_config
from src.detection.detector import PersonDetector
from src.logging_store import SessionStore
from src.presence import PresenceEvaluator
from src.reminder.factory import create_reminder
from src.timer_engine import TimerEngine
from src.types import ReminderContext
from src.ui.main_window import MainWindow
from src.ui.settings import SettingsDialog
from src.ui.tray import TrayIcon


def _build_worker(cfg: AppConfig) -> DetectionWorker:
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
    store = SessionStore(cfg.logging.db_path)
    reminder_context = ReminderContext(
        work_minutes=int(cfg.timer.work_threshold_min),
        media_path=cfg.reminder.popup.media_path,
        media_type=cfg.reminder.popup.media_type,
        sound_path=cfg.reminder.popup.sound_path,
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
    app = QApplication.instance() or QApplication(sys.argv)
    cfg = load_config("config.yaml")

    worker = _build_worker(cfg)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    window = MainWindow(cfg)
    tray = TrayIcon()
    tray.bind_window(window)
    reminder = create_reminder(cfg.reminder, tray)
    settings_dialog = SettingsDialog(cfg, window)

    worker.frame_ready.connect(window.on_frame_ready)
    worker.presence_changed.connect(window.on_presence_changed)
    worker.timer_updated.connect(window.on_timer_updated)
    worker.timer_updated.connect(lambda snapshot: tray.update_status(snapshot.state))
    worker.connection_status.connect(window.on_connection_status)
    worker.failed.connect(window.on_connection_status)
    worker.failed.connect(lambda _message: app.quit())
    worker.reminder_show.connect(reminder.show)
    worker.reminder_repeat.connect(reminder.show)
    reminder.dismissed.connect(worker.dismiss_reminder)
    window.roi_changed.connect(worker.set_roi)

    tray.settings_action.triggered.connect(settings_dialog.show)
    tray.toggle_action.triggered.connect(worker.pause)
    tray.quit_action.triggered.connect(app.quit)
    app.aboutToQuit.connect(worker.stop)
    app.aboutToQuit.connect(thread.quit)
    app.aboutToQuit.connect(thread.wait)

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
