# 模塊任務：`src/logging_store.py`（修改）

> **對應需求**：FR-5（SQLite 跨執行緒安全）  
> **詳細設計**：`docs/detailed-design.md` §4.7  
> **測試檔**：既有 store 測試（擴充）

---

## 任務清單

### 1. 修改 `close()` 方法

- [ ] 找到現有的 `close()` 實作（目前會關閉字典內所有連線）
- [ ] 改為**僅關閉呼叫端執行緒自己的連線**：
  ```python
  def close(self) -> None:
      thread_id = threading.get_ident()
      connection = self._connections.pop(thread_id, None)
      if connection is not None:
          connection.close()
  ```
- [ ] 確認不再有「走訪並關閉所有連線」的行為

### 2. 確認其他方法維持現狀

- [ ] `_get_connection`：仍為 per-thread（依 `threading.get_ident()` 建立）
- [ ] `init_schema`、`log_session`、`today_summary`：不需修改

### 3. 確認關閉職責分工

- [ ] Worker 執行緒：在 `run()` 的 `finally` 呼叫 `self._store.close()`（關自己的連線）
- [ ] UI 主執行緒：在 `aboutToQuit` 呼叫 `store.close()`（由 `main.py` 負責，見 `main-entrypoint` 任務）
- [ ] 確認兩個執行緒各自關閉、互不干涉

### 4. 擴充單元測試（store 測試檔）

- [ ] **跨執行緒安全測試**：
  - [ ] 主執行緒建立連線並查詢 `today_summary()`
  - [ ] 另以 `threading.Thread` 建立第二個執行緒，在該執行緒中建立連線、寫入 session，然後在**該執行緒內**呼叫 `close()`
  - [ ] 確認主執行緒連線仍可用（不拋出 `ProgrammingError`）
  - [ ] 確認全程無 `sqlite3.ProgrammingError: SQLite objects created in a thread...`
- [ ] **冪等測試**：`close()` 後同執行緒再次呼叫 `_get_connection` 可建立新連線（不丟例外）
- [ ] 執行 `rtk pytest tests/` 確認相關測試通過且無跨執行緒例外

---

## 驗收標準

- `close()` 只關呼叫端執行緒自己的連線，不跨執行緒操作（AC-5.2）
- 完整一輪「啟動→工作→提醒→休息→返回→暫停→恢復→關閉」背景無 `ProgrammingError`（AC-5.1）
- 程式關閉後各執行緒連線各自被正確釋放，無資源洩漏（AC-5.3）
