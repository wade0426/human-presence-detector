"""config v2：載入/驗證/儲存與 core 換算（spec §8）。

- ``version != 2`` 或檔案缺失 → 以預設值啟動（不遷移 v1）。
- 格式/數值錯誤一律以 :class:`ConfigError` 列錯，不外洩原始例外。
- ``machine_config`` / ``escalation_policy`` 負責 AppConfig → core 型別換算
  （分→秒）。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.core.escalation import EscalationPolicy
from src.core.state_machine import MachineConfig
from src.types import BBox

CONFIG_VERSION: int = 2
MINUTE_MIN: float = 0.1
MINUTE_MAX: float = 9999.0

_DEFAULT_ROI = BBox(0.0, 0.0, 1.0, 1.0)


@dataclass
class SourceConfig:
    type: str = "rtsp"
    rtsp_url: str = ""
    webcam_index: int = 0
    reconnect_interval_sec: float = 5.0


@dataclass
class DetectionConfig:
    model_path: str = "data/model/yolov8n.pt"
    device: str = "auto"
    confidence: float = 0.5
    interval_sec: float = 1.0
    min_box_height_ratio: float = 0.3


@dataclass
class PresenceConfig:
    roi: BBox = field(default_factory=lambda: _DEFAULT_ROI)
    debounce_count: int = 3


@dataclass
class TimerConfig:
    work_threshold_min: float = 50.0
    reset_threshold_min: float = 5.0
    required_rest_min: float = 10.0
    rest_count_mode: str = "presence"  # "presence" | "fixed"


@dataclass
class EscalationConfig:
    max_stage: int = 3  # 0..3
    stage_after_sec: tuple[float, float, float] = (60.0, 120.0, 180.0)
    apply_to_reminding: bool = True


@dataclass
class RestFlowConfig:
    pending_accounting: str = "work"  # "work" | "none"
    interrupt_behavior: str = "remind"  # "remind" | "new_work"
    rest_interrupt_after_sec: float = 120.0
    escalation: EscalationConfig = field(default_factory=EscalationConfig)


@dataclass
class PopupConfig:
    media_path: str = ""
    media_type: str = "image"  # "image" | "video"
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
    method: str = "popup"  # "popup" | "toast" | "floating"
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
class UiConfig:
    start_minimized: bool = False


@dataclass
class AppConfig:
    source: SourceConfig = field(default_factory=SourceConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    presence: PresenceConfig = field(default_factory=PresenceConfig)
    timer: TimerConfig = field(default_factory=TimerConfig)
    rest_flow: RestFlowConfig = field(default_factory=RestFlowConfig)
    reminder: ReminderConfig = field(default_factory=ReminderConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    ui: UiConfig = field(default_factory=UiConfig)


class ConfigError(Exception):
    """設定錯誤；``errors`` 保留逐條錯誤訊息（訊息本體為換行串接）。"""

    def __init__(self, errors: list[str] | str) -> None:
        items = [errors] if isinstance(errors, str) else list(errors)
        self.errors: list[str] = items
        super().__init__("\n".join(items))


# ---------------------------------------------------------------------------
# 驗證
# ---------------------------------------------------------------------------


def validate(raw: dict[str, Any]) -> list[str]:
    """嚴格驗證 raw mapping，回傳逐條錯誤訊息（空 list = 合法）。"""
    errors: list[str] = []
    errors += _validate_source(_section(raw, "source"))
    errors += _validate_detection(_section(raw, "detection"))
    errors += _validate_presence(_section(raw, "presence"))
    errors += _validate_timer(_section(raw, "timer"))
    errors += _validate_rest_flow(_section(raw, "rest_flow"))
    errors += _validate_reminder(_section(raw, "reminder"))
    return errors


def _validate_source(source: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source_type = source.get("type", SourceConfig.type)
    if source_type not in {"rtsp", "webcam"}:
        errors.append("source.type must be one of: rtsp, webcam")
    if source_type == "rtsp" and not str(source.get("rtsp_url", "")).strip():
        errors.append("source.rtsp_url must be non-empty when source.type is 'rtsp'")

    webcam_index = source.get("webcam_index", SourceConfig.webcam_index)
    if not _is_int(webcam_index) or webcam_index < 0:
        errors.append("source.webcam_index must be an integer >= 0")

    reconnect = source.get("reconnect_interval_sec", SourceConfig.reconnect_interval_sec)
    if not _greater_than_zero(reconnect):
        errors.append("source.reconnect_interval_sec must be a number > 0")
    return errors


def _validate_detection(detection: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    confidence = detection.get("confidence", DetectionConfig.confidence)
    if not _in_range(confidence, min_value=0.0, max_value=1.0, include_min=False):
        errors.append("detection.confidence must satisfy 0 < confidence <= 1")

    interval_sec = detection.get("interval_sec", DetectionConfig.interval_sec)
    if not _greater_than_zero(interval_sec):
        errors.append("detection.interval_sec must be a number > 0")

    ratio = detection.get("min_box_height_ratio", DetectionConfig.min_box_height_ratio)
    if not _in_range(ratio, min_value=0.0, max_value=1.0, include_min=False):
        errors.append("detection.min_box_height_ratio must satisfy 0 < value <= 1")
    return errors


def _validate_presence(presence: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    roi = presence.get("roi")
    if roi is not None:
        errors += _validate_roi(roi)

    debounce_count = presence.get("debounce_count", PresenceConfig.debounce_count)
    if not _is_int(debounce_count) or debounce_count < 1:
        errors.append("presence.debounce_count must be an integer >= 1")
    return errors


def _validate_timer(timer: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("work_threshold_min", "reset_threshold_min", "required_rest_min"):
        value = timer.get(key, getattr(TimerConfig, key))
        if not _in_range(value, min_value=MINUTE_MIN, max_value=MINUTE_MAX):
            errors.append(
                f"timer.{key} must satisfy {MINUTE_MIN} <= value <= {MINUTE_MAX}"
            )

    rest_count_mode = timer.get("rest_count_mode", TimerConfig.rest_count_mode)
    if rest_count_mode not in {"presence", "fixed"}:
        errors.append("timer.rest_count_mode must be one of: presence, fixed")
    return errors


def _validate_rest_flow(rest_flow: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pending = rest_flow.get("pending_accounting", RestFlowConfig.pending_accounting)
    if pending not in {"work", "none"}:
        errors.append("rest_flow.pending_accounting must be one of: work, none")

    interrupt = rest_flow.get("interrupt_behavior", RestFlowConfig.interrupt_behavior)
    if interrupt not in {"remind", "new_work"}:
        errors.append("rest_flow.interrupt_behavior must be one of: remind, new_work")

    after_sec = rest_flow.get(
        "rest_interrupt_after_sec", RestFlowConfig.rest_interrupt_after_sec
    )
    if not _greater_than_zero(after_sec):
        errors.append("rest_flow.rest_interrupt_after_sec must be a number > 0")

    escalation = _section(rest_flow, "escalation")
    max_stage = escalation.get("max_stage", EscalationConfig.max_stage)
    if not _is_int(max_stage) or not 0 <= max_stage <= 3:
        errors.append("rest_flow.escalation.max_stage must be an integer between 0 and 3")

    stage_after = escalation.get(
        "stage_after_sec", list(EscalationConfig.stage_after_sec)
    )
    errors += _validate_stage_after_sec(stage_after)
    return errors


def _validate_stage_after_sec(value: Any) -> list[str]:
    items = list(value) if isinstance(value, tuple) else value
    if not isinstance(items, list) or len(items) != 3:
        return [
            "rest_flow.escalation.stage_after_sec must be a list of 3 numbers [s1, s2, s3]"
        ]
    if not all(_is_number(part) for part in items):
        return ["rest_flow.escalation.stage_after_sec values must all be numbers"]

    errors: list[str] = []
    s1, s2, s3 = items
    if not all(part > 0 for part in items):
        errors.append("rest_flow.escalation.stage_after_sec values must all be > 0")
    if not (s1 < s2 < s3):
        errors.append("rest_flow.escalation.stage_after_sec must be strictly increasing")
    return errors


def _validate_reminder(reminder: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    method = reminder.get("method", ReminderConfig.method)
    if method not in {"popup", "toast", "floating"}:
        errors.append("reminder.method must be one of: popup, toast, floating")

    display_mode = reminder.get(
        "reminding_display_mode", ReminderConfig.reminding_display_mode
    )
    if display_mode not in {"overtime", "work_and_reminder"}:
        errors.append(
            "reminder.reminding_display_mode must be one of: overtime, work_and_reminder"
        )

    repeat = reminder.get("repeat_interval_min", ReminderConfig.repeat_interval_min)
    if not _in_range(repeat, min_value=MINUTE_MIN, max_value=MINUTE_MAX):
        errors.append(
            f"reminder.repeat_interval_min must satisfy {MINUTE_MIN} <= value <= {MINUTE_MAX}"
        )

    popup = _section(reminder, "popup")
    media_type = popup.get("media_type", PopupConfig.media_type)
    if media_type not in {"image", "video"}:
        errors.append("reminder.popup.media_type must be one of: image, video")
    return errors


def _validate_roi(value: Any) -> list[str]:
    """v2 嚴格驗證 roi：畸形與越界一律列錯（不做 clamp 遷移）。"""
    if not isinstance(value, list) or len(value) != 4:
        return ["presence.roi must be a list of 4 numbers [x, y, w, h]"]
    if not all(_is_number(part) for part in value):
        return ["presence.roi values must all be numbers"]

    x, y, w, h = value
    errors: list[str] = []
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        errors.append("presence.roi x and y must satisfy 0 <= value <= 1")
    if not (w > 0.0 and h > 0.0):
        errors.append("presence.roi w and h must be > 0")
    if x + w > 1.0 or y + h > 1.0:
        errors.append("presence.roi must satisfy x + w <= 1 and y + h <= 1")
    return errors


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _greater_than_zero(value: Any) -> bool:
    return _is_number(value) and value > 0


def _in_range(
    value: Any, *, min_value: float, max_value: float, include_min: bool = True
) -> bool:
    if not _is_number(value):
        return False
    lower_ok = value >= min_value if include_min else value > min_value
    return bool(lower_ok and value <= max_value)


def _section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key, {})
    return value if isinstance(value, dict) else {}


# ---------------------------------------------------------------------------
# 載入 / 儲存
# ---------------------------------------------------------------------------


def load_config(path: str) -> AppConfig:
    """載入 config v2。

    - 檔案缺失或 ``version != 2`` → 回傳全預設 :class:`AppConfig`（不炸）。
    - YAML 語法錯誤 / IO 錯誤 / 驗證失敗 → :class:`ConfigError`
      （上輪 §4.5：不得外洩原始例外，否則上層 except ConfigError 攔不到）。
    """
    config_path = Path(path)
    if not config_path.exists():
        return AppConfig()

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"設定檔 YAML 語法錯誤（{path}）：{exc}") from exc
    except OSError as exc:
        raise ConfigError(f"無法讀取設定檔（{path}）：{exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping")

    if data.get("version") != CONFIG_VERSION:
        return AppConfig()

    errors = validate(data)
    if errors:
        raise ConfigError(errors)

    return _app_config_from_dict(data)


def save_config(config: AppConfig, path: str) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _serialize_app_config(config)
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)


def _serialize_app_config(config: AppConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {"version": CONFIG_VERSION}
    payload.update(asdict(config))
    roi = config.presence.roi
    payload["presence"]["roi"] = [roi.x, roi.y, roi.w, roi.h]
    payload["rest_flow"]["escalation"]["stage_after_sec"] = list(
        config.rest_flow.escalation.stage_after_sec
    )
    return payload


def _app_config_from_dict(raw: dict[str, Any]) -> AppConfig:
    source_raw = _section(raw, "source")
    detection_raw = _section(raw, "detection")
    presence_raw = _section(raw, "presence")
    timer_raw = _section(raw, "timer")
    rest_flow_raw = _section(raw, "rest_flow")
    escalation_raw = _section(rest_flow_raw, "escalation")
    reminder_raw = _section(raw, "reminder")
    popup_raw = _section(reminder_raw, "popup")
    floating_raw = _section(reminder_raw, "floating")
    return_sound_raw = _section(reminder_raw, "return_sound")
    logging_raw = _section(raw, "logging")
    ui_raw = _section(raw, "ui")

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
            device=str(detection_raw.get("device", DetectionConfig.device)),
            confidence=float(
                detection_raw.get("confidence", DetectionConfig.confidence)
            ),
            interval_sec=float(
                detection_raw.get("interval_sec", DetectionConfig.interval_sec)
            ),
            min_box_height_ratio=float(
                detection_raw.get(
                    "min_box_height_ratio", DetectionConfig.min_box_height_ratio
                )
            ),
        ),
        presence=PresenceConfig(
            roi=_roi_from_raw(presence_raw.get("roi")),
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
        rest_flow=RestFlowConfig(
            pending_accounting=str(
                rest_flow_raw.get(
                    "pending_accounting", RestFlowConfig.pending_accounting
                )
            ),
            interrupt_behavior=str(
                rest_flow_raw.get(
                    "interrupt_behavior", RestFlowConfig.interrupt_behavior
                )
            ),
            rest_interrupt_after_sec=float(
                rest_flow_raw.get(
                    "rest_interrupt_after_sec", RestFlowConfig.rest_interrupt_after_sec
                )
            ),
            escalation=EscalationConfig(
                max_stage=int(
                    escalation_raw.get("max_stage", EscalationConfig.max_stage)
                ),
                stage_after_sec=_stage_after_from_raw(
                    escalation_raw.get("stage_after_sec")
                ),
                apply_to_reminding=bool(
                    escalation_raw.get(
                        "apply_to_reminding", EscalationConfig.apply_to_reminding
                    )
                ),
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
                enabled=bool(
                    return_sound_raw.get("enabled", ReturnSoundConfig.enabled)
                ),
                sound_path=str(
                    return_sound_raw.get("sound_path", ReturnSoundConfig.sound_path)
                ),
            ),
        ),
        logging=LoggingConfig(
            enabled=bool(logging_raw.get("enabled", LoggingConfig.enabled)),
            db_path=str(logging_raw.get("db_path", LoggingConfig.db_path)),
        ),
        ui=UiConfig(
            start_minimized=bool(
                ui_raw.get("start_minimized", UiConfig.start_minimized)
            )
        ),
    )


def _roi_from_raw(value: Any) -> BBox:
    if isinstance(value, list) and len(value) == 4:
        return BBox(*(float(part) for part in value))
    return _DEFAULT_ROI


def _stage_after_from_raw(value: Any) -> tuple[float, float, float]:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        s1, s2, s3 = (float(part) for part in value)
        return (s1, s2, s3)
    return EscalationConfig.stage_after_sec


def clamp_roi(roi: BBox) -> BBox:
    """把越界的 roi 夾回合法範圍（ROI 編輯端留邊修正，沿用上輪語意）。

    x、y 夾進 [0, 1]，w、h 夾至不超出右/下邊界；夾完後寬高歸零（退化）
    時回退預設 roi。注意：v2 的 ``validate`` 對越界 roi 一律列錯，
    本函式僅供編輯端在「存檔前」修正使用。
    """
    x = min(max(roi.x, 0.0), 1.0)
    y = min(max(roi.y, 0.0), 1.0)
    w = min(roi.w, 1.0 - x)
    h = min(roi.h, 1.0 - y)
    if w <= 0.0 or h <= 0.0:
        return _DEFAULT_ROI
    return BBox(x, y, w, h)


# ---------------------------------------------------------------------------
# AppConfig → core 換算
# ---------------------------------------------------------------------------


def machine_config(cfg: AppConfig) -> MachineConfig:
    """AppConfig → :class:`MachineConfig`（分→秒換算）。"""
    return MachineConfig(
        work_threshold_sec=cfg.timer.work_threshold_min * 60.0,
        reset_threshold_sec=cfg.timer.reset_threshold_min * 60.0,
        required_rest_sec=cfg.timer.required_rest_min * 60.0,
        repeat_interval_sec=cfg.reminder.repeat_interval_min * 60.0,
        rest_count_mode=cfg.timer.rest_count_mode,
        pending_accounting=cfg.rest_flow.pending_accounting,
        interrupt_behavior=cfg.rest_flow.interrupt_behavior,
        rest_interrupt_after_sec=cfg.rest_flow.rest_interrupt_after_sec,
        apply_to_reminding=cfg.rest_flow.escalation.apply_to_reminding,
    )


def escalation_policy(cfg: AppConfig) -> EscalationPolicy:
    """AppConfig → :class:`EscalationPolicy`（已通過 validate 的值直接對映）。"""
    return EscalationPolicy(
        stage_after_sec=cfg.rest_flow.escalation.stage_after_sec,
        max_stage=cfg.rest_flow.escalation.max_stage,
    )
