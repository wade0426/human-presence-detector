from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.types import BBox

MINUTE_MIN: float = 0.1
MINUTE_MAX: float = 9999.0


@dataclass
class SourceConfig:
    type: str = "rtsp"
    rtsp_url: str = ""
    webcam_index: int = 0
    reconnect_interval_sec: float = 5.0


@dataclass
class DetectionConfig:
    model_path: str = "data/model/yolov8n.pt"
    interval_sec: float = 1.0
    confidence: float = 0.4
    device: str = "auto"


@dataclass
class PresenceConfig:
    roi: BBox = field(default_factory=lambda: BBox(0.30, 0.20, 0.40, 0.70))
    min_box_height_ratio: float = 0.25
    debounce_count: int = 3


@dataclass
class TimerConfig:
    work_threshold_min: float = 45.0
    reset_threshold_min: float = 5.0
    required_rest_min: float = 5.0
    rest_count_mode: str = "presence"


@dataclass
class PopupConfig:
    media_path: str = "data/assets/rest_placeholder.png"
    media_type: str = "image"
    sound_path: str = ""


@dataclass
class FloatingConfig:
    position: str = "top-right"


@dataclass
class ReturnSoundConfig:
    enabled: bool = False
    sound_path: str = "data/assets/Radar.mp3"


@dataclass
class ReminderConfig:
    method: str = "popup"
    repeat_interval_min: float = 2.0
    reminding_display_mode: str = "overtime"  # "overtime" | "work_and_reminder"
    popup: PopupConfig = field(default_factory=PopupConfig)
    floating: FloatingConfig = field(default_factory=FloatingConfig)
    return_sound: ReturnSoundConfig = field(default_factory=ReturnSoundConfig)


@dataclass
class LoggingConfig:
    enabled: bool = True
    db_path: str = "data/records.sqlite"


@dataclass
class UIConfig:
    start_minimized: bool = False


@dataclass
class ForceLockConfig:
    enabled: bool = False
    trigger: str = "overtime"          # "overtime" | "on_rest"
    overtime_threshold_min: float = 10.0
    warning_mode: str = "immediate"    # "countdown_cancel" | "countdown_only" | "immediate"
    countdown_sec: int = 10


@dataclass
class AppConfig:
    source: SourceConfig = field(default_factory=SourceConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    presence: PresenceConfig = field(default_factory=PresenceConfig)
    timer: TimerConfig = field(default_factory=TimerConfig)
    reminder: ReminderConfig = field(default_factory=ReminderConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    force_lock: ForceLockConfig = field(default_factory=ForceLockConfig)


class ConfigError(Exception):
    pass


def validate(raw: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    source = _section(raw, "source")
    source_type = source.get("type", SourceConfig.type)
    if source_type not in {"rtsp", "webcam"}:
        errors.append("source.type must be one of: rtsp, webcam")
    if source_type == "rtsp" and not str(source.get("rtsp_url", "")).strip():
        errors.append("source.rtsp_url must be non-empty when source.type is 'rtsp'")

    detection = _section(raw, "detection")
    confidence = detection.get("confidence", DetectionConfig.confidence)
    if not _in_range(confidence, min_value=0.0, max_value=1.0, include_min=False):
        errors.append("detection.confidence must satisfy 0 < confidence <= 1")

    presence = _section(raw, "presence")
    min_box_height_ratio = presence.get(
        "min_box_height_ratio", PresenceConfig.min_box_height_ratio
    )
    if not _in_range(min_box_height_ratio, min_value=0.0, max_value=1.0, include_min=False):
        errors.append("presence.min_box_height_ratio must satisfy 0 < value <= 1")

    debounce_count = presence.get("debounce_count", PresenceConfig.debounce_count)
    if not isinstance(debounce_count, int) or debounce_count < 1:
        errors.append("presence.debounce_count must be an integer >= 1")

    timer = _section(raw, "timer")
    for key in ("work_threshold_min", "reset_threshold_min", "required_rest_min"):
        value = timer.get(key, getattr(TimerConfig, key))
        if not _in_range(value, min_value=MINUTE_MIN, max_value=MINUTE_MAX):
            errors.append(
                f"timer.{key} must satisfy {MINUTE_MIN} <= value <= {MINUTE_MAX}"
            )
    rest_count_mode = timer.get("rest_count_mode", TimerConfig.rest_count_mode)
    if rest_count_mode not in {"presence", "fixed"}:
        errors.append("timer.rest_count_mode must be one of: presence, fixed")

    reminder = _section(raw, "reminder")
    method = reminder.get("method", ReminderConfig.method)
    if method not in {"popup", "toast", "floating"}:
        errors.append("reminder.method must be one of: popup, toast, floating")

    reminding_display_mode = reminder.get(
        "reminding_display_mode", ReminderConfig.reminding_display_mode
    )
    if reminding_display_mode not in {"overtime", "work_and_reminder"}:
        errors.append(
            "reminder.reminding_display_mode must be one of: overtime, work_and_reminder"
        )

    for key in ("repeat_interval_min",):
        value = reminder.get(key, getattr(ReminderConfig, key))
        if not _in_range(value, min_value=MINUTE_MIN, max_value=MINUTE_MAX):
            errors.append(
                f"reminder.{key} must satisfy {MINUTE_MIN} <= value <= {MINUTE_MAX}"
            )

    popup = _section(reminder, "popup")
    media_type = popup.get("media_type", PopupConfig.media_type)
    if media_type not in {"image", "video"}:
        errors.append("reminder.popup.media_type must be one of: image, video")

    force_lock = _section(raw, "force_lock")
    trigger = force_lock.get("trigger", ForceLockConfig.trigger)
    if trigger not in {"overtime", "on_rest"}:
        errors.append("force_lock.trigger must be one of: overtime, on_rest")

    warning_mode = force_lock.get("warning_mode", ForceLockConfig.warning_mode)
    if warning_mode not in {"countdown_cancel", "countdown_only", "immediate"}:
        errors.append(
            "force_lock.warning_mode must be one of: countdown_cancel, countdown_only, immediate"
        )

    overtime_threshold_min = force_lock.get(
        "overtime_threshold_min", ForceLockConfig.overtime_threshold_min
    )
    if not _in_range(overtime_threshold_min, min_value=MINUTE_MIN, max_value=MINUTE_MAX):
        errors.append(
            f"force_lock.overtime_threshold_min must satisfy {MINUTE_MIN} <= value <= {MINUTE_MAX}"
        )

    countdown_sec = force_lock.get("countdown_sec", ForceLockConfig.countdown_sec)
    if not isinstance(countdown_sec, int) or isinstance(countdown_sec, bool) or countdown_sec < 1:
        errors.append("force_lock.countdown_sec must be an integer >= 1")

    return errors


def load_config(path: str) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        return AppConfig()

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping")

    errors = validate(data)
    if errors:
        raise ConfigError("\n".join(errors))

    return _app_config_from_dict(data)


def save_config(config: AppConfig, path: str) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _serialize_app_config(config)
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)


def _section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key, {})
    return value if isinstance(value, dict) else {}


def _greater_than_zero(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _in_range(
    value: Any, *, min_value: float, max_value: float, include_min: bool = True
) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    lower_ok = value >= min_value if include_min else value > min_value
    return lower_ok and value <= max_value


def _app_config_from_dict(raw: dict[str, Any]) -> AppConfig:
    source_raw = _section(raw, "source")
    detection_raw = _section(raw, "detection")
    presence_raw = _section(raw, "presence")
    timer_raw = _section(raw, "timer")
    reminder_raw = _section(raw, "reminder")
    popup_raw = _section(reminder_raw, "popup")
    floating_raw = _section(reminder_raw, "floating")
    return_sound_raw = _section(reminder_raw, "return_sound")
    logging_raw = _section(raw, "logging")
    ui_raw = _section(raw, "ui")
    force_lock_raw = _section(raw, "force_lock")

    return AppConfig(
        source=SourceConfig(
            type=str(source_raw.get("type", SourceConfig.type)),
            rtsp_url=str(source_raw.get("rtsp_url", SourceConfig.rtsp_url)),
            webcam_index=int(source_raw.get("webcam_index", SourceConfig.webcam_index)),
            reconnect_interval_sec=float(
                source_raw.get(
                    "reconnect_interval_sec", SourceConfig.reconnect_interval_sec
                )
            ),
        ),
        detection=DetectionConfig(
            model_path=str(detection_raw.get("model_path", DetectionConfig.model_path)),
            interval_sec=float(detection_raw.get("interval_sec", DetectionConfig.interval_sec)),
            confidence=float(detection_raw.get("confidence", DetectionConfig.confidence)),
            device=str(detection_raw.get("device", DetectionConfig.device)),
        ),
        presence=PresenceConfig(
            roi=_roi_from_raw(presence_raw.get("roi")),
            min_box_height_ratio=float(
                presence_raw.get(
                    "min_box_height_ratio", PresenceConfig.min_box_height_ratio
                )
            ),
            debounce_count=int(
                presence_raw.get("debounce_count", PresenceConfig.debounce_count)
            ),
        ),
        timer=TimerConfig(
            work_threshold_min=float(
                timer_raw.get("work_threshold_min", TimerConfig.work_threshold_min)
            ),
            reset_threshold_min=float(
                timer_raw.get("reset_threshold_min", TimerConfig.reset_threshold_min)
            ),
            required_rest_min=float(
                timer_raw.get("required_rest_min", TimerConfig.required_rest_min)
            ),
            rest_count_mode=str(
                timer_raw.get("rest_count_mode", TimerConfig.rest_count_mode)
            ),
        ),
        reminder=ReminderConfig(
            method=str(reminder_raw.get("method", ReminderConfig.method)),
            repeat_interval_min=float(
                reminder_raw.get(
                    "repeat_interval_min", ReminderConfig.repeat_interval_min
                )
            ),
            reminding_display_mode=str(
                reminder_raw.get(
                    "reminding_display_mode", ReminderConfig.reminding_display_mode
                )
            ),
            popup=PopupConfig(
                media_path=str(popup_raw.get("media_path", PopupConfig.media_path)),
                media_type=str(popup_raw.get("media_type", PopupConfig.media_type)),
                sound_path=str(popup_raw.get("sound_path", PopupConfig.sound_path)),
            ),
            floating=FloatingConfig(
                position=str(floating_raw.get("position", FloatingConfig.position))
            ),
            return_sound=ReturnSoundConfig(
                enabled=bool(return_sound_raw.get("enabled", ReturnSoundConfig.enabled)),
                sound_path=str(return_sound_raw.get("sound_path", ReturnSoundConfig.sound_path)),
            ),
        ),
        logging=LoggingConfig(
            enabled=bool(logging_raw.get("enabled", LoggingConfig.enabled)),
            db_path=str(logging_raw.get("db_path", LoggingConfig.db_path)),
        ),
        ui=UIConfig(
            start_minimized=bool(ui_raw.get("start_minimized", UIConfig.start_minimized))
        ),
        force_lock=ForceLockConfig(
            enabled=bool(force_lock_raw.get("enabled", ForceLockConfig.enabled)),
            trigger=str(force_lock_raw.get("trigger", ForceLockConfig.trigger)),
            overtime_threshold_min=float(
                force_lock_raw.get(
                    "overtime_threshold_min", ForceLockConfig.overtime_threshold_min
                )
            ),
            warning_mode=str(force_lock_raw.get("warning_mode", ForceLockConfig.warning_mode)),
            countdown_sec=int(
                force_lock_raw.get("countdown_sec", ForceLockConfig.countdown_sec)
            ),
        ),
    )


def _roi_from_raw(value: Any) -> BBox:
    if isinstance(value, list) and len(value) == 4:
        return BBox(*(float(part) for part in value))
    default = PresenceConfig().roi
    return BBox(default.x, default.y, default.w, default.h)


def _serialize_app_config(config: AppConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["presence"]["roi"] = [
        config.presence.roi.x,
        config.presence.roi.y,
        config.presence.roi.w,
        config.presence.roi.h,
    ]
    return payload
