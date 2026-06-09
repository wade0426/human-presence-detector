from __future__ import annotations

import sqlite3
import threading
from datetime import datetime


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

    def close(self) -> None:
        for connection in self._connections.values():
            connection.close()
        self._connections.clear()
