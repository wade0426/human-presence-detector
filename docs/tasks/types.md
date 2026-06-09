# 模塊任務：`src/types.py`（修改）

> **對應需求**：FR-1（overtime_sec）、FR-3（work_elapsed_sec in ReminderContext）  
> **詳細設計**：`docs/detailed-design.md` §3.1  
> **測試檔**：`tests/test_types.py`（擴充）

---

## 任務清單

### 1. 修改 `TimerSnapshot`

- [ ] 在 `TimerSnapshot` dataclass 新增欄位（含預設值，保持向後相容）：
  ```python
  overtime_sec: float = 0.0   # REMINDING 時 = max(0, work_elapsed - work_threshold)
  ```
- [ ] 確認 `frozen=True` 維持不變

### 2. 修改 `ReminderContext`

- [ ] 在 `ReminderContext` dataclass 新增欄位（含預設值）：
  ```python
  work_elapsed_sec: float = 0.0   # 提醒觸發當下實際連續工作秒數
  ```
- [ ] 確認既有欄位（`work_minutes`、`media_path`、`media_type`、`sound_path`）不動

### 3. 確認向後相容

- [ ] 現有所有 `TimerSnapshot(...)` 建構呼叫不需修改（新欄位有預設值）
- [ ] 現有所有 `ReminderContext(...)` 建構呼叫不需修改（新欄位有預設值）

### 4. 擴充單元測試（`tests/test_types.py`）

- [ ] 測試 `TimerSnapshot` 預設 `overtime_sec == 0.0`
- [ ] 測試 `ReminderContext` 預設 `work_elapsed_sec == 0.0`
- [ ] 測試既有欄位的建構方式仍正確（不帶新欄位也能建構）
- [ ] 執行 `rtk pytest tests/test_types.py` 確認全部通過

---

## 驗收標準

- 既有程式碼不需任何修改即可相容（新欄位皆有預設值）
- `overtime_sec` 與 `work_elapsed_sec` 型別均為 `float`
- 所有測試通過
