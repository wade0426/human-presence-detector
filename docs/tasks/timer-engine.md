# 模塊任務：`src/timer_engine.py`（修改）

> **對應需求**：FR-1（overtime_sec）、FR-2（暫停凍結）、FR-4（WORK_ENDED 完整化）  
> **詳細設計**：`docs/detailed-design.md` §4.4  
> **測試檔**：`tests/test_timer_engine.py`（擴充）

---

## 任務清單

### 1. `snapshot(now)` 新增 `overtime_sec`

- [ ] 在 `TimerSnapshot` 建構時計算：
  ```python
  overtime_sec = max(0.0, self._work_elapsed - self._work_threshold_sec) \
                 if self._state == TimerState.REMINDING else 0.0
  ```
- [ ] 確認暫停（`SUSPENDED`）狀態下，`_work_elapsed` 已凍結，`overtime_sec` 同樣為凍結值

### 2. 補齊「進入休息」時的 `WORK_ENDED` 事件（FR-4）

- [ ] 找到 `REMINDING → RESTING` 的兩條路徑：
  - [ ] `start_rest()`（手動）
  - [ ] 自動離開觸發的 rest 路徑
- [ ] 在送出 `REST_STARTED` **之前**，先送：
  ```python
  self._event(TimerEventType.WORK_ENDED, now, duration_sec=self._work_elapsed, ended_by="rest")
  ```
- [ ] 隨即將 `self._work_elapsed = 0.0`（確保 RESTING 期間 `work_elapsed=0`，避免重複計算）
- [ ] 確認 `confirm_return()` **不再**送 `WORK_ENDED`（工作已於進入休息時結束）
- [ ] 確認 `WORK_ENDED` 的 `ended_by` 欄位新增 `"rest"` 可能值（檢查現有 `ended_by` 類型定義）

### 3. 明文化暫停凍結契約（FR-2）

- [ ] 確認 `pause(now)`：記錄 `_state_before_pause`，設 `_paused=True`；**不**更新 `_work_elapsed`、**不**更新 `_last_t`
- [ ] 確認暫停期間 `update()` 立即回傳 `[]`，計時不前進
- [ ] 確認 `resume(now)`：設 `_paused=False`、`_last_t=now`（使下一次 `dt ≈ 0`）、還原 `_state`
- [ ] 如上述行為已正確實作，補加程式碼註解說明契約（而非新增邏輯）

### 4. 擴充單元測試（`tests/test_timer_engine.py`）

- [ ] **overtime_sec 測試**
  - [ ] REMINDING 下，`overtime_sec` 自 0 起隨在場時間累加
  - [ ] 未達 REMINDING（WORKING 等狀態）時，`overtime_sec == 0`
- [ ] **WORK_ENDED 完整化測試**
  - [ ] `start_rest()` 路徑：確認送出 `WORK_ENDED(duration=work_elapsed, ended_by="rest")`，且其後 `snapshot.work_elapsed_sec == 0`
  - [ ] 自動離開觸發休息路徑：同上確認
  - [ ] 一輪「工作→提醒→休息→確認返回」中，`WORK_ENDED` 恰好送出一次（不重複）
- [ ] **暫停不回溯測試**
  - [ ] 暫停後多次 `update()` 期間 `work_elapsed` 不變
  - [ ] 恢復後第一筆 `update` 的 `dt ≈ 0`，`work_elapsed` 不回溯
- [ ] 執行 `rtk pytest tests/test_timer_engine.py` 確認全部通過

---

## 驗收標準

- `overtime_sec` 在 REMINDING 狀態隨在場時間遞增，其他狀態為 0
- `WORK_ENDED` 在「進入休息」時恰好送出一次，且其後 `work_elapsed == 0`
- 暫停後恢復，`work_elapsed` 嚴格不回溯
- 所有新增測試通過，既有測試不回歸
