"""持久化 v2（spec §7）：sessions/events 兩表、user_version=2、per-thread 連線。

- ``init_schema()``：``PRAGMA user_version != 2`` → 直接 drop 兩表重建（不遷移）。
- ``log_session()``/``log_event()``：寫入 :class:`SessionRecord` / :class:`LedgerEvent`
  （payload 以 JSON 序列化）。
- today 統計由 sessions 推導（以本地午夜為界）。
- per-thread 連線與 ``close()`` 語意移植自舊 ``src/logging_store.py:SessionStore``：
  ``close()`` 僅關閉呼叫端執行緒自己的連線，避免跨執行緒 ``ProgrammingError``。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.events import LedgerEvent, SessionRecord

SCHEMA_VERSION = 2

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('work', 'rest')),
    start_ts REAL NOT NULL,
    end_ts REAL NOT NULL,
    duration_sec REAL NOT NULL,
    ended_by TEXT NOT NULL
)
"""

_CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}'
)
"""


def _today_range(now: datetime | None) -> tuple[float, float]:
    """回傳今日（本地時區）的 [午夜, 隔日午夜) epoch 區間。"""
    moment = now if now is not None else datetime.now()
    day_start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return day_start.timestamp(), day_end.timestamp()


class RecordStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._connections: dict[int, sqlite3.Connection] = {}

    @property
    def _connection(self) -> sqlite3.Connection:
        return self._get_connection()

    def _get_connection(self) -> sqlite3.Connection:
        thread_id = threading.get_ident()
        connection = self._connections.get(thread_id)
        if connection is None:
            connection = sqlite3.connect(self._db_path)
            self._connections[thread_id] = connection
        return connection

    def init_schema(self) -> None:
        connection = self._get_connection()
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != SCHEMA_VERSION:
            connection.execute("DROP TABLE IF EXISTS sessions")
            connection.execute("DROP TABLE IF EXISTS events")
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.execute(_CREATE_SESSIONS)
        connection.execute(_CREATE_EVENTS)
        connection.commit()

    def log_session(self, rec: SessionRecord) -> None:
        connection = self._get_connection()
        connection.execute(
            """
            INSERT INTO sessions (kind, start_ts, end_ts, duration_sec, ended_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rec.kind, rec.start_ts, rec.end_ts, rec.duration_sec, rec.ended_by),
        )
        connection.commit()

    def log_event(self, ev: LedgerEvent) -> None:
        connection = self._get_connection()
        connection.execute(
            "INSERT INTO events (ts, type, payload) VALUES (?, ?, ?)",
            (ev.ts, ev.type, json.dumps(ev.payload, ensure_ascii=False)),
        )
        connection.commit()

    def today_work_seconds(self, now: datetime | None = None) -> float:
        day_start, day_end = _today_range(now)
        cursor = self._get_connection().execute(
            """
            SELECT COALESCE(SUM(duration_sec), 0)
            FROM sessions
            WHERE kind = 'work' AND start_ts >= ? AND start_ts < ?
            """,
            (day_start, day_end),
        )
        return float(cursor.fetchone()[0])

    def today_rest_count(self, now: datetime | None = None) -> int:
        day_start, day_end = _today_range(now)
        cursor = self._get_connection().execute(
            """
            SELECT COUNT(*)
            FROM sessions
            WHERE kind = 'rest' AND start_ts >= ? AND start_ts < ?
            """,
            (day_start, day_end),
        )
        return int(cursor.fetchone()[0])

    def clear_today(self, now: datetime | None = None) -> int:
        """刪除今日的 sessions 與 events，回傳兩表合計刪除筆數。"""
        self.init_schema()
        day_start, day_end = _today_range(now)
        connection = self._get_connection()
        sessions = connection.execute(
            "DELETE FROM sessions WHERE start_ts >= ? AND start_ts < ?",
            (day_start, day_end),
        )
        events = connection.execute(
            "DELETE FROM events WHERE ts >= ? AND ts < ?",
            (day_start, day_end),
        )
        connection.commit()
        return sessions.rowcount + events.rowcount

    def clear_all(self) -> int:
        """刪除全部 sessions 與 events，回傳兩表合計刪除筆數。"""
        self.init_schema()
        connection = self._get_connection()
        sessions = connection.execute("DELETE FROM sessions")
        events = connection.execute("DELETE FROM events")
        connection.commit()
        return sessions.rowcount + events.rowcount

    def close(self) -> None:
        """僅關閉『呼叫端執行緒』自己建立的連線；其他執行緒連線不動。

        - Worker 執行緒於 run() finally 呼叫 → 只關 worker 自己的連線
        - UI 主執行緒於 aboutToQuit 呼叫 → 只關主執行緒自己的連線
        - 兩者互不干涉，不會觸發跨執行緒 sqlite3.ProgrammingError
        """
        thread_id = threading.get_ident()
        connection = self._connections.pop(thread_id, None)
        if connection is not None:
            connection.close()
