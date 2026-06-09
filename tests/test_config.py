from __future__ import annotations

from pathlib import Path

import yaml

from src.config import AppConfig, load_config, save_config, validate
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
