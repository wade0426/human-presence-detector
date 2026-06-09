from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TodaySummary:
    work_seconds: int
    rest_count: int
    work_sessions: int


class SessionStore:
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                start_ts TEXT NOT NULL,
                end_ts TEXT,
                duration_sec INTEGER,
                ended_by TEXT
            )
            """
        )
        connection.commit()

    def log_session(
        self,
        type: str,
        start_ts: datetime,
        end_ts: datetime,
        duration_sec: int,
        ended_by: str,
    ) -> int:
        connection = self._get_connection()
        cursor = connection.execute(
            """
            INSERT INTO sessions (type, start_ts, end_ts, duration_sec, ended_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (type, start_ts.isoformat(), end_ts.isoformat(), duration_sec, ended_by),
        )
        connection.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("SQLite did not return a row id")
        return row_id

    def today_summary(self, now: datetime | None = None) -> TodaySummary:
        today = (now or datetime.now()).strftime("%Y-%m-%d")
        connection = self._get_connection()
        cursor = connection.execute(
            """
            SELECT type,
                   COALESCE(SUM(duration_sec), 0) AS total_sec,
                   COUNT(*) AS cnt
            FROM sessions
            WHERE date(start_ts) = date(:today)
            GROUP BY type
            """,
            {"today": today},
        )

        work_seconds = 0
        work_sessions = 0
        rest_count = 0
        for row in cursor:
            if row[0] == "work":
                work_seconds = int(row[1])
                work_sessions = int(row[2])
            elif row[0] == "rest":
                rest_count = int(row[2])

        return TodaySummary(
            work_seconds=work_seconds,
            rest_count=rest_count,
            work_sessions=work_sessions,
        )

    def close(self) -> None:
        """僅關閉『呼叫端執行緒』自己建立的連線；其他執行緒連線不動。

        維持 per-thread 連線架構的安全性（FR-5）：
        - Worker 執行緒於 run() finally 呼叫 → 只關 worker 自己的連線
        - UI 主執行緒於 aboutToQuit 呼叫 → 只關主執行緒自己的連線
        - 兩者互不干涉，不會觸發跨執行緒 sqlite3.ProgrammingError
        """
        thread_id = threading.get_ident()
        connection = self._connections.pop(thread_id, None)
        if connection is not None:
            connection.close()
