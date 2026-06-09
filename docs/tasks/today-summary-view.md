# 模塊任務：`src/ui/widgets/today_summary_view.py`（修改）

> **對應需求**：FR-4（今日工作統計即時更新）  
> **詳細設計**：`docs/detailed-design.md` §4.10  
> **測試檔**：`tests/test_ui.py`（擴充）

---

## 任務清單

### 1. 修改顯示介面

- [ ] 將現有方法（如 `set_summary(TodaySummary)`）改為（或新增）：
  ```python
  def set_today(self, work_seconds: int, rest_count: int) -> None:
  ```
- [ ] `work_seconds > 0` 或 `rest_count > 0` 時：使用 `format_duration_zh(work_seconds)` 顯示工作時間（如「1 分 30 秒」）
- [ ] `work_seconds == 0` 且 `rest_count == 0` 時：顯示 `TODAY_EMPTY`（空狀態文案）

### 2. 確認匯入

- [ ] 匯入 `format_duration_zh` 自 `src/duration_format.py`
- [ ] 確認 `TODAY_EMPTY` 字串定義在 `strings.py` 或 widget 內

### 3. 擴充單元測試（`tests/test_ui.py`）

- [ ] `set_today(90, 2)` → 顯示文字含「1 分 30 秒」及「2 次」（或類似格式）
- [ ] `set_today(0, 0)` → 顯示空狀態文案（`TODAY_EMPTY`）
- [ ] `set_today(30, 0)` → 顯示「30 秒」
- [ ] 執行 `rtk pytest tests/test_ui.py -k today_summary` 確認通過

---

## 驗收標準

- 每次 `on_timer_updated` 呼叫都更新顯示，「今日工作」隨時間可見變化（AC-4.1）
- 工作時間以動態單位呈現（秒 / 分鐘 / 分秒），不再固定顯示「X 分鐘」
