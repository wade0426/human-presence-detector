from __future__ import annotations

from src.core.accounting import SessionTranslator
from src.core.events import LedgerEvent, SessionRecord, TimerEvent, TimerEventType


def _translator() -> SessionTranslator:
    return SessionTranslator()


# ──────────────────────────────────────────────────────────────────────────────
# WORK_ENDED → work SessionRecord（start_ts = at − duration_sec；ended_by 透傳）
# ──────────────────────────────────────────────────────────────────────────────


def test_work_ended_maps_to_work_session_record() -> None:
    event = TimerEvent(
        type=TimerEventType.WORK_ENDED, at=1000.0, duration_sec=300.0, ended_by="rest"
    )
    record, ledger = _translator().translate(event)
    assert ledger is None
    assert record == SessionRecord(
        kind="work", start_ts=700.0, end_ts=1000.0, duration_sec=300.0, ended_by="rest"
    )


def test_work_ended_passes_through_each_ended_by_value() -> None:
    translator = _translator()
    for ended_by in ("reset", "rest", "rest_pending", "interrupted"):
        event = TimerEvent(
            type=TimerEventType.WORK_ENDED, at=50.0, duration_sec=20.0, ended_by=ended_by
        )
        record, ledger = translator.translate(event)
        assert ledger is None
        assert record is not None
        assert record.kind == "work"
        assert record.ended_by == ended_by


# ──────────────────────────────────────────────────────────────────────────────
# REST_ENDED → rest SessionRecord
# ──────────────────────────────────────────────────────────────────────────────


def test_rest_ended_maps_to_rest_session_record() -> None:
    event = TimerEvent(type=TimerEventType.REST_ENDED, at=2000.0, duration_sec=600.0)
    record, ledger = _translator().translate(event)
    assert ledger is None
    assert record == SessionRecord(
        kind="rest", start_ts=1400.0, end_ts=2000.0, duration_sec=600.0, ended_by=""
    )


def test_rest_ended_interrupted_passes_through_ended_by() -> None:
    event = TimerEvent(
        type=TimerEventType.REST_ENDED, at=130.0, duration_sec=45.0, ended_by="interrupted"
    )
    record, ledger = _translator().translate(event)
    assert ledger is None
    assert record == SessionRecord(
        kind="rest", start_ts=85.0, end_ts=130.0, duration_sec=45.0, ended_by="interrupted"
    )


# ──────────────────────────────────────────────────────────────────────────────
# ESCALATED → LedgerEvent(payload={"stage": n})
# ──────────────────────────────────────────────────────────────────────────────


def test_escalated_maps_to_ledger_event_with_stage_payload() -> None:
    translator = _translator()
    for stage in (1, 2, 3):
        event = TimerEvent(type=TimerEventType.ESCALATED, at=321.0, stage=stage)
        record, ledger = translator.translate(event)
        assert record is None
        assert ledger == LedgerEvent(ts=321.0, type="escalated", payload={"stage": stage})


# ──────────────────────────────────────────────────────────────────────────────
# REST_PENDING_ENTERED / CANCELLED / LOCK_REQUESTED / REST_INTERRUPTED → LedgerEvent
# ──────────────────────────────────────────────────────────────────────────────


def test_ledger_only_events_map_with_empty_payload() -> None:
    translator = _translator()
    cases = (
        (TimerEventType.REST_PENDING_ENTERED, "rest_pending_entered"),
        (TimerEventType.REST_PENDING_CANCELLED, "rest_pending_cancelled"),
        (TimerEventType.LOCK_REQUESTED, "lock_requested"),
        (TimerEventType.REST_INTERRUPTED, "rest_interrupted"),
    )
    for event_type, expected_type in cases:
        event = TimerEvent(type=event_type, at=77.5)
        record, ledger = translator.translate(event)
        assert record is None
        assert ledger == LedgerEvent(ts=77.5, type=expected_type, payload={})


# ──────────────────────────────────────────────────────────────────────────────
# 其餘事件 → (None, None)
# ──────────────────────────────────────────────────────────────────────────────


def test_other_events_translate_to_none_pair() -> None:
    translator = _translator()
    for event_type in (
        TimerEventType.WORK_STARTED,
        TimerEventType.REMINDER_TRIGGERED,
        TimerEventType.REMINDER_REPEATED,
        TimerEventType.REST_STARTED,
        TimerEventType.RETURN_PROMPT,
    ):
        event = TimerEvent(type=event_type, at=10.0)
        assert translator.translate(event) == (None, None)


# ──────────────────────────────────────────────────────────────────────────────
# 無狀態：同一實例重複轉換互不影響
# ──────────────────────────────────────────────────────────────────────────────


def test_translate_is_stateless_across_calls() -> None:
    translator = _translator()
    work = TimerEvent(type=TimerEventType.WORK_ENDED, at=100.0, duration_sec=40.0, ended_by="rest")
    first = translator.translate(work)
    translator.translate(TimerEvent(type=TimerEventType.ESCALATED, at=110.0, stage=2))
    second = translator.translate(work)
    assert first == second
