from __future__ import annotations

import pytest

from src.core.escalation import EscalationPolicy

DEFAULT_STAGES: tuple[float, float, float] = (60.0, 120.0, 180.0)


def _policy(
    stage_after_sec: tuple[float, float, float] = DEFAULT_STAGES,
    max_stage: int = 3,
) -> EscalationPolicy:
    return EscalationPolicy(stage_after_sec, max_stage)


# ──────────────────────────────────────────────────────────────────────────────
# 邊界：dwell<s1→0；≥s1→1；≥s2→2；≥s3→3
# ──────────────────────────────────────────────────────────────────────────────


def test_dwell_below_first_threshold_is_stage_zero() -> None:
    policy = _policy()
    assert policy.stage_for(0.0) == 0
    assert policy.stage_for(59.9) == 0


def test_dwell_at_thresholds_is_inclusive() -> None:
    policy = _policy()
    assert policy.stage_for(60.0) == 1
    assert policy.stage_for(120.0) == 2
    assert policy.stage_for(180.0) == 3


def test_dwell_between_thresholds_keeps_lower_stage() -> None:
    policy = _policy()
    assert policy.stage_for(119.9) == 1
    assert policy.stage_for(179.9) == 2


def test_dwell_far_beyond_last_threshold_stays_at_three() -> None:
    policy = _policy()
    assert policy.stage_for(99999.0) == 3


def test_negative_dwell_is_stage_zero() -> None:
    policy = _policy()
    assert policy.stage_for(-1.0) == 0


# ──────────────────────────────────────────────────────────────────────────────
# max_stage 封頂
# ──────────────────────────────────────────────────────────────────────────────


def test_max_stage_caps_result() -> None:
    policy = _policy(max_stage=1)
    assert policy.stage_for(999.0) == 1


def test_max_stage_two_caps_at_two() -> None:
    policy = _policy(max_stage=2)
    assert policy.stage_for(180.0) == 2
    assert policy.stage_for(119.9) == 1


def test_max_stage_zero_is_always_zero() -> None:
    policy = _policy(max_stage=0)
    assert policy.stage_for(0.0) == 0
    assert policy.stage_for(60.0) == 0
    assert policy.stage_for(1e9) == 0


def test_max_stage_property_exposes_constructor_value() -> None:
    assert _policy(max_stage=3).max_stage == 3
    assert _policy(max_stage=0).max_stage == 0


# ──────────────────────────────────────────────────────────────────────────────
# 純函式（無狀態）
# ──────────────────────────────────────────────────────────────────────────────


def test_stage_for_is_stateless_pure_function() -> None:
    policy = _policy()
    assert policy.stage_for(200.0) == 3
    # 再以較小 dwell 查詢不受先前呼叫影響（無遲滯、無內部狀態）
    assert policy.stage_for(10.0) == 0
    assert policy.stage_for(200.0) == 3


# ──────────────────────────────────────────────────────────────────────────────
# 建構驗證
# ──────────────────────────────────────────────────────────────────────────────


def test_non_increasing_thresholds_raise_value_error() -> None:
    with pytest.raises(ValueError):
        EscalationPolicy((60.0, 60.0, 180.0), 3)
    with pytest.raises(ValueError):
        EscalationPolicy((120.0, 60.0, 180.0), 3)
    with pytest.raises(ValueError):
        EscalationPolicy((60.0, 120.0, 120.0), 3)


def test_non_positive_first_threshold_raises_value_error() -> None:
    with pytest.raises(ValueError):
        EscalationPolicy((-1.0, 60.0, 120.0), 3)
    with pytest.raises(ValueError):
        EscalationPolicy((0.0, 60.0, 120.0), 3)


def test_max_stage_out_of_range_raises_value_error() -> None:
    with pytest.raises(ValueError):
        EscalationPolicy(DEFAULT_STAGES, -1)
    with pytest.raises(ValueError):
        EscalationPolicy(DEFAULT_STAGES, 4)
