from __future__ import annotations

from src.config import MINUTE_MAX, MINUTE_MIN, AppConfig
from src.ui.settings_schema import CATEGORIES, SCHEMA, fields_for, get_value, set_value, tooltip_for


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


# ---------------------------------------------------------------------------
# FR-1 tests: reminder.reminding_display_mode in schema
# ---------------------------------------------------------------------------


def test_schema_has_reminding_display_mode_field() -> None:
    """SCHEMA must contain the reminder.reminding_display_mode entry."""
    keys = [spec.key for spec in SCHEMA]
    assert "reminder.reminding_display_mode" in keys


def test_reminding_display_mode_choices() -> None:
    """reminder.reminding_display_mode choices must be ('overtime', 'work_and_reminder')."""
    from src.ui.settings_schema import WidgetKind

    spec = next(
        (s for s in SCHEMA if s.key == "reminder.reminding_display_mode"), None
    )
    assert spec is not None
    assert spec.widget == WidgetKind.CHOICE
    assert spec.choices == ("overtime", "work_and_reminder")


def test_get_set_reminding_display_mode() -> None:
    """get_value / set_value round-trip for reminder.reminding_display_mode."""
    config = AppConfig()
    original = get_value(config, "reminder.reminding_display_mode")
    assert original == "overtime"

    updated = set_value(config, "reminder.reminding_display_mode", "work_and_reminder")
    assert get_value(updated, "reminder.reminding_display_mode") == "work_and_reminder"

    restored = set_value(updated, "reminder.reminding_display_mode", original)
    assert get_value(restored, "reminder.reminding_display_mode") == original


# ---------------------------------------------------------------------------
# M4 Tests — tooltip_for, new categories, new fields
# ---------------------------------------------------------------------------


def test_every_field_has_hint() -> None:
    for spec in SCHEMA:
        assert spec.hint.strip() != "", f"Field {spec.key} has empty hint"


def test_tooltip_for_falls_back_to_hint() -> None:
    sample = next(spec for spec in SCHEMA if spec.tooltip is None)
    assert tooltip_for(sample) == sample.hint


def test_method_tooltip_mentions_floating() -> None:
    spec = next(spec for spec in SCHEMA if spec.key == "reminder.method")
    tooltip = tooltip_for(spec)
    assert "floating" in tooltip
    assert "角落" in tooltip


def test_categories_contains_force_lock() -> None:
    assert "強制休息" in CATEGORIES


def test_force_lock_fields_exist_in_schema() -> None:
    keys = [spec.key for spec in SCHEMA]
    assert "force_lock.enabled" in keys
    assert "force_lock.trigger" in keys
    assert "force_lock.warning_mode" in keys
    assert "force_lock.overtime_threshold_min" in keys
    assert "force_lock.countdown_sec" in keys


def test_return_sound_fields_exist_in_schema() -> None:
    keys = [spec.key for spec in SCHEMA]
    assert "reminder.return_sound.enabled" in keys
    assert "reminder.return_sound.sound_path" in keys


def test_force_lock_fields_in_correct_category() -> None:
    for spec in SCHEMA:
        if spec.key.startswith("force_lock."):
            assert spec.category == "強制休息", (
                f"Expected '強制休息' for {spec.key}, got {spec.category!r}"
            )


def test_return_sound_fields_in_reminder_category() -> None:
    for spec in SCHEMA:
        if spec.key.startswith("reminder.return_sound."):
            assert spec.category == "提醒", (
                f"Expected '提醒' for {spec.key}, got {spec.category!r}"
            )


def test_fields_for_force_lock_category() -> None:
    fields = fields_for("強制休息")
    assert len(fields) > 0


def test_existing_fields_have_tooltips() -> None:
    keys_with_tooltip = {
        "reminder.method",
        "timer.rest_count_mode",
        "reminder.reminding_display_mode",
        "presence.debounce_count",
        "detection.confidence",
        "presence.min_box_height_ratio",
        "detection.device",
    }
    for spec in SCHEMA:
        if spec.key in keys_with_tooltip:
            assert spec.tooltip is not None and spec.tooltip.strip() != "", (
                f"Field {spec.key} should have a non-empty tooltip"
            )
