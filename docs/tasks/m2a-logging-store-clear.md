# M2a：紀錄清除方法

> 對應需求：`docs/proposal.md` 需求二（FR-2.x，§2.3）
> 對應設計：`docs/detailed-design.md` §4.1
> 依賴模塊：無（M2b 依賴本模塊）
> 異動檔案：
> - 修改 `src/logging_store.py`
> - 擴充 `tests/test_logging_store.py`

---

## 任務清單

- [ ] **任務 1：新增 `SessionStore.clear_today()`**

  在 `src/logging_store.py` 的 `SessionStore` 類別新增方法：

  ```python
  def clear_today(self, now: datetime | None = None) -> int:
      today = (now or datetime.now()).strftime("%Y-%m-%d")
      connection = self._get_connection()
      cursor = connection.execute(
          "DELETE FROM sessions WHERE date(start_ts) = date(:today)",
          {"today": today},
      )
      connection.commit()
      return cursor.rowcount
  ```

  - 沿用 `_get_connection()`（per-thread 連線），由 UI 主執行緒呼叫。
  - `today` 字串格式與既有 `today_summary()` 一致（`"%Y-%m-%d"`）。
  - 回傳值取自 `cursor.rowcount`，`commit()` 後回傳。

- [ ] **任務 2：新增 `SessionStore.clear_all()`**

  ```python
  def clear_all(self) -> int:
      connection = self._get_connection()
      cursor = connection.execute("DELETE FROM sessions")
      connection.commit()
      return cursor.rowcount
  ```

- [ ] **任務 3：確保資料表不存在時不例外**

  兩個方法執行前先呼叫 `self.init_schema()`（與既有 `run()` 開頭一致的模式），確保即使資料庫檔案剛建立、尚未呼叫過 `init_schema()`，`DELETE` 也不會因資料表不存在而丟例外。

  ```python
  def clear_today(self, now: datetime | None = None) -> int:
      self.init_schema()
      ...

  def clear_all(self) -> int:
      self.init_schema()
      ...
  ```

- [ ] **任務 4：撰寫測試（`tests/test_logging_store.py`）**

  - `test_clear_today_removes_only_today`：用 `SessionStore(tmp_path 下的 sqlite 檔)`，先 `log_session(...)` 寫入「今日」與「昨日」各一列（昨日列可直接用 `connection.execute(INSERT ...)` 或呼叫 `log_session` 後手動更新 `start_ts`），呼叫 `clear_today(now=固定 datetime)` 後：
    - 回傳值等於今日列數
    - `today_summary()` 反映今日列已被刪除
    - 昨日列仍存在（可用 `SELECT COUNT(*) FROM sessions` 驗證總數）
  - `test_clear_all_empties_table`：寫入多筆（含今日與非今日），呼叫 `clear_all()` 後：
    - 回傳值等於寫入總筆數
    - `today_summary()` 全為 0（`work_seconds == 0`、`rest_count == 0`、`work_sessions == 0`）
  - `test_clear_today_on_empty_table`：對空表（僅 `init_schema()`，未寫入任何列）呼叫 `clear_today()`，回傳 `0`，不拋例外。

  > 注入點：以 `tmp_path` 建立臨時 sqlite 檔；`clear_today(now=固定 datetime)` 注入時鐘以穩定測試（避免測試在跨日邊界 flaky）。

---

## 完成定義（Definition of Done）

- [ ] `SessionStore.clear_today(now=None) -> int` 與 `SessionStore.clear_all() -> int` 已實作
- [ ] 3 個新測試新增並通過
- [ ] `rtk pytest tests/test_logging_store.py` 全數通過
- [ ] `rtk ruff check src/logging_store.py` 無錯誤
- [ ] `rtk mypy src/logging_store.py` 無錯誤
