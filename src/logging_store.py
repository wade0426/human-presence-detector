from __future__ import annotations

import sqlite3
from datetime import datetime


class SessionStore:
    def __init__(self, db_path: str) -> None:
        self._connection = sqlite3.connect(db_path)

    def init_schema(self) -> None:
        self._connection.execute(
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
        self._connection.commit()

    def log_session(
        self,
        type: str,
        start_ts: datetime,
        end_ts: datetime,
        duration_sec: int,
        ended_by: str,
    ) -> int:
        cursor = self._connection.execute(
            """
            INSERT INTO sessions (type, start_ts, end_ts, duration_sec, ended_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (type, start_ts.isoformat(), end_ts.isoformat(), duration_sec, ended_by),
        )
        self._connection.commit()
        row_id = cursor.lastrowid
        if row_id is None:
            raise RuntimeError("SQLite did not return a row id")
        return row_id

    def close(self) -> None:
        self._connection.close()
