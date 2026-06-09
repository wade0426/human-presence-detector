from __future__ import annotations

from src.config import MINUTE_MAX, MINUTE_MIN, AppConfig
from src.types import ResetMode
from src.ui.settings_schema import CATEGORIES, SCHEMA, fields_for, get_value, set_value


def test_fields_for_covers_all_categories() -> None:
    for category in CATEGORIES:
        assert len(fields_for(category)) > 0


def test_get_set_roundtrip() -> None:
    config = AppConfig()
    for spec in SCHEMA:
        original = get_value(config, spec.key)
        restored = set_value(config, spec.key, original)
        assert get_value(restored, spec.key) == original


def test_minute_fields_have_correct_constraints() -> None:
    minute_keys = {
        "timer.work_threshold_min",
        "timer.reset_threshold_min",
        "timer.required_rest_min",
        "reminder.repeat_interval_min",
        "reminder.snooze_min",
    }
    for spec in SCHEMA:
        if spec.key in minute_keys:
            assert spec.minimum == MINUTE_MIN
            assert spec.maximum == MINUTE_MAX
            assert spec.step == 0.1
            assert spec.decimals == 1


def test_schema_includes_reset_mode_choices() -> None:
    spec = next(item for item in SCHEMA if item.key == "reminder.reset_mode")
    assert spec.choices == tuple(mode.value for mode in ResetMode)


def test_set_value_rejects_unsupported_key_depth() -> None:
    config = AppConfig()

    try:
        set_value(config, "reminder.popup.media.path", "clip.mp4")
    except ValueError as exc:
        assert "Unsupported key depth" in str(exc)
    else:
        raise AssertionError("expected ValueError for nested key depth > 3")
