from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config import MINUTE_MAX, MINUTE_MIN, AppConfig, load_config, save_config, validate
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

