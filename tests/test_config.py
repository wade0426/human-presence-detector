from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config import MINUTE_MAX, MINUTE_MIN, AppConfig, load_config, save_config, validate
from src.types import BBox, ResetMode


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
    config.reminder.reset_mode = ResetMode.SNOOZE
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
        ("reminder", "snooze_min"),
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
            "reminder": {"repeat_interval_min": 1.0, "snooze_min": 1.0},
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
