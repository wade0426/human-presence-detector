# M6 `src/logging_store.py` — 今日彙總唯讀查詢

**目標**：在 `SessionStore` 新增 `today_summary()` 方法，供主視窗顯示今日工作時長與休息次數。

**涉及檔案**：
- 修改：`src/logging_store.py`
- 修改：`tests/test_logging_store.py`

**相依**：`sqlite3`、`datetime`（皆既有）；**不更動**既有寫入路徑與 schema。

---

## 任務清單

- [ ] **1. 在 `src/logging_store.py` 新增 `TodaySummary` dataclass**

  在既有 import 區塊下方加入：
  ```python
  from dataclasses import dataclass

  @dataclass(frozen=True)
  class TodaySummary:
      work_seconds: int
      rest_count: int
      work_sessions: int
  ```

- [ ] **2. 實作 `SessionStore.today_summary()`**

  在 `SessionStore` 類別中新增：
  ```python
  from datetime import datetime

  def today_summary(self, now: datetime | None = None) -> TodaySummary:
      today = (now or datetime.now()).strftime("%Y-%m-%d")
      conn = self._get_conn()
      cur = conn.execute(
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
      work_sec = 0
      work_cnt = 0
      rest_cnt = 0
      for row in cur:
          if row[0] == "work":
              work_sec = int(row[1])
              work_cnt = int(row[2])
          elif row[0] == "rest":
              rest_cnt = int(row[2])
      return TodaySummary(
          work_seconds=work_sec,
          rest_count=rest_cnt,
          work_sessions=work_cnt,
      )
  ```

  > `_get_conn()` 是既有的每執行緒連線機制。確認它存在（或依既有命名調整）；若名稱不同請搜尋 `SessionStore` 的私有方法。

- [ ] **3. 新增測試到 `tests/test_logging_store.py`**

  ```python
  from datetime import datetime
  from src.logging_store import SessionStore, TodaySummary

  def test_today_summary_empty(tmp_path):
      store = SessionStore(str(tmp_path / "test.db"))
      store.init_schema()
      summary = store.today_summary(now=datetime(2024, 1, 15, 12, 0))
      assert summary == TodaySummary(work_seconds=0, rest_count=0, work_sessions=0)

  def test_today_summary_counts_only_today(tmp_path):
      store = SessionStore(str(tmp_path / "test.db"))
      store.init_schema()
      today = datetime(2024, 1, 15, 10, 0)
      yesterday = datetime(2024, 1, 14, 10, 0)
      # 今日 work session：1800 秒
      store.log_session("work", datetime(2024, 1, 15, 9, 0), datetime(2024, 1, 15, 9, 30), 1800, "")
      # 今日 rest session：300 秒
      store.log_session("rest", datetime(2024, 1, 15, 9, 30), datetime(2024, 1, 15, 9, 35), 300, "")
      # 昨日 work session（不應計入）
      store.log_session("work", datetime(2024, 1, 14, 9, 0), datetime(2024, 1, 14, 9, 30), 1800, "")

      summary = store.today_summary(now=today)
      assert summary.work_seconds == 1800
      assert summary.rest_count == 1
      assert summary.work_sessions == 1
  ```

- [ ] **4. 確認既有 `test_logging_store.py` 測試仍通過**

  ```bash
  rtk pytest tests/test_logging_store.py -v
  ```

- [ ] **5. Commit**

  ```bash
  rtk git add src/logging_store.py tests/test_logging_store.py
  rtk git commit -m "feat(M6): 新增 today_summary() 今日彙總唯讀查詢"
  ```
