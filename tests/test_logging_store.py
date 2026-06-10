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


# ---------------------------------------------------------------------------
# FR-5 跨執行緒安全測試
# ---------------------------------------------------------------------------


def test_close_only_closes_calling_thread_connection(tmp_path: object) -> None:
    """close() 只關閉呼叫端執行緒自己的連線，不影響其他執行緒的連線（FR-5）。

    - 主執行緒建立連線並查詢
    - 另一 worker 執行緒建立連線、寫入後在該執行緒內 close()
    - 確認主執行緒連線仍可用，全程無 sqlite3.ProgrammingError
    """
    import os

    db_path = os.path.join(str(tmp_path), "thread_test.db")
    store = SessionStore(db_path)
    errors: list[BaseException] = []

    # 主執行緒先建立連線（初始化並查詢）
    store.init_schema()
    summary_before = store.today_summary()
    assert summary_before.work_seconds == 0

    start = datetime(2026, 6, 9, 10, 0, 0)
    end = datetime(2026, 6, 9, 10, 30, 0)

    def worker() -> None:
        try:
            # Worker 執行緒建立自己的連線並寫入
            store.log_session("work", start, end, 1800, "rest")
        except BaseException as exc:
            errors.append(exc)
        finally:
            # Worker 執行緒只關閉自己的連線
            store.close()

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=2.0)

    # Worker 的 close() 不應影響主執行緒連線
    assert not errors

    # 主執行緒連線仍可用，且可看到 worker 寫入的記錄
    try:
        summary_after = store.today_summary(now=datetime(2026, 6, 9, 12, 0))
        assert summary_after.work_seconds == 1800
    except Exception as exc:  # pragma: no cover
        raise AssertionError(f"主執行緒連線在 worker close() 後失效: {exc}") from exc
    finally:
        store.close()


def test_close_is_idempotent_same_thread() -> None:
    """close() 後同執行緒再次呼叫 _get_connection 可建立新連線（冪等可重用）。"""
    store = SessionStore(":memory:")
    store.init_schema()
    store.close()

    # close() 後可以重新建立連線
    store.init_schema()  # 不應丟例外
    store.close()


# ---------------------------------------------------------------------------
# M2a 清除歷史紀錄方法測試
# ---------------------------------------------------------------------------


def test_clear_today_removes_only_today(tmp_path: object) -> None:
    """clear_today() 只刪除今日紀錄，不影響其他日期的資料。"""
    store = SessionStore(str(tmp_path / "records.sqlite"))
    today = datetime(2024, 3, 10, 12, 0, 0)
    yesterday = datetime(2024, 3, 9, 10, 0, 0)
    try:
        store.init_schema()
        # 寫入今日一列
        store.log_session("work", today, today, 100, "auto")
        # 寫入昨日一列（先 log 再 UPDATE start_ts）
        row_id = store.log_session("work", today, today, 200, "auto")
        connection = store._get_connection()
        connection.execute(
            "UPDATE sessions SET start_ts = ?, end_ts = ? WHERE id = ?",
            (yesterday.isoformat(), yesterday.isoformat(), row_id),
        )
        connection.commit()

        # 呼叫 clear_today
        deleted = store.clear_today(now=today)

        # 今日列被刪除（共 1 列）
        assert deleted == 1
        # 今日 work_seconds 已清空
        summary = store.today_summary(now=today)
        assert summary.work_seconds == 0
        # 昨日列仍存在
        total = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        assert total == 1
    finally:
        store.close()


def test_clear_all_empties_table(tmp_path: object) -> None:
    """clear_all() 刪除所有紀錄，today_summary() 全部歸零。"""
    store = SessionStore(str(tmp_path / "records.sqlite"))
    today = datetime(2024, 3, 10, 12, 0, 0)
    yesterday = datetime(2024, 3, 9, 10, 0, 0)
    try:
        store.init_schema()
        store.log_session("work", today, today, 100, "auto")
        store.log_session("rest", today, today, 60, "auto")
        store.log_session("work", yesterday, yesterday, 200, "auto")

        deleted = store.clear_all()

        assert deleted == 3
        summary = store.today_summary(now=today)
        assert summary.work_seconds == 0
        assert summary.rest_count == 0
        assert summary.work_sessions == 0
    finally:
        store.close()


def test_clear_today_on_empty_table(tmp_path: object) -> None:
    """clear_today() 在空資料庫（未呼叫 init_schema）時不丟例外，回傳 0。"""
    store = SessionStore(str(tmp_path / "records.sqlite"))
    try:
        # 不呼叫 init_schema，clear_today 內部應自動建立 schema
        deleted = store.clear_today()
        assert deleted == 0
    finally:
        store.close()


def test_close_no_cross_thread_programming_error(tmp_path: object) -> None:
    """完整模擬：主執行緒讀取統計，worker 執行緒寫入後 close，全程無 ProgrammingError。"""
    import sqlite3

    db_path = str(tmp_path) + "/test_thread.db"
    store = SessionStore(db_path)
    errors: list[BaseException] = []
    programming_errors: list[sqlite3.ProgrammingError] = []

    # 主執行緒初始化
    store.init_schema()

    start = datetime(2026, 6, 9, 9, 0, 0)
    end = datetime(2026, 6, 9, 9, 30, 0)

    def worker() -> None:
        try:
            store.log_session("work", start, end, 1800, "rest")
        except sqlite3.ProgrammingError as exc:
            programming_errors.append(exc)
        except BaseException as exc:
            errors.append(exc)
        finally:
            store.close()  # 只關閉 worker 執行緒自己的連線

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=2.0)

    # 主執行緒再次查詢（不應受 worker close() 影響）
    try:
        summary = store.today_summary(now=datetime(2026, 6, 9, 12, 0))
        assert summary.work_seconds == 1800
    except sqlite3.ProgrammingError as exc:  # pragma: no cover
        raise AssertionError(f"主執行緒連線被跨執行緒 close() 破壞: {exc}") from exc
    finally:
        store.close()

    assert not programming_errors, f"出現跨執行緒 ProgrammingError: {programming_errors}"
    assert not errors, f"出現其他例外: {errors}"
