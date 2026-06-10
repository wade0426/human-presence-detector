from __future__ import annotations

from src.app.force_lock import ForceLockPolicy
from src.config import ForceLockConfig
from src.types import TimerSnapshot, TimerState


def _snap(state: TimerState, overtime_sec: float = 0.0) -> TimerSnapshot:
    return TimerSnapshot(
        state=state,
        work_elapsed_sec=0.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=False,
        overtime_sec=overtime_sec,
    )


def test_disabled_never_fires() -> None:
    policy = ForceLockPolicy(ForceLockConfig(enabled=False))
    # 即使是會觸發的狀態也不觸發
    results = [
        policy.observe(_snap(TimerState.RESTING)),
        policy.observe(_snap(TimerState.REMINDING, overtime_sec=999)),
    ]
    assert results == [False, False]


def test_overtime_fires_once() -> None:
    policy = ForceLockPolicy(
        ForceLockConfig(enabled=True, trigger="overtime", overtime_threshold_min=1.0)
    )
    # overtime_sec=120 > 60 秒 threshold，連續多筆
    results = [
        policy.observe(_snap(TimerState.REMINDING, overtime_sec=120)),
        policy.observe(_snap(TimerState.REMINDING, overtime_sec=130)),
        policy.observe(_snap(TimerState.REMINDING, overtime_sec=140)),
    ]
    assert results == [True, False, False]


def test_overtime_resets_next_cycle() -> None:
    policy = ForceLockPolicy(
        ForceLockConfig(enabled=True, trigger="overtime", overtime_threshold_min=1.0)
    )
    # 第一次觸發 → RESTING → WORKING → 再次 REMINDING 超門檻
    r1 = policy.observe(_snap(TimerState.REMINDING, overtime_sec=120))  # True
    r2 = policy.observe(_snap(TimerState.RESTING))                       # False（重置 _fired）
    r3 = policy.observe(_snap(TimerState.WORKING))                       # False
    r4 = policy.observe(_snap(TimerState.REMINDING, overtime_sec=120))  # True（再次觸發）
    assert r1 is True
    assert r2 is False
    assert r3 is False
    assert r4 is True


def test_overtime_below_threshold_no_fire() -> None:
    policy = ForceLockPolicy(
        ForceLockConfig(enabled=True, trigger="overtime", overtime_threshold_min=5.0)
    )
    # threshold=300 秒，overtime_sec=60 不夠
    result = policy.observe(_snap(TimerState.REMINDING, overtime_sec=60))
    assert result is False


def test_on_rest_fires_on_entering_resting() -> None:
    policy = ForceLockPolicy(ForceLockConfig(enabled=True, trigger="on_rest"))
    r1 = policy.observe(_snap(TimerState.WORKING))   # False
    r2 = policy.observe(_snap(TimerState.RESTING))   # True（進入 RESTING）
    r3 = policy.observe(_snap(TimerState.RESTING))   # False（同週期第二筆）
    assert r1 is False
    assert r2 is True
    assert r3 is False


def test_suspended_does_not_retrigger() -> None:
    policy = ForceLockPolicy(
        ForceLockConfig(enabled=True, trigger="overtime", overtime_threshold_min=1.0)
    )
    # 已觸發 → SUSPENDED → 再次 REMINDING 超門檻，不應再觸發
    r1 = policy.observe(_snap(TimerState.REMINDING, overtime_sec=120))  # True（觸發）
    r2 = policy.observe(_snap(TimerState.SUSPENDED))                    # False（凍結）
    r3 = policy.observe(_snap(TimerState.REMINDING, overtime_sec=130))  # False（_fired 未被重置）
    assert r1 is True
    assert r2 is False
    assert r3 is False
