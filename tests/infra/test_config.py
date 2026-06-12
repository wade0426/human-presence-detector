from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from src.core.escalation import EscalationPolicy
from src.core.state_machine import MachineConfig
from src.infra.config import (
    MINUTE_MAX,
    MINUTE_MIN,
    AppConfig,
    ConfigError,
    clamp_roi,
    escalation_policy,
    load_config,
    machine_config,
    save_config,
    validate,
)
from src.types import BBox


def _write_yaml(tmp_path: Path, data: object, name: str = "config.yaml") -> str:
    path = tmp_path / name
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return str(path)


# ---------------------------------------------------------------------------
# 預設值（spec §8）
# ---------------------------------------------------------------------------


def test_load_config_returns_defaults_when_path_missing(tmp_path: Path) -> None:
    config = load_config(str(tmp_path / "missing.yaml"))
    assert config == AppConfig()


def test_default_appconfig_matches_spec_section_8() -> None:
    cfg = AppConfig()

    assert cfg.source.type == "rtsp"
    assert cfg.source.rtsp_url == ""
    assert cfg.source.webcam_index == 0
    assert cfg.source.reconnect_interval_sec == 5.0

    assert cfg.detection.model_path == "data/model/yolov8n.pt"
    assert cfg.detection.device == "auto"
    assert cfg.detection.confidence == 0.5
    assert cfg.detection.interval_sec == 1.0
    assert cfg.detection.min_box_height_ratio == 0.3

    assert cfg.presence.roi == BBox(0.0, 0.0, 1.0, 1.0)
    assert cfg.presence.debounce_count == 3

    assert cfg.timer.work_threshold_min == 50.0
    assert cfg.timer.reset_threshold_min == 5.0
    assert cfg.timer.required_rest_min == 10.0
    assert cfg.timer.rest_count_mode == "presence"

    assert cfg.rest_flow.pending_accounting == "work"
    assert cfg.rest_flow.interrupt_behavior == "remind"
    assert cfg.rest_flow.rest_interrupt_after_sec == 120.0
    assert cfg.rest_flow.escalation.max_stage == 3
    assert cfg.rest_flow.escalation.stage_after_sec == (60.0, 120.0, 180.0)
    assert cfg.rest_flow.escalation.apply_to_reminding is True

    assert cfg.reminder.method == "popup"
    assert cfg.reminder.repeat_interval_min == 2.0
    assert cfg.reminder.reminding_display_mode == "overtime"
    assert cfg.reminder.popup.media_path == ""
    assert cfg.reminder.popup.media_type == "image"
    assert cfg.reminder.popup.sound_path == ""
    assert cfg.reminder.floating.position == "top-right"
    assert cfg.reminder.return_sound.enabled is False
    assert cfg.reminder.return_sound.sound_path == "data/assets/Radar.mp3"

    assert cfg.logging.enabled is True
    assert cfg.logging.db_path == "data/records.sqlite"

    assert cfg.ui.start_minimized is False


def test_appconfig_has_no_force_lock_section() -> None:
    """force_lock 已被升級階梯吸收（spec §12 刻意例外）。"""
    assert not hasattr(AppConfig(), "force_lock")


def test_load_config_fills_missing_sections_with_defaults(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path,
        {
            "version": 2,
            "source": {"type": "webcam"},
            "rest_flow": {"escalation": {"max_stage": 2}},
        },
    )

    cfg = load_config(path)

    assert cfg.source.type == "webcam"
    assert cfg.detection == AppConfig().detection
    assert cfg.reminder == AppConfig().reminder
    assert cfg.rest_flow.pending_accounting == "work"
    assert cfg.rest_flow.escalation.max_stage == 2
    assert cfg.rest_flow.escalation.stage_after_sec == (60.0, 120.0, 180.0)


def test_load_config_coerces_numeric_types(tmp_path: Path) -> None:
    """YAML 整數載入後必須是 float（stage_after_sec、rest_interrupt_after_sec）。"""
    path = _write_yaml(
        tmp_path,
        {
            "version": 2,
            "source": {"type": "webcam"},
            "rest_flow": {
                "rest_interrupt_after_sec": 90,
                "escalation": {"stage_after_sec": [30, 60, 120]},
            },
        },
    )

    cfg = load_config(path)

    assert isinstance(cfg.rest_flow.rest_interrupt_after_sec, float)
    assert cfg.rest_flow.rest_interrupt_after_sec == 90.0
    assert cfg.rest_flow.escalation.stage_after_sec == (30.0, 60.0, 120.0)
    assert all(
        isinstance(value, float) for value in cfg.rest_flow.escalation.stage_after_sec
    )


# ---------------------------------------------------------------------------
# round-trip save/load
# ---------------------------------------------------------------------------


def test_save_then_load_round_trip_default(tmp_path: Path) -> None:
    config = AppConfig()
    config.source.type = "webcam"

    path = tmp_path / "round-trip.yaml"
    save_config(config, str(path))

    assert load_config(str(path)) == config


def test_save_then_load_round_trip_preserves_modified_values(tmp_path: Path) -> None:
    config = AppConfig()
    config.source.type = "webcam"
    config.source.webcam_index = 2
    config.detection.confidence = 0.7
    config.detection.min_box_height_ratio = 0.5
    config.presence.roi = BBox(0.1, 0.2, 0.3, 0.4)
    config.presence.debounce_count = 5
    config.timer.work_threshold_min = 25.0
    config.timer.rest_count_mode = "fixed"
    config.rest_flow.pending_accounting = "none"
    config.rest_flow.interrupt_behavior = "new_work"
    config.rest_flow.rest_interrupt_after_sec = 60.0
    config.rest_flow.escalation.max_stage = 1
    config.rest_flow.escalation.stage_after_sec = (30.0, 90.0, 300.0)
    config.rest_flow.escalation.apply_to_reminding = False
    config.reminder.method = "floating"
    config.reminder.repeat_interval_min = 5.0
    config.reminder.return_sound.enabled = True
    config.logging.enabled = False
    config.ui.start_minimized = True

    path = tmp_path / "round-trip.yaml"
    save_config(config, str(path))

    assert load_config(str(path)) == config


def test_save_config_writes_version_2_and_plain_lists(tmp_path: Path) -> None:
    config = AppConfig()
    config.source.type = "webcam"

    path = tmp_path / "config.yaml"
    save_config(config, str(path))

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert "force_lock" not in payload
    assert payload["presence"]["roi"] == [0.0, 0.0, 1.0, 1.0]
    assert payload["rest_flow"]["escalation"]["stage_after_sec"] == [60.0, 120.0, 180.0]


def test_save_config_creates_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deeper" / "config.yaml"
    save_config(AppConfig(), str(path))
    assert path.exists()


# ---------------------------------------------------------------------------
# version 檢查：version != 2 或缺 version → 預設值啟動、不炸
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("version", [1, 0, 3, "2", "two", None])
def test_load_config_returns_defaults_for_non_v2_version(
    tmp_path: Path, version: object
) -> None:
    """version != 2 → 預設值；連驗證都不跑（內含非法值也不得炸）。"""
    path = _write_yaml(
        tmp_path,
        {
            "version": version,
            "source": {"type": "not-a-valid-type"},
            "rest_flow": {"escalation": {"max_stage": 99}},
        },
    )

    assert load_config(path) == AppConfig()


def test_load_config_returns_defaults_when_version_missing(tmp_path: Path) -> None:
    """v1 設定檔（無 version 鍵）不遷移：直接以預設值啟動。"""
    path = _write_yaml(tmp_path, {"source": {"type": "webcam"}})
    assert load_config(path) == AppConfig()


# ---------------------------------------------------------------------------
# 錯誤通道：一律 ConfigError，不外洩原始例外
# ---------------------------------------------------------------------------


def test_load_config_raises_config_error_for_broken_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("source: [unclosed\n  type: webcam\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(str(path))


def test_load_config_raises_config_error_for_unreadable_path(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.mkdir()

    with pytest.raises(ConfigError):
        load_config(str(path))


def test_load_config_raises_config_error_for_non_mapping_root(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path, ["a", "b"])

    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_reports_all_validation_errors(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path,
        {
            "version": 2,
            "source": {"type": "webcam"},
            "timer": {"rest_count_mode": "bad"},
            "rest_flow": {"pending_accounting": "always"},
        },
    )

    with pytest.raises(ConfigError) as excinfo:
        load_config(path)

    assert isinstance(excinfo.value.errors, list)
    assert any("timer.rest_count_mode" in e for e in excinfo.value.errors)
    assert any("rest_flow.pending_accounting" in e for e in excinfo.value.errors)
    message = str(excinfo.value)
    assert "timer.rest_count_mode" in message
    assert "rest_flow.pending_accounting" in message


@pytest.mark.parametrize(
    "roi",
    [
        [None, 0.2, 0.3, 0.4],
        ["abc", 0.2, 0.3, 0.4],
        "not-a-list",
        [0.1, 0.2, 0.3],
        [0.7, 0.2, 0.4, 0.4],  # x + w > 1：v2 嚴格拒絕（不做 clamp 遷移）
    ],
)
def test_load_config_raises_config_error_for_bad_roi(
    tmp_path: Path, roi: object
) -> None:
    path = _write_yaml(
        tmp_path,
        {"version": 2, "source": {"type": "webcam"}, "presence": {"roi": roi}},
    )

    with pytest.raises(ConfigError) as excinfo:
        load_config(path)
    assert "presence.roi" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 驗證矩陣：source
# ---------------------------------------------------------------------------


def test_validate_reports_invalid_source_type() -> None:
    errors = validate({"source": {"type": "x"}})
    assert any("source.type" in e for e in errors)


def test_validate_requires_rtsp_url_for_rtsp_source() -> None:
    errors = validate({"source": {"type": "rtsp", "rtsp_url": ""}})
    assert any("rtsp_url" in e for e in errors)


def test_validate_accepts_rtsp_with_url() -> None:
    errors = validate({"source": {"type": "rtsp", "rtsp_url": "rtsp://cam/main"}})
    assert not errors


@pytest.mark.parametrize("value", [-1, 1.5, "0", None, True])
def test_validate_reports_invalid_webcam_index(value: object) -> None:
    errors = validate({"source": {"type": "webcam", "webcam_index": value}})
    assert any("source.webcam_index" in e for e in errors)


@pytest.mark.parametrize("value", [0, 1, 3])
def test_validate_accepts_valid_webcam_index(value: int) -> None:
    errors = validate({"source": {"type": "webcam", "webcam_index": value}})
    assert not any("source.webcam_index" in e for e in errors)


@pytest.mark.parametrize("value", [0, 0.0, -5, "abc", None, True, [1.0]])
def test_validate_reports_invalid_reconnect_interval_sec(value: object) -> None:
    errors = validate({"source": {"type": "webcam", "reconnect_interval_sec": value}})
    assert any("source.reconnect_interval_sec" in e for e in errors)


@pytest.mark.parametrize("value", [0.5, 5, 30.0])
def test_validate_accepts_valid_reconnect_interval_sec(value: object) -> None:
    errors = validate({"source": {"type": "webcam", "reconnect_interval_sec": value}})
    assert not any("source.reconnect_interval_sec" in e for e in errors)


# ---------------------------------------------------------------------------
# 驗證矩陣：detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, 0.0, 1.5, -0.2, "x", None, True])
def test_validate_reports_invalid_confidence(value: object) -> None:
    errors = validate({"source": {"type": "webcam"}, "detection": {"confidence": value}})
    assert any("detection.confidence" in e for e in errors)


@pytest.mark.parametrize("value", [0.5, 1, 1.0, 0.01])
def test_validate_accepts_valid_confidence(value: object) -> None:
    errors = validate({"source": {"type": "webcam"}, "detection": {"confidence": value}})
    assert not any("detection.confidence" in e for e in errors)


@pytest.mark.parametrize("value", [0, 0.0, -1.0, "abc", None, True, [1.0]])
def test_validate_reports_invalid_detection_interval_sec(value: object) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "detection": {"interval_sec": value}}
    )
    assert any("detection.interval_sec" in e for e in errors)


@pytest.mark.parametrize("value", [0.5, 1, 2.0])
def test_validate_accepts_valid_detection_interval_sec(value: object) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "detection": {"interval_sec": value}}
    )
    assert not any("detection.interval_sec" in e for e in errors)


@pytest.mark.parametrize("value", [0, 0.0, 1.5, "x", None, True])
def test_validate_reports_invalid_min_box_height_ratio(value: object) -> None:
    """min_box_height_ratio 在 v2 移到 detection 區段。"""
    errors = validate(
        {"source": {"type": "webcam"}, "detection": {"min_box_height_ratio": value}}
    )
    assert any("detection.min_box_height_ratio" in e for e in errors)


@pytest.mark.parametrize("value", [0.3, 1, 1.0, 0.01])
def test_validate_accepts_valid_min_box_height_ratio(value: object) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "detection": {"min_box_height_ratio": value}}
    )
    assert not any("detection.min_box_height_ratio" in e for e in errors)


# ---------------------------------------------------------------------------
# 驗證矩陣：presence（roi 畸形/越界、debounce_count）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "roi",
    [
        "not-a-list",  # 非 list（字串）
        {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},  # 非 list（dict）
        0.5,  # 非 list（純量）
        [0.1, 0.2, 0.3],  # 長度 3
        [0.1, 0.2, 0.3, 0.4, 0.5],  # 長度 5
        [None, 0.2, 0.3, 0.4],  # 含 None
        ["0.1", 0.2, 0.3, 0.4],  # 含字串
        [True, 0.2, 0.3, 0.4],  # 含 bool
        [-0.1, 0.2, 0.3, 0.4],  # x 負值
        [0.1, 1.5, 0.3, 0.4],  # y > 1
        [0.1, 0.2, 0.0, 0.4],  # w = 0
        [0.1, 0.2, 0.3, 0.0],  # h = 0
        [0.1, 0.2, -0.3, 0.4],  # w 負值
        [0.7, 0.2, 0.4, 0.4],  # x + w > 1
        [0.1, 0.8, 0.3, 0.4],  # y + h > 1
    ],
)
def test_validate_reports_malformed_roi(roi: object) -> None:
    errors = validate({"source": {"type": "webcam"}, "presence": {"roi": roi}})
    assert any("presence.roi" in e for e in errors)


@pytest.mark.parametrize(
    "roi",
    [
        [0.1, 0.2, 0.3, 0.4],
        [0, 0, 1, 1],  # 整數邊界值（v2 預設）
        [0.0, 0.0, 0.5, 1.0],
    ],
)
def test_validate_accepts_valid_roi(roi: list[float]) -> None:
    errors = validate({"source": {"type": "webcam"}, "presence": {"roi": roi}})
    assert not any("presence.roi" in e for e in errors)


def test_validate_accepts_missing_roi() -> None:
    errors = validate({"source": {"type": "webcam"}, "presence": {}})
    assert not any("presence.roi" in e for e in errors)


@pytest.mark.parametrize("value", [0, -1, 1.5, "3", None, True])
def test_validate_reports_invalid_debounce_count(value: object) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "presence": {"debounce_count": value}}
    )
    assert any("presence.debounce_count" in e for e in errors)


@pytest.mark.parametrize("value", [1, 3, 10])
def test_validate_accepts_valid_debounce_count(value: int) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "presence": {"debounce_count": value}}
    )
    assert not any("presence.debounce_count" in e for e in errors)


# ---------------------------------------------------------------------------
# 驗證矩陣：timer 分鐘欄位與 rest_count_mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("section", "key"),
    [
        ("timer", "work_threshold_min"),
        ("timer", "reset_threshold_min"),
        ("timer", "required_rest_min"),
        ("reminder", "repeat_interval_min"),
    ],
)
def test_validate_minute_fields(section: str, key: str) -> None:
    def make(value: object) -> dict[str, object]:
        base: dict[str, object] = {"source": {"type": "webcam"}, section: {key: value}}
        return base

    field_name = f"{section}.{key}"

    low_errors = validate(make(MINUTE_MIN - 0.01))
    assert any(field_name in e for e in low_errors)

    min_errors = validate(make(MINUTE_MIN))
    assert not any(field_name in e for e in min_errors)

    max_errors = validate(make(MINUTE_MAX))
    assert not any(field_name in e for e in max_errors)

    high_errors = validate(make(MINUTE_MAX + 0.1))
    assert any(field_name in e for e in high_errors)

    type_errors = validate(make("abc"))
    assert any(field_name in e for e in type_errors)

    bool_errors = validate(make(True))
    assert any(field_name in e for e in bool_errors)


def test_validate_reports_invalid_rest_count_mode() -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "timer": {"rest_count_mode": "invalid"}}
    )
    assert any("timer.rest_count_mode" in e for e in errors)


@pytest.mark.parametrize("mode", ["presence", "fixed"])
def test_validate_accepts_valid_rest_count_mode(mode: str) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "timer": {"rest_count_mode": mode}}
    )
    assert not any("timer.rest_count_mode" in e for e in errors)


# ---------------------------------------------------------------------------
# 驗證矩陣：rest_flow（新區段）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["always", "rest", "", None, 1, True])
def test_validate_reports_invalid_pending_accounting(value: object) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "rest_flow": {"pending_accounting": value}}
    )
    assert any("rest_flow.pending_accounting" in e for e in errors)


@pytest.mark.parametrize("value", ["work", "none"])
def test_validate_accepts_valid_pending_accounting(value: str) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "rest_flow": {"pending_accounting": value}}
    )
    assert not any("rest_flow.pending_accounting" in e for e in errors)


@pytest.mark.parametrize("value", ["punish", "work", "", None, 0])
def test_validate_reports_invalid_interrupt_behavior(value: object) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "rest_flow": {"interrupt_behavior": value}}
    )
    assert any("rest_flow.interrupt_behavior" in e for e in errors)


@pytest.mark.parametrize("value", ["remind", "new_work"])
def test_validate_accepts_valid_interrupt_behavior(value: str) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "rest_flow": {"interrupt_behavior": value}}
    )
    assert not any("rest_flow.interrupt_behavior" in e for e in errors)


@pytest.mark.parametrize("value", [0, 0.0, -5, "abc", None, True, [120]])
def test_validate_reports_invalid_rest_interrupt_after_sec(value: object) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "rest_flow": {"rest_interrupt_after_sec": value}}
    )
    assert any("rest_flow.rest_interrupt_after_sec" in e for e in errors)


@pytest.mark.parametrize("value", [1, 120, 600.5])
def test_validate_accepts_valid_rest_interrupt_after_sec(value: object) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "rest_flow": {"rest_interrupt_after_sec": value}}
    )
    assert not any("rest_flow.rest_interrupt_after_sec" in e for e in errors)


@pytest.mark.parametrize("value", [-1, 4, 1.5, "3", True, None])
def test_validate_reports_invalid_max_stage(value: object) -> None:
    errors = validate(
        {
            "source": {"type": "webcam"},
            "rest_flow": {"escalation": {"max_stage": value}},
        }
    )
    assert any("rest_flow.escalation.max_stage" in e for e in errors)


@pytest.mark.parametrize("value", [0, 1, 2, 3])
def test_validate_accepts_valid_max_stage(value: int) -> None:
    errors = validate(
        {
            "source": {"type": "webcam"},
            "rest_flow": {"escalation": {"max_stage": value}},
        }
    )
    assert not any("rest_flow.escalation.max_stage" in e for e in errors)


@pytest.mark.parametrize(
    "value",
    [
        "not-a-list",  # 非 list
        {"s1": 60},  # 非 list（dict）
        [60, 120],  # 長度 2
        [60, 120, 180, 240],  # 長度 4
        [60, "x", 180],  # 含字串
        [True, 120, 180],  # 含 bool
        [None, 120, 180],  # 含 None
        [0, 60, 120],  # 含 0（必須 > 0）
        [-10, 60, 120],  # 含負值
        [60, 60, 180],  # 非嚴格遞增（相等）
        [120, 60, 180],  # 非遞增
    ],
)
def test_validate_reports_invalid_stage_after_sec(value: object) -> None:
    errors = validate(
        {
            "source": {"type": "webcam"},
            "rest_flow": {"escalation": {"stage_after_sec": value}},
        }
    )
    assert any("rest_flow.escalation.stage_after_sec" in e for e in errors)


@pytest.mark.parametrize(
    "value",
    [
        [60, 120, 180],
        [1, 2, 3],
        [0.5, 1.5, 2.5],
        [30.0, 90.0, 300.0],
    ],
)
def test_validate_accepts_valid_stage_after_sec(value: list[float]) -> None:
    errors = validate(
        {
            "source": {"type": "webcam"},
            "rest_flow": {"escalation": {"stage_after_sec": value}},
        }
    )
    assert not any("rest_flow.escalation.stage_after_sec" in e for e in errors)


# ---------------------------------------------------------------------------
# 驗證矩陣：reminder
# ---------------------------------------------------------------------------


def test_validate_reports_invalid_reminder_method() -> None:
    errors = validate({"source": {"type": "webcam"}, "reminder": {"method": "siren"}})
    assert any("reminder.method" in e for e in errors)


@pytest.mark.parametrize("method", ["popup", "toast", "floating"])
def test_validate_accepts_valid_reminder_method(method: str) -> None:
    errors = validate({"source": {"type": "webcam"}, "reminder": {"method": method}})
    assert not any("reminder.method" in e for e in errors)


def test_validate_reports_invalid_reminding_display_mode() -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "reminder": {"reminding_display_mode": "foo"}}
    )
    assert any("reminding_display_mode" in e for e in errors)


@pytest.mark.parametrize("mode", ["overtime", "work_and_reminder"])
def test_validate_accepts_valid_reminding_display_mode(mode: str) -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "reminder": {"reminding_display_mode": mode}}
    )
    assert not any("reminding_display_mode" in e for e in errors)


def test_validate_reports_invalid_popup_media_type() -> None:
    errors = validate(
        {"source": {"type": "webcam"}, "reminder": {"popup": {"media_type": "gif"}}}
    )
    assert any("reminder.popup.media_type" in e for e in errors)


@pytest.mark.parametrize("media_type", ["image", "video"])
def test_validate_accepts_valid_popup_media_type(media_type: str) -> None:
    errors = validate(
        {
            "source": {"type": "webcam"},
            "reminder": {"popup": {"media_type": media_type}},
        }
    )
    assert not any("reminder.popup.media_type" in e for e in errors)


def test_validate_full_valid_config_has_no_errors() -> None:
    raw: dict[str, Any] = {
        "version": 2,
        "source": {"type": "webcam", "webcam_index": 1, "reconnect_interval_sec": 3.0},
        "detection": {
            "model_path": "data/model/yolov8n.pt",
            "device": "auto",
            "confidence": 0.5,
            "interval_sec": 1.0,
            "min_box_height_ratio": 0.3,
        },
        "presence": {"roi": [0.0, 0.0, 1.0, 1.0], "debounce_count": 3},
        "timer": {
            "work_threshold_min": 50.0,
            "reset_threshold_min": 5.0,
            "required_rest_min": 10.0,
            "rest_count_mode": "presence",
        },
        "rest_flow": {
            "pending_accounting": "work",
            "interrupt_behavior": "remind",
            "rest_interrupt_after_sec": 120,
            "escalation": {
                "max_stage": 3,
                "stage_after_sec": [60, 120, 180],
                "apply_to_reminding": True,
            },
        },
        "reminder": {
            "method": "popup",
            "repeat_interval_min": 2.0,
            "reminding_display_mode": "overtime",
            "popup": {"media_path": "", "media_type": "image", "sound_path": ""},
            "floating": {"position": "top-right"},
            "return_sound": {"enabled": False, "sound_path": "data/assets/Radar.mp3"},
        },
        "logging": {"enabled": True, "db_path": "data/records.sqlite"},
        "ui": {"start_minimized": False},
    }

    assert validate(raw) == []


# ---------------------------------------------------------------------------
# machine_config / escalation_policy 對映（分→秒換算）
# ---------------------------------------------------------------------------


def test_machine_config_converts_minutes_to_seconds() -> None:
    mc = machine_config(AppConfig())

    assert mc == MachineConfig(
        work_threshold_sec=3000.0,
        reset_threshold_sec=300.0,
        required_rest_sec=600.0,
        repeat_interval_sec=120.0,
        rest_count_mode="presence",
        pending_accounting="work",
        interrupt_behavior="remind",
        rest_interrupt_after_sec=120.0,
        apply_to_reminding=True,
    )


def test_machine_config_maps_custom_values() -> None:
    cfg = AppConfig()
    cfg.timer.work_threshold_min = 0.5
    cfg.timer.reset_threshold_min = 1.5
    cfg.timer.required_rest_min = 2.5
    cfg.timer.rest_count_mode = "fixed"
    cfg.reminder.repeat_interval_min = 0.1
    cfg.rest_flow.pending_accounting = "none"
    cfg.rest_flow.interrupt_behavior = "new_work"
    cfg.rest_flow.rest_interrupt_after_sec = 45.0
    cfg.rest_flow.escalation.apply_to_reminding = False

    mc = machine_config(cfg)

    assert mc.work_threshold_sec == pytest.approx(30.0)
    assert mc.reset_threshold_sec == pytest.approx(90.0)
    assert mc.required_rest_sec == pytest.approx(150.0)
    assert mc.repeat_interval_sec == pytest.approx(6.0)
    assert mc.rest_count_mode == "fixed"
    assert mc.pending_accounting == "none"
    assert mc.interrupt_behavior == "new_work"
    assert mc.rest_interrupt_after_sec == 45.0
    assert mc.apply_to_reminding is False


def test_escalation_policy_maps_defaults() -> None:
    policy = escalation_policy(AppConfig())

    assert isinstance(policy, EscalationPolicy)
    assert policy.max_stage == 3
    assert policy.stage_for(59.9) == 0
    assert policy.stage_for(60.0) == 1
    assert policy.stage_for(120.0) == 2
    assert policy.stage_for(180.0) == 3


def test_escalation_policy_respects_max_stage_cap() -> None:
    cfg = AppConfig()
    cfg.rest_flow.escalation.max_stage = 1
    cfg.rest_flow.escalation.stage_after_sec = (10.0, 20.0, 30.0)

    policy = escalation_policy(cfg)

    assert policy.max_stage == 1
    assert policy.stage_for(999.0) == 1


# ---------------------------------------------------------------------------
# clamp_roi（ROI 編輯端留邊修正用的工具，沿用上輪語意；v2 預設 roi 全幅）
# ---------------------------------------------------------------------------


def test_clamp_roi_keeps_valid_roi_unchanged() -> None:
    roi = BBox(0.3, 0.2, 0.4, 0.7)
    assert clamp_roi(roi) == roi


def test_clamp_roi_clamps_overflowing_extent() -> None:
    assert clamp_roi(BBox(0.875, 0.25, 0.25, 0.25)) == BBox(0.875, 0.25, 0.125, 0.25)


def test_clamp_roi_clamps_negative_origin() -> None:
    assert clamp_roi(BBox(-0.1, 0.2, 0.3, 0.4)) == BBox(0.0, 0.2, 0.3, 0.4)


@pytest.mark.parametrize(
    "roi",
    [
        BBox(1.5, 0.2, 0.4, 0.7),  # x>1 → clamp 後寬度歸零（退化）
        BBox(0.1, 0.2, -0.3, 0.4),  # w 負值（退化）
        BBox(0.1, 0.2, 0.3, 0.0),  # h=0（退化）
    ],
)
def test_clamp_roi_degenerate_falls_back_to_default(roi: BBox) -> None:
    assert clamp_roi(roi) == AppConfig().presence.roi
