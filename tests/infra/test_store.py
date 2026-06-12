"""src/infra/store.py（RecordStore，schema v2）測試。

涵蓋：init_schema 建表＋user_version=2、版本不符重建、log_session/log_event
讀回、today 統計只算今日（跨日）、clear_today/clear_all 筆數、payload JSON
round-trip、per-thread 連線（移植 tests/test_logging_store.py 的對應測試）。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import pytest

from src.infra.store import RecordStore

try:
    from src.core.events import LedgerEvent, SessionRecord
except ImportError:  # pragma: no cover - T1 落地前的本地替身（欄位依計畫「鎖定介面」）
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class SessionRecord:  # type: ignore[no-redef]
        kind: str
        start_ts: float
        end_ts: float
        duration_sec: float
        ended_by: str

    @dataclass(frozen=True)
    class LedgerEvent:  # type: ignore[no-redef]
        ts: float
        type: str
        payload: dict[str, object]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def ts(*args: int) -> float:
    return datetime(*args).timestamp()


def work(start_ts: float, duration_sec: float, ended_by: str = "reset") -> SessionRecord:
    return SessionRecord(
        kind="work",
        start_ts=start_ts,
        end_ts=start_ts + duration_sec,
        duration_sec=duration_sec,
        ended_by=ended_by,
    )


def rest(start_ts: float, duration_sec: float, ended_by: str = "") -> SessionRecord:
    return SessionRecord(
        kind="rest",
        start_ts=start_ts,
        end_ts=start_ts + duration_sec,
        duration_sec=duration_sec,
        ended_by=ended_by,
    )


def make_store(tmp_path: Path, name: str = "records.sqlite") -> RecordStore:
    return RecordStore(str(tmp_path / name))


# ---------------------------------------------------------------------------
# init_schema：建表、user_version、重建
# ---------------------------------------------------------------------------


def test_init_schema_creates_tables_and_sets_user_version(tmp_path: Path) -> None:
    db_path = str(tmp_path / "records.sqlite")
    store = RecordStore(db_path)
    try:
        store.init_schema()
    finally:
        store.close()

    raw = sqlite3.connect(db_path)
    try:
        names = {
            row[0]
            for row in raw.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        version = raw.execute("PRAGMA user_version").fetchone()[0]
    finally:
        raw.close()

    assert {"sessions", "events"} <= names
    assert version == 2


def test_init_schema_is_idempotent_and_keeps_data(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    try:
        store.init_schema()
        store.log_session(work(ts(2026, 6, 9, 10, 0), 1800.0))
        store.init_schema()  # user_version 已是 2 → 不得 drop
        count = store._connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    finally:
        store.close()

    assert count == 1


def test_init_schema_rebuilds_when_user_version_mismatch(tmp_path: Path) -> None:
    db_path = str(tmp_path / "records.sqlite")
    # 手動建一個 v0 舊表（舊 SessionStore schema），user_version 預設 0
    raw = sqlite3.connect(db_path)
    raw.execute(
        """
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            start_ts TEXT NOT NULL,
            end_ts TEXT,
            duration_sec INTEGER,
            ended_by TEXT
        )
        """
    )
    raw.execute(
        "INSERT INTO sessions (type, start_ts, end_ts, duration_sec, ended_by)"
        " VALUES ('work', '2026-06-09T10:00:00', '2026-06-09T10:30:00', 1800, 'reset')"
    )
    raw.commit()
    raw.close()

    store = RecordStore(db_path)
    try:
        store.init_schema()  # 不炸、直接重建
        # 重建後為空表，且新欄位（kind）可寫
        store.log_session(work(ts(2026, 6, 9, 11, 0), 600.0))
        rows = store._connection.execute("SELECT kind, duration_sec FROM sessions").fetchall()
        version = store._connection.execute("PRAGMA user_version").fetchone()[0]
    finally:
        store.close()

    assert rows == [("work", 600.0)]
    assert version == 2


# ---------------------------------------------------------------------------
# log_session / log_event：寫入讀回
# ---------------------------------------------------------------------------


def test_log_session_roundtrip(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    start = ts(2026, 6, 9, 10, 0)
    try:
        store.init_schema()
        store.log_session(work(start, 1800.0, ended_by="rest"))
        row = store._connection.execute(
            "SELECT kind, start_ts, end_ts, duration_sec, ended_by FROM sessions"
        ).fetchone()
    finally:
        store.close()

    assert row == ("work", start, start + 1800.0, 1800.0, "rest")


def test_log_session_rejects_unknown_kind(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    bad = SessionRecord(kind="play", start_ts=0.0, end_ts=1.0, duration_sec=1.0, ended_by="")
    try:
        store.init_schema()
        with pytest.raises(sqlite3.IntegrityError):
            store.log_session(bad)
    finally:
        store.close()


def test_log_event_payload_json_roundtrip(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    payload: dict[str, object] = {"stage": 3, "note": "鎖屏"}
    try:
        store.init_schema()
        store.log_event(LedgerEvent(ts=ts(2026, 6, 9, 10, 5), type="escalated", payload=payload))
        row = store._connection.execute("SELECT ts, type, payload FROM events").fetchone()
    finally:
        store.close()

    assert row[0] == ts(2026, 6, 9, 10, 5)
    assert row[1] == "escalated"
    assert json.loads(row[2]) == payload


def test_log_event_empty_payload(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    try:
        store.init_schema()
        store.log_event(LedgerEvent(ts=1000.0, type="rest_pending_entered", payload={}))
        row = store._connection.execute("SELECT payload FROM events").fetchone()
    finally:
        store.close()

    assert json.loads(row[0]) == {}


# ---------------------------------------------------------------------------
# today 統計：只算今日
# ---------------------------------------------------------------------------


def test_today_stats_empty(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    now = datetime(2026, 6, 9, 12, 0)
    try:
        store.init_schema()
        assert store.today_work_seconds(now=now) == 0.0
        assert store.today_rest_count(now=now) == 0
    finally:
        store.close()


def test_today_work_seconds_counts_only_today_work(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    now = datetime(2026, 6, 9, 12, 0)
    try:
        store.init_schema()
        store.log_session(work(ts(2026, 6, 9, 9, 0), 1800.0))  # 今日 work
        store.log_session(rest(ts(2026, 6, 9, 9, 30), 300.0))  # 今日 rest（不算 work）
        store.log_session(work(ts(2026, 6, 8, 9, 0), 3600.0))  # 昨日 work（不算）
        total = store.today_work_seconds(now=now)
    finally:
        store.close()

    assert total == 1800.0


def test_today_rest_count_counts_only_today_rest(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    now = datetime(2026, 6, 9, 12, 0)
    try:
        store.init_schema()
        store.log_session(rest(ts(2026, 6, 9, 9, 30), 300.0))  # 今日
        store.log_session(rest(ts(2026, 6, 9, 11, 0), 600.0))  # 今日
        store.log_session(rest(ts(2026, 6, 8, 9, 30), 300.0))  # 昨日
        store.log_session(work(ts(2026, 6, 9, 8, 0), 1800.0))  # work 不算
        count = store.today_rest_count(now=now)
    finally:
        store.close()

    assert count == 2


def test_today_boundary_is_local_midnight(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    now = datetime(2026, 6, 9, 12, 0)
    try:
        store.init_schema()
        store.log_session(work(ts(2026, 6, 9, 0, 0, 0), 60.0))  # 今日 00:00:00 → 算
        store.log_session(work(ts(2026, 6, 8, 23, 59, 59), 60.0))  # 昨日 23:59:59 → 不算
        total = store.today_work_seconds(now=now)
    finally:
        store.close()

    assert total == 60.0


# ---------------------------------------------------------------------------
# clear_today / clear_all：筆數（兩表合計）
# ---------------------------------------------------------------------------


def test_clear_today_removes_only_today_rows_in_both_tables(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    now = datetime(2026, 6, 9, 12, 0)
    try:
        store.init_schema()
        store.log_session(work(ts(2026, 6, 9, 9, 0), 1800.0))  # 今日 session
        store.log_session(work(ts(2026, 6, 8, 9, 0), 1800.0))  # 昨日 session
        store.log_event(LedgerEvent(ts=ts(2026, 6, 9, 9, 5), type="escalated", payload={}))
        store.log_event(LedgerEvent(ts=ts(2026, 6, 8, 9, 5), type="escalated", payload={}))

        deleted = store.clear_today(now=now)

        sessions_left = store._connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        events_left = store._connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        total_after = store.today_work_seconds(now=now)
    finally:
        store.close()

    assert deleted == 2  # 今日 1 session ＋ 1 event
    assert sessions_left == 1  # 昨日仍在
    assert events_left == 1
    assert total_after == 0.0


def test_clear_all_empties_both_tables(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    now = datetime(2026, 6, 9, 12, 0)
    try:
        store.init_schema()
        store.log_session(work(ts(2026, 6, 9, 9, 0), 1800.0))
        store.log_session(rest(ts(2026, 6, 9, 9, 30), 300.0))
        store.log_session(work(ts(2026, 6, 8, 9, 0), 1800.0))
        store.log_event(LedgerEvent(ts=ts(2026, 6, 9, 9, 5), type="lock_requested", payload={}))

        deleted = store.clear_all()

        assert store.today_work_seconds(now=now) == 0.0
        assert store.today_rest_count(now=now) == 0
        events_left = store._connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    finally:
        store.close()

    assert deleted == 4  # 3 sessions ＋ 1 event
    assert events_left == 0


def test_clear_today_on_uninitialized_db_returns_zero(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    try:
        # 不先呼叫 init_schema，clear_today 內部應自動建立 schema（移植舊行為）
        assert store.clear_today() == 0
    finally:
        store.close()


# ---------------------------------------------------------------------------
# per-thread 連線（移植 tests/test_logging_store.py）
# ---------------------------------------------------------------------------


def test_store_can_initialize_and_write_from_different_thread(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    errors: list[BaseException] = []

    def worker_thread() -> None:
        try:
            store.init_schema()
            store.log_session(work(ts(2026, 6, 9, 12, 0), 300.0))
        except BaseException as exc:  # pragma: no cover - 供下方斷言
            errors.append(exc)
        finally:
            store.close()

    thread = threading.Thread(target=worker_thread)
    thread.start()
    thread.join(timeout=2.0)

    try:
        assert not errors
        # 主執行緒以自己的連線讀回 worker 寫入的資料
        total = store.today_work_seconds(now=datetime(2026, 6, 9, 13, 0))
        assert total == 300.0
    finally:
        store.close()


def test_close_only_closes_calling_thread_connection(tmp_path: Path) -> None:
    """close() 只關閉呼叫端執行緒自己的連線，不影響其他執行緒的連線。"""
    store = make_store(tmp_path)
    errors: list[BaseException] = []

    # 主執行緒先建立連線（初始化並查詢）
    store.init_schema()
    assert store.today_work_seconds(now=datetime(2026, 6, 9, 12, 0)) == 0.0

    def worker_thread() -> None:
        try:
            store.log_session(work(ts(2026, 6, 9, 10, 0), 1800.0, ended_by="rest"))
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)
        finally:
            store.close()  # 只關 worker 自己的連線

    thread = threading.Thread(target=worker_thread)
    thread.start()
    thread.join(timeout=2.0)

    assert not errors
    # 主執行緒連線仍可用，且看得到 worker 寫入的記錄
    try:
        total = store.today_work_seconds(now=datetime(2026, 6, 9, 12, 0))
        assert total == 1800.0
    except sqlite3.ProgrammingError as exc:  # pragma: no cover
        raise AssertionError(f"主執行緒連線在 worker close() 後失效: {exc}") from exc
    finally:
        store.close()


def test_close_is_idempotent_and_reusable(tmp_path: Path) -> None:
    """close() 後同執行緒再呼叫任何方法可重建連線（冪等可重用）。"""
    store = make_store(tmp_path)
    store.init_schema()
    store.close()

    store.init_schema()  # 不應丟例外
    store.close()
    store.close()  # 重複 close 也不應丟例外
