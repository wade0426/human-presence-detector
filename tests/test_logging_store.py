from __future__ import annotations

from datetime import datetime

from src.logging_store import SessionStore


def test_init_schema_is_idempotent() -> None:
    store = SessionStore(":memory:")
    try:
        store.init_schema()
        store.init_schema()
    finally:
        store.close()


def test_log_session_persists_work_record() -> None:
    store = SessionStore(":memory:")
    start = datetime(2026, 6, 9, 10, 0, 0)
    end = datetime(2026, 6, 9, 10, 30, 0)
    try:
        store.init_schema()
        row_id = store.log_session("work", start, end, 1800, "reset")
        row = store._connection.execute(
            "SELECT type, start_ts, end_ts, duration_sec, ended_by FROM sessions"
        ).fetchone()
    finally:
        store.close()

    assert row_id > 0
    assert row == ("work", start.isoformat(), end.isoformat(), 1800, "reset")


def test_log_session_persists_rest_type() -> None:
    store = SessionStore(":memory:")
    start = datetime(2026, 6, 9, 11, 0, 0)
    end = datetime(2026, 6, 9, 11, 5, 0)
    try:
        store.init_schema()
        row_id = store.log_session("rest", start, end, 300, "")
        row = store._connection.execute("SELECT type FROM sessions").fetchone()
    finally:
        store.close()

    assert row_id > 0
    assert row == ("rest",)
