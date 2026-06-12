"""記帳轉換器：將狀態機事件對映為持久化型別（SessionRecord / LedgerEvent）。

無狀態純轉換：session 邊界由狀態機決定，此處僅做型別對映。
"""

from __future__ import annotations

from src.core.events import LedgerEvent, SessionRecord, TimerEvent, TimerEventType

_SESSION_KIND_BY_TYPE: dict[TimerEventType, str] = {
    TimerEventType.WORK_ENDED: "work",
    TimerEventType.REST_ENDED: "rest",
}

_LEDGER_TYPES: frozenset[TimerEventType] = frozenset(
    {
        TimerEventType.REST_PENDING_ENTERED,
        TimerEventType.REST_PENDING_CANCELLED,
        TimerEventType.ESCALATED,
        TimerEventType.LOCK_REQUESTED,
        TimerEventType.REST_INTERRUPTED,
    }
)


class SessionTranslator:
    """事件 → (SessionRecord | None, LedgerEvent | None) 的無狀態轉換器。"""

    def translate(self, event: TimerEvent) -> tuple[SessionRecord | None, LedgerEvent | None]:
        """WORK_ENDED→work session；REST_ENDED→rest session；
        REST_PENDING_ENTERED/CANCELLED、ESCALATED(payload={'stage':n})、
        LOCK_REQUESTED、REST_INTERRUPTED→LedgerEvent；其餘→(None, None)。"""
        kind = _SESSION_KIND_BY_TYPE.get(event.type)
        if kind is not None:
            record = SessionRecord(
                kind=kind,
                start_ts=event.at - event.duration_sec,
                end_ts=event.at,
                duration_sec=event.duration_sec,
                ended_by=event.ended_by,
            )
            return record, None
        if event.type in _LEDGER_TYPES:
            payload: dict[str, object] = {}
            if event.type is TimerEventType.ESCALATED:
                payload = {"stage": event.stage}
            return None, LedgerEvent(ts=event.at, type=event.type.value, payload=payload)
        return None, None
