# 記錄寫入 `logging_store.py`

> **對應檔案**：`src/logging_store.py`、`tests/test_logging_store.py`  
> **前置條件**：[[environment]]  
> **相依**：`sqlite3`（標準庫）

## 任務

- [ ] **LS1** 建立 `src/logging_store.py`，實作 `SessionStore`：
  ```python
  class SessionStore:
      def __init__(self, db_path: str): ...
      def init_schema(self) -> None: ...
      def log_session(self, type: str, start_ts: datetime, end_ts: datetime,
                      duration_sec: int, ended_by: str) -> int: ...  # 回傳 row id
      def close(self) -> None: ...
  ```

- [ ] **LS2** 實作 `init_schema`：
  - 建立 `sessions` 資料表（照 `docs/proposal.md` §9.2 的 SQL）
  - 使用 `CREATE TABLE IF NOT EXISTS`，可重複呼叫不報錯

- [ ] **LS3** 實作 `log_session`：
  - 將 `start_ts`、`end_ts` 轉為 ISO8601 字串（`datetime.isoformat()`）
  - 插入記錄並回傳 `lastrowid`

- [ ] **LS4** 建立 `tests/test_logging_store.py`，使用 `db_path=':memory:'` 測試：
  - `init_schema()` 可重複呼叫兩次不報錯
  - `log_session('work', start, end, 1800, 'reset')` 後查 `SELECT * FROM sessions` 能取得相同欄位
  - `log_session('rest', ...)` 類型欄位正確為 `'rest'`
  - 回傳的 row id 為正整數

- [ ] **LS5** 執行 `rtk pytest tests/test_logging_store.py -v` 確認全部通過

- [ ] **LS6** `git commit -m "feat: add SQLite session store"`
