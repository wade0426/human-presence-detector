"""T9：設定頁 schema v2 — 鍵存在/分類/choices/roundtrip/tooltip/stage 三欄虛擬鍵。"""

from __future__ import annotations

from src.infra.config import (
    MINUTE_MAX,
    MINUTE_MIN,
    AppConfig,
    _serialize_app_config,
)
from src.shell.settings.schema import (
    CATEGORIES,
    SCHEMA,
    STAGE_FIELD_KEYS,
    FieldSpec,
    WidgetKind,
    fields_for,
    get_value,
    set_value,
    tooltip_for,
)


def _spec_for(key: str) -> FieldSpec:
    spec = next((spec for spec in SCHEMA if spec.key == key), None)
    assert spec is not None, f"SCHEMA must contain {key}"
    return spec


# ---------------------------------------------------------------------------
# 分類 v2
# ---------------------------------------------------------------------------


def test_categories_v2() -> None:
    assert CATEGORIES == ("基本", "偵測", "提醒", "休息流程", "紀錄", "進階")


def test_categories_drop_force_lock() -> None:
    assert "強制休息" not in CATEGORIES


def test_fields_for_covers_all_categories() -> None:
    for category in CATEGORIES:
        assert len(fields_for(category)) > 0


def test_schema_has_no_force_lock_fields() -> None:
    keys = [spec.key for spec in SCHEMA]
    assert not any(key.startswith("force_lock.") for key in keys)


# ---------------------------------------------------------------------------
# get/set roundtrip（含 stage 虛擬鍵）
# ---------------------------------------------------------------------------


def test_get_set_roundtrip() -> None:
    config = AppConfig()
    for spec in SCHEMA:
        original = get_value(config, spec.key)
        restored = set_value(config, spec.key, original)
        assert get_value(restored, spec.key) == original


def test_set_value_rejects_unsupported_key_depth() -> None:
    config = AppConfig()
    try:
        set_value(config, "reminder.popup.media.path", "clip.mp4")
    except ValueError as exc:
        assert "Unsupported key depth" in str(exc)
    else:
        raise AssertionError("expected ValueError for nested key depth > 3")


# ---------------------------------------------------------------------------
# 既有欄位（v1 對等保留）
# ---------------------------------------------------------------------------


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


def test_schema_has_rest_count_mode() -> None:
    spec = _spec_for("timer.rest_count_mode")
    assert spec.widget == WidgetKind.CHOICE
    assert spec.choices == ("presence", "fixed")


def test_reminding_display_mode_choices() -> None:
    spec = _spec_for("reminder.reminding_display_mode")
    assert spec.widget == WidgetKind.CHOICE
    assert spec.choices == ("overtime", "work_and_reminder")


def test_return_sound_fields_in_reminder_category() -> None:
    for spec in SCHEMA:
        if spec.key.startswith("reminder.return_sound."):
            assert spec.category == "提醒"


def test_method_tooltip_mentions_floating() -> None:
    spec = _spec_for("reminder.method")
    tooltip = tooltip_for(spec)
    assert "floating" in tooltip
    assert "角落" in tooltip


# ---------------------------------------------------------------------------
# 休息流程（新分類）
# ---------------------------------------------------------------------------


def test_pending_accounting_field() -> None:
    spec = _spec_for("rest_flow.pending_accounting")
    assert spec.widget == WidgetKind.CHOICE
    assert spec.choices == ("work", "none")
    assert spec.category == "休息流程"


def test_interrupt_behavior_field() -> None:
    spec = _spec_for("rest_flow.interrupt_behavior")
    assert spec.widget == WidgetKind.CHOICE
    assert spec.choices == ("remind", "new_work")
    assert spec.category == "休息流程"


def test_rest_interrupt_after_sec_field() -> None:
    spec = _spec_for("rest_flow.rest_interrupt_after_sec")
    assert spec.widget == WidgetKind.INT
    assert spec.category == "休息流程"
    assert spec.minimum == 1
    assert spec.maximum is not None and spec.maximum >= 180


def test_max_stage_field_is_choice_0_to_3() -> None:
    spec = _spec_for("rest_flow.escalation.max_stage")
    assert spec.widget == WidgetKind.CHOICE
    assert spec.choices == ("0", "1", "2", "3")
    assert spec.category == "休息流程"


def test_apply_to_reminding_field() -> None:
    spec = _spec_for("rest_flow.escalation.apply_to_reminding")
    assert spec.widget == WidgetKind.BOOL
    assert spec.category == "休息流程"


def test_stage_fields_are_int_in_rest_flow_category() -> None:
    assert tuple(STAGE_FIELD_KEYS) == (
        "rest_flow.escalation.stage1_sec",
        "rest_flow.escalation.stage2_sec",
        "rest_flow.escalation.stage3_sec",
    )
    for key in STAGE_FIELD_KEYS:
        spec = _spec_for(key)
        assert spec.widget == WidgetKind.INT
        assert spec.category == "休息流程"
        assert spec.minimum == 1
        # QSpinBox 預設上限 99，未設 maximum 會把預設值 180 砍掉。
        assert spec.maximum is not None and spec.maximum >= 180


def test_all_rest_flow_fields_have_tooltip() -> None:
    for spec in SCHEMA:
        if spec.key.startswith("rest_flow."):
            assert spec.tooltip is not None and spec.tooltip.strip() != "", (
                f"Field {spec.key} should have a non-empty tooltip"
            )


# ---------------------------------------------------------------------------
# stage 三欄虛擬鍵 ↔ list 對映
# ---------------------------------------------------------------------------


def test_stage_virtual_keys_read_from_tuple() -> None:
    config = AppConfig()
    assert get_value(config, "rest_flow.escalation.stage1_sec") == 60.0
    assert get_value(config, "rest_flow.escalation.stage2_sec") == 120.0
    assert get_value(config, "rest_flow.escalation.stage3_sec") == 180.0


def test_stage_virtual_keys_write_back_to_tuple() -> None:
    config = AppConfig()
    config = set_value(config, "rest_flow.escalation.stage1_sec", 10)
    config = set_value(config, "rest_flow.escalation.stage2_sec", 20)
    config = set_value(config, "rest_flow.escalation.stage3_sec", 30)
    assert config.rest_flow.escalation.stage_after_sec == (10.0, 20.0, 30.0)


def test_stage_virtual_keys_do_not_touch_siblings() -> None:
    config = AppConfig()
    updated = set_value(config, "rest_flow.escalation.stage2_sec", 90)
    assert updated.rest_flow.escalation.stage_after_sec == (60.0, 90.0, 180.0)
    assert updated.rest_flow.escalation.max_stage == config.rest_flow.escalation.max_stage
    # 原 config 不被就地修改
    assert config.rest_flow.escalation.stage_after_sec == (60.0, 120.0, 180.0)


def test_stage_values_serialize_back_to_list() -> None:
    """存檔時三個虛擬鍵組回 stage_after_sec list（payload 無 stage1_sec 等假鍵）。"""
    config = AppConfig()
    config = set_value(config, "rest_flow.escalation.stage1_sec", 10)
    config = set_value(config, "rest_flow.escalation.stage2_sec", 20)
    config = set_value(config, "rest_flow.escalation.stage3_sec", 30)
    payload = _serialize_app_config(config)
    escalation = payload["rest_flow"]["escalation"]
    assert escalation["stage_after_sec"] == [10.0, 20.0, 30.0]
    assert "stage1_sec" not in escalation
    assert "stage2_sec" not in escalation
    assert "stage3_sec" not in escalation


def test_max_stage_set_value_coerces_choice_string_to_int() -> None:
    """CHOICE widget 取值為字串，set_value 必須轉回 int 才能通過 validate。"""
    config = AppConfig()
    updated = set_value(config, "rest_flow.escalation.max_stage", "1")
    assert get_value(updated, "rest_flow.escalation.max_stage") == 1
    assert isinstance(updated.rest_flow.escalation.max_stage, int)


# ---------------------------------------------------------------------------
# hint / tooltip
# ---------------------------------------------------------------------------


def test_every_field_has_hint() -> None:
    for spec in SCHEMA:
        assert spec.hint.strip() != "", f"Field {spec.key} has empty hint"


def test_tooltip_for_falls_back_to_hint() -> None:
    sample = next(spec for spec in SCHEMA if spec.tooltip is None)
    assert tooltip_for(sample) == sample.hint


def test_existing_fields_have_tooltips() -> None:
    keys_with_tooltip = {
        "reminder.method",
        "timer.rest_count_mode",
        "reminder.reminding_display_mode",
        "presence.debounce_count",
        "detection.confidence",
        "detection.min_box_height_ratio",
        "detection.device",
    }
    for spec in SCHEMA:
        if spec.key in keys_with_tooltip:
            assert spec.tooltip is not None and spec.tooltip.strip() != ""


# ---------------------------------------------------------------------------
# 音檔欄位 key 清單（FR-2.7 / FR-3.1 鎖定）
# ---------------------------------------------------------------------------


def test_sound_field_keys_locked() -> None:
    from src.shell.settings.window import SOUND_FIELD_KEYS

    assert SOUND_FIELD_KEYS == (
        "reminder.popup.sound_path",
        "reminder.return_sound.sound_path",
    )

    specs = {spec.key: spec for spec in SCHEMA}
    for key in SOUND_FIELD_KEYS:
        assert key in specs, f"SCHEMA must contain {key}"
        assert specs[key].widget == WidgetKind.PATH
