from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config import (
    MINUTE_MAX,
    MINUTE_MIN,
    AppConfig,
    ConfigError,
    load_config,
    save_config,
    validate,
)
from src.types import BBox


def test_load_config_returns_defaults_when_path_missing(tmp_path: Path) -> None:
    config = load_config(str(tmp_path / "missing.yaml"))
    assert config == AppConfig()


def test_load_config_fills_missing_detection_section(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "source": {"type": "webcam"},
                "presence": {"roi": [0.1, 0.2, 0.3, 0.4]},
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    config = load_config(str(path))

    assert config.detection == AppConfig().detection
    assert config.source.type == "webcam"
    assert config.presence.roi == BBox(0.1, 0.2, 0.3, 0.4)


def test_validate_reports_out_of_range_confidence() -> None:
    errors = validate({"detection": {"confidence": 2.0}})
    assert any("confidence" in error for error in errors)


def test_validate_reports_invalid_source_type() -> None:
    errors = validate({"source": {"type": "x"}})
    assert any("source.type" in error for error in errors)


def test_validate_requires_rtsp_url_for_rtsp_source() -> None:
    errors = validate({"source": {"type": "rtsp", "rtsp_url": ""}})
    assert any("rtsp_url" in error for error in errors)


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    config = AppConfig()
    config.presence.roi = BBox(0.11, 0.22, 0.33, 0.44)
    config.source.type = "webcam"

    path = tmp_path / "round-trip.yaml"
    save_config(config, str(path))

    reloaded = load_config(str(path))

    assert reloaded == config


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
        base: dict[str, object] = {
            "source": {"type": "webcam"},
            "timer": {
                "work_threshold_min": 1.0,
                "reset_threshold_min": 1.0,
                "required_rest_min": 1.0,
            },
            "reminder": {"repeat_interval_min": 1.0},
        }
        target = base[section]
        assert isinstance(target, dict)
        target[key] = value
        return base

    field_name = f"{section}.{key}"

    low_errors = validate(make(MINUTE_MIN - 0.01))
    assert any(field_name in error for error in low_errors)

    min_errors = validate(make(MINUTE_MIN))
    assert not any(field_name in error for error in min_errors)

    max_errors = validate(make(MINUTE_MAX))
    assert not any(field_name in error for error in max_errors)

    high_errors = validate(make(MINUTE_MAX + 0.1))
    assert any(field_name in error for error in high_errors)

    type_errors = validate(make("abc"))
    assert any(field_name in error for error in type_errors)


# ---------------------------------------------------------------------------
# M8 tests
# ---------------------------------------------------------------------------


def test_timer_config_default_rest_count_mode() -> None:
    """Test 1: default TimerConfig.rest_count_mode == 'presence'"""
    from src.config import TimerConfig

    assert TimerConfig().rest_count_mode == "presence"


def test_validate_rest_count_mode_invalid() -> None:
    """Test 2a: validate() reports error for invalid rest_count_mode."""
    errors = validate(
        {
            "source": {"type": "webcam"},
            "timer": {"rest_count_mode": "invalid"},
        }
    )
    assert any("rest_count_mode" in error for error in errors)


@pytest.mark.parametrize("mode", ["presence", "fixed"])
def test_validate_rest_count_mode_valid(mode: str) -> None:
    """Test 2b: validate() passes for valid rest_count_mode values."""
    errors = validate(
        {
            "source": {"type": "webcam"},
            "timer": {"rest_count_mode": mode},
        }
    )
    assert not any("rest_count_mode" in error for error in errors)


def test_load_config_ignores_legacy_reset_mode_snooze(tmp_path: Path) -> None:
    """Test 3: loading a yaml with legacy reset_mode/snooze_min does not raise."""
    path = tmp_path / "legacy.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "source": {"type": "webcam"},
                "reminder": {
                    "reset_mode": "snooze",
                    "snooze_min": 10.0,
                    "method": "popup",
                },
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    # Must not raise
    config = load_config(str(path))
    # Legacy fields are ignored — no attribute on ReminderConfig
    assert not hasattr(config.reminder, "reset_mode")
    assert not hasattr(config.reminder, "snooze_min")


def test_round_trip_preserves_rest_count_mode(tmp_path: Path) -> None:
    """Test 4: save -> load preserves rest_count_mode; output has no reset_mode/snooze."""
    from src.config import _serialize_app_config

    config = AppConfig()
    config.source.type = "webcam"
    config.timer.rest_count_mode = "fixed"

    path = tmp_path / "rt.yaml"
    save_config(config, str(path))

    reloaded = load_config(str(path))
    assert reloaded.timer.rest_count_mode == "fixed"

    payload = _serialize_app_config(reloaded)
    assert "reset_mode" not in payload.get("reminder", {})
    assert "snooze_min" not in payload.get("reminder", {})
    assert payload["timer"]["rest_count_mode"] == "fixed"


def test_schema_has_rest_count_mode_no_legacy_fields() -> None:
    """Test 5: SCHEMA contains timer.rest_count_mode and no reset_mode/snooze_min."""
    from src.ui.settings_schema import SCHEMA

    keys = [spec.key for spec in SCHEMA]
    assert "timer.rest_count_mode" in keys
    assert "reminder.reset_mode" not in keys
    assert "reminder.snooze_min" not in keys


# ---------------------------------------------------------------------------
# FR-1 tests: reminding_display_mode
# ---------------------------------------------------------------------------


def test_reminder_config_default_reminding_display_mode() -> None:
    """Default ReminderConfig.reminding_display_mode must be 'overtime'."""
    from src.config import ReminderConfig

    assert ReminderConfig().reminding_display_mode == "overtime"


def test_load_config_default_reminding_display_mode_when_field_missing(
    tmp_path: Path,
) -> None:
    """Old YAML without reminding_display_mode loads and defaults to 'overtime'."""
    path = tmp_path / "legacy.yaml"
    path.write_text(
        yaml.safe_dump(
            {"source": {"type": "webcam"}},
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    config = load_config(str(path))
    assert config.reminder.reminding_display_mode == "overtime"


def test_validate_reminding_display_mode_invalid() -> None:
    """validate() must report an error for an invalid reminding_display_mode value."""
    errors = validate(
        {
            "source": {"type": "webcam"},
            "reminder": {"reminding_display_mode": "foo"},
        }
    )
    assert any("reminding_display_mode" in e for e in errors)


@pytest.mark.parametrize("mode", ["overtime", "work_and_reminder"])
def test_validate_reminding_display_mode_valid(mode: str) -> None:
    """validate() must NOT report an error for valid reminding_display_mode values."""
    errors = validate(
        {
            "source": {"type": "webcam"},
            "reminder": {"reminding_display_mode": mode},
        }
    )
    assert not any("reminding_display_mode" in e for e in errors)


# ---------------------------------------------------------------------------
# M0 tests: ReturnSoundConfig & ForceLockConfig
# ---------------------------------------------------------------------------


def test_return_sound_defaults() -> None:
    """ReturnSoundConfig default values: enabled=False, sound_path='data/assets/Radar.mp3'."""
    from src.config import ReminderConfig

    rs = ReminderConfig().return_sound
    assert rs.enabled is False
    assert rs.sound_path == "data/assets/Radar.mp3"


def test_force_lock_defaults() -> None:
    """AppConfig().force_lock has correct default values for all five fields."""

    fl = AppConfig().force_lock
    assert fl.enabled is False
    assert fl.trigger == "overtime"
    assert fl.overtime_threshold_min == 10.0
    assert fl.warning_mode == "immediate"
    assert fl.countdown_sec == 10


def test_validate_force_lock_trigger_invalid() -> None:
    """validate() must report an error when force_lock.trigger is invalid."""
    errors = validate(
        {
            "source": {"type": "webcam"},
            "force_lock": {"trigger": "bad"},
        }
    )
    assert any("force_lock.trigger" in e for e in errors)


def test_validate_force_lock_warning_mode_invalid() -> None:
    """validate() must report an error when force_lock.warning_mode is invalid."""
    errors = validate(
        {
            "source": {"type": "webcam"},
            "force_lock": {"warning_mode": "bad"},
        }
    )
    assert any("force_lock.warning_mode" in e for e in errors)


def test_validate_countdown_sec_min() -> None:
    """validate() reports error for countdown_sec=0, but not for countdown_sec=1."""
    errors_zero = validate(
        {
            "source": {"type": "webcam"},
            "force_lock": {"countdown_sec": 0},
        }
    )
    assert any("force_lock.countdown_sec" in e for e in errors_zero)

    errors_one = validate(
        {
            "source": {"type": "webcam"},
            "force_lock": {"countdown_sec": 1},
        }
    )
    assert not any("force_lock.countdown_sec" in e for e in errors_one)


def test_roundtrip_serialize_force_lock(tmp_path: Path) -> None:
    """save -> load preserves force_lock and reminder.return_sound values."""
    config = AppConfig()
    config.source.type = "webcam"
    config.force_lock.enabled = True
    config.force_lock.trigger = "on_rest"
    config.force_lock.overtime_threshold_min = 15.0
    config.force_lock.warning_mode = "countdown_cancel"
    config.force_lock.countdown_sec = 30
    config.reminder.return_sound.enabled = True
    config.reminder.return_sound.sound_path = "data/assets/custom.mp3"

    path = tmp_path / "force-lock-rt.yaml"
    save_config(config, str(path))

    reloaded = load_config(str(path))

    assert reloaded.force_lock.enabled is True
    assert reloaded.force_lock.trigger == "on_rest"
    assert reloaded.force_lock.overtime_threshold_min == 15.0
    assert reloaded.force_lock.warning_mode == "countdown_cancel"
    assert reloaded.force_lock.countdown_sec == 30
    assert reloaded.reminder.return_sound.enabled is True
    assert reloaded.reminder.return_sound.sound_path == "data/assets/custom.mp3"


# ---------------------------------------------------------------------------
# T2 tests: presence.roi & sibling field validation (proposal §4.5)
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
    """validate() must report a presence.roi error for malformed/out-of-range roi."""
    errors = validate({"source": {"type": "webcam"}, "presence": {"roi": roi}})
    assert any("presence.roi" in e for e in errors)


@pytest.mark.parametrize(
    "roi",
    [
        [0.1, 0.2, 0.3, 0.4],
        [0, 0, 1, 1],  # 整數邊界值
        [0.3, 0.2, 0.4, 0.7],  # 預設值
        [0.0, 0.0, 0.5, 1.0],
    ],
)
def test_validate_accepts_valid_roi(roi: list[float]) -> None:
    """validate() must not report presence.roi errors for legal roi values."""
    errors = validate({"source": {"type": "webcam"}, "presence": {"roi": roi}})
    assert not any("presence.roi" in e for e in errors)


def test_validate_accepts_missing_roi() -> None:
    """Missing roi falls back to the default and must not be reported."""
    errors = validate({"source": {"type": "webcam"}, "presence": {}})
    assert not any("presence.roi" in e for e in errors)


@pytest.mark.parametrize(
    "roi",
    [
        [None, 0.2, 0.3, 0.4],
        ["abc", 0.2, 0.3, 0.4],
        "not-a-list",
        [0.1, 0.2, 0.3],
    ],
)
def test_load_config_raises_config_error_for_malformed_roi(
    tmp_path: Path, roi: object
) -> None:
    """load_config must raise ConfigError (not TypeError/ValueError) for bad roi.

    結構損壞（非數值、形狀錯誤）仍整檔拒絕；數值越界改走 clamp 遷移
    （見 test_load_config_clamps_out_of_range_roi）。
    """
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {"source": {"type": "webcam"}, "presence": {"roi": roi}},
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError) as excinfo:
        load_config(str(path))
    assert "presence.roi" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 審查修正：load_config 對 YAML 語法錯誤／IO 錯誤一律拋 ConfigError（§4.5）
# ---------------------------------------------------------------------------


def test_load_config_raises_config_error_for_broken_yaml(tmp_path: Path) -> None:
    """語法損壞的 YAML 必須以 ConfigError 呈現，而非外洩 yaml.YAMLError。"""
    path = tmp_path / "config.yaml"
    path.write_text("source: [unclosed\n  type: webcam\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(str(path))


def test_load_config_raises_config_error_for_unreadable_path(tmp_path: Path) -> None:
    """無法讀取（路徑是目錄）必須以 ConfigError 呈現，而非外洩 OSError。"""
    path = tmp_path / "config.yaml"
    path.mkdir()

    with pytest.raises(ConfigError):
        load_config(str(path))


# ---------------------------------------------------------------------------
# 審查修正（§4.8 防鎖死）：數值越界的 roi 載入時 clamp 遷移，不整檔拒絕
# ---------------------------------------------------------------------------


def _write_roi_config(tmp_path: Path, roi: list[float]) -> str:
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {"source": {"type": "webcam"}, "presence": {"roi": roi}},
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return str(path)


def test_load_config_clamps_out_of_range_roi(tmp_path: Path) -> None:
    """舊版框選寫入的 x+w>1 越界值：載入時夾回合法範圍，不得拒絕啟動。"""
    path = _write_roi_config(tmp_path, [0.875, 0.25, 0.25, 0.25])

    config = load_config(path)

    assert config.presence.roi == BBox(0.875, 0.25, 0.125, 0.25)


def test_load_config_clamps_negative_roi_origin(tmp_path: Path) -> None:
    path = _write_roi_config(tmp_path, [-0.1, 0.2, 0.3, 0.4])

    config = load_config(path)

    assert config.presence.roi == BBox(0.0, 0.2, 0.3, 0.4)


@pytest.mark.parametrize(
    "roi",
    [
        [1.5, 0.2, 0.4, 0.7],  # x>1 → clamp 後寬度歸零（退化）
        [0.1, 0.2, -0.3, 0.4],  # w 負值（退化）
        [0.1, 0.2, 0.3, 0.0],  # h=0（退化）
    ],
)
def test_load_config_degenerate_roi_falls_back_to_default(
    tmp_path: Path, roi: list[float]
) -> None:
    """clamp 後寬高歸零的退化 roi 回退預設值，仍不得拒絕啟動。"""
    path = _write_roi_config(tmp_path, roi)

    config = load_config(path)

    assert config.presence.roi == AppConfig().presence.roi


def test_clamp_roi_keeps_valid_roi_unchanged() -> None:
    from src.config import clamp_roi

    roi = BBox(0.3, 0.2, 0.4, 0.7)
    assert clamp_roi(roi) == roi


def test_clamp_roi_clamps_overflowing_extent() -> None:
    from src.config import clamp_roi

    assert clamp_roi(BBox(0.875, 0.25, 0.25, 0.25)) == BBox(0.875, 0.25, 0.125, 0.25)


@pytest.mark.parametrize("value", [0, 0.0, -1.0, "abc", None, True, [1.0]])
def test_validate_reports_invalid_detection_interval_sec(value: object) -> None:
    """detection.interval_sec must be a number > 0 (bool excluded)."""
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


@pytest.mark.parametrize("value", [0, 0.0, -5, "abc", None, True, [1.0]])
def test_validate_reports_invalid_reconnect_interval_sec(value: object) -> None:
    """source.reconnect_interval_sec must be a number > 0 (bool excluded)."""
    errors = validate(
        {"source": {"type": "webcam", "reconnect_interval_sec": value}}
    )
    assert any("source.reconnect_interval_sec" in e for e in errors)


@pytest.mark.parametrize("value", [0.5, 5, 30.0])
def test_validate_accepts_valid_reconnect_interval_sec(value: object) -> None:
    errors = validate(
        {"source": {"type": "webcam", "reconnect_interval_sec": value}}
    )
    assert not any("source.reconnect_interval_sec" in e for e in errors)


@pytest.mark.parametrize("value", [-1, 1.5, "0", None, True])
def test_validate_reports_invalid_webcam_index(value: object) -> None:
    """source.webcam_index must be an int >= 0 (bool excluded)."""
    errors = validate(
        {"source": {"type": "webcam", "webcam_index": value}}
    )
    assert any("source.webcam_index" in e for e in errors)


@pytest.mark.parametrize("value", [0, 1, 3])
def test_validate_accepts_valid_webcam_index(value: int) -> None:
    errors = validate({"source": {"type": "webcam", "webcam_index": value}})
    assert not any("source.webcam_index" in e for e in errors)

