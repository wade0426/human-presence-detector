# 模塊任務：`src/ui/widgets/status_strip.py`（修改）

> **對應需求**：FR-1（提醒中時間語意）、FR-2（暫停凍結顯示）  
> **詳細設計**：`docs/detailed-design.md` §4.5  
> **測試檔**：`tests/test_ui.py`（擴充）

---

## 任務清單

### 1. 修改 `update_snapshot` 方法簽章

- [ ] 將方法簽章改為：
  ```python
  def update_snapshot(
      self,
      snap: TimerSnapshot,
      work_threshold_sec: float,
      reminding_mode: str = "overtime",   # "overtime" | "work_and_reminder"
  ) -> None:
  ```

### 2. 實作渲染規則

- [ ] **狀態標籤**：一律使用 `STATE_TEXT[snap.state]`（含 `SUSPENDED → "已暫停"`）
- [ ] **時間標籤**（依優先順序）：
  - [ ] `snap.state == RESTING`：沿用現有休息時間顯示（`rest_remaining` 或 `rest_elapsed`，用 `format_clock`）
  - [ ] `snap.reminder_active is True`（REMINDING，或自 REMINDING 暫停的 SUSPENDED）：
    - [ ] `reminding_mode == "overtime"` → `f"超時 {format_clock(snap.overtime_sec)}"`
    - [ ] `reminding_mode == "work_and_reminder"` → `f"工作 {format_clock(snap.work_elapsed_sec)} / 提醒 {format_clock(snap.overtime_sec)}"`
  - [ ] 其餘狀態 → `format_clock(snap.work_elapsed_sec)`
- [ ] **進度條**：非 RESTING 時 `maximum=work_threshold_sec`、`value=min(work_elapsed, maximum)`（提醒中即滿格）
- [ ] 未知 `reminding_mode` 時退回 `"overtime"` 行為

### 3. 確認匯入

- [ ] 匯入 `format_clock` 自 `src/duration_format.py`（取代原本的格式化邏輯）
- [ ] 確認 `STATE_TEXT` 已含 `SUSPENDED → "已暫停"`（如無則補上）

### 4. 擴充單元測試（`tests/test_ui.py`）

- [ ] WORKING 狀態：顯示 `format_clock(work_elapsed)`
- [ ] REMINDING + `"overtime"` 模式：顯示 `"超時 00:xx"`，數值 = `work_elapsed - threshold`
- [ ] REMINDING + `"work_and_reminder"` 模式：同時含工作時間與提醒時間兩段文字
- [ ] SUSPENDED（由 REMINDING 暫停）：標籤「已暫停」、數字等於凍結的超時值、不跳變
- [ ] 執行 `rtk pytest tests/test_ui.py -k status_strip` 確認通過

---

## 驗收標準

- 暫停後數字凍結，不跳變，不回溯（AC-2.1、AC-2.4）
- 提醒中預設顯示「超時 MM:SS」，進入「提醒中」時約從 `00:00` 起跳（AC-1.1）
- 「工作 + 提醒」模式兩段文字語意可明確區分（AC-1.2）
