from __future__ import annotations

from src.config import MINUTE_MAX, MINUTE_MIN, AppConfig
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
    }
    for spec in SCHEMA:
        if spec.key in minute_keys:
            assert spec.minimum == MINUTE_MIN
            assert spec.maximum == MINUTE_MAX
            assert spec.step == 0.1
            assert spec.decimals == 1


def test_schema_has_no_reset_mode_field() -> None:
    keys = [spec.key for spec in SCHEMA]
    assert "reminder.reset_mode" not in keys
    assert "reminder.snooze_min" not in keys


def test_schema_has_rest_count_mode() -> None:
    """timer.rest_count_mode should appear with choices (presence, fixed)."""
    from src.ui.settings_schema import WidgetKind

    rest_spec = next((spec for spec in SCHEMA if spec.key == "timer.rest_count_mode"), None)
    assert rest_spec is not None, "SCHEMA must contain timer.rest_count_mode"
    assert rest_spec.widget == WidgetKind.CHOICE
    assert rest_spec.choices == ("presence", "fixed")


def test_set_value_rejects_unsupported_key_depth() -> None:
    config = AppConfig()

    try:
        set_value(config, "reminder.popup.media.path", "clip.mp4")
    except ValueError as exc:
        assert "Unsupported key depth" in str(exc)
    else:
        raise AssertionError("expected ValueError for nested key depth > 3")
