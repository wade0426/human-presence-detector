# 模塊任務：`src/ui/main_window.py`（修改）

> **對應需求**：FR-1（傳入顯示模式）、FR-4（串接 TodayWorkModel）  
> **詳細設計**：`docs/detailed-design.md` §4.11  
> **測試檔**：`tests/test_ui.py`（擴充）

---

## 任務清單

### 1. 初始化新成員

- [ ] 在 `__init__` 新增：
  ```python
  self._work_threshold_sec = config.timer.work_threshold_min * 60.0
  self._reminding_mode = config.reminder.reminding_display_mode
  self._today_model = TodayWorkModel()
  self._rest_count = 0
  self._last_snapshot = None
  ```
- [ ] 確認匯入 `TodayWorkModel` 自 `src/today_work_model.py`

### 2. 啟動時取一次 DB 基準

- [ ] 在 `__init__` 末呼叫 `self._refresh_base()`

### 3. 實作 `_refresh_base(self)`

- [ ] 以 `try/except` 包覆以下邏輯（失敗時沿用上次顯示，不影響 UI）：
  ```python
  summary = self._store.today_summary()
  self._today_model.set_base(summary.work_seconds)
  self._rest_count = summary.rest_count
  if self._last_snapshot:
      display = self._today_model.observe(self._last_snapshot).display_seconds
  else:
      display = summary.work_seconds
  self._summary.set_today(display, self._rest_count)
  ```

### 4. 修改 `on_timer_updated(self, snap: TimerSnapshot)`

- [ ] 更新 `self._last_snapshot = snap`
- [ ] 呼叫 `result = self._today_model.observe(snap)`
- [ ] 若 `result.base_refresh_needed`：
  - [ ] 呼叫 `self._refresh_base()`（工作剛結束已寫入 DB，重抓）
  - [ ] 重算 `result = self._today_model.observe(snap)`
- [ ] 呼叫 `self._summary.set_today(result.display_seconds, self._rest_count)`
- [ ] 呼叫 `self._status.update_snapshot(snap, self._work_threshold_sec, self._reminding_mode)`

### 5. 保留 30 秒 QTimer 保險刷新

- [ ] 確認既有 30 秒 QTimer 的 `timeout` 訊號仍連接至 `_refresh_base`（作為換日等情況的保險）

### 6. 擴充單元測試（`tests/test_ui.py`）

- [ ] 連續送 WORKING 快照，確認 `today_summary_view` 工作秒數遞增
- [ ] 送出「`work_elapsed` 由 > 0 轉 0」的快照序列，確認觸發一次 `today_summary()` 重抓
- [ ] 暫停快照下，顯示值不增加
- [ ] 使用假 store / 假 model 執行上述測試，不依賴真實 DB
- [ ] 執行 `rtk pytest tests/test_ui.py -k main_window` 確認通過

---

## 驗收標準

- 工作進行中，「今日工作」隨每次 `on_timer_updated` 更新（AC-4.1）
- 工作結束寫入 DB 後，顯示值連續不跳增（AC-4.3）
- 暫停期間顯示值不增加（AC-4.4）
- DB 查詢失敗不影響 UI 正常運作
