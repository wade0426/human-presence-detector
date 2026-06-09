from __future__ import annotations

import threading
from datetime import datetime

from src.logging_store import SessionStore, TodaySummary


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


def test_store_can_initialize_and_write_from_different_thread() -> None:
    store = SessionStore(":memory:")
    start = datetime(2026, 6, 9, 12, 0, 0)
    end = datetime(2026, 6, 9, 12, 5, 0)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            store.init_schema()
            store.log_session("work", start, end, 300, "reset")
            row = store._connection.execute("SELECT COUNT(*) FROM sessions").fetchone()
            assert row == (1,)
        except BaseException as exc:  # pragma: no cover - captured for assertion below
            errors.append(exc)
        finally:
            store.close()

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=1.0)

    assert not errors


def test_today_summary_empty(tmp_path: object) -> None:
    store = SessionStore(str(tmp_path / "test.db"))
    try:
        store.init_schema()
        summary = store.today_summary(now=datetime(2024, 1, 15, 12, 0))
    finally:
        store.close()

    assert summary == TodaySummary(work_seconds=0, rest_count=0, work_sessions=0)


def test_today_summary_counts_only_today(tmp_path: object) -> None:
    store = SessionStore(str(tmp_path / "test.db"))
    today = datetime(2024, 1, 15, 10, 0)
    try:
        store.init_schema()
        store.log_session(
            "work",
            datetime(2024, 1, 15, 9, 0),
            datetime(2024, 1, 15, 9, 30),
            1800,
            "",
        )
        store.log_session(
            "rest",
            datetime(2024, 1, 15, 9, 30),
            datetime(2024, 1, 15, 9, 35),
            300,
            "",
        )
        store.log_session(
            "work",
            datetime(2024, 1, 14, 9, 0),
            datetime(2024, 1, 14, 9, 30),
            1800,
            "",
        )
        summary = store.today_summary(now=today)
    finally:
        store.close()

    assert summary.work_seconds == 1800
    assert summary.rest_count == 1
    assert summary.work_sessions == 1
