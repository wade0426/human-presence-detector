# M2 計時/狀態機

**涉及檔案**：`src/timer_engine.py`、`tests/test_timer_engine.py`

**相依**：M1（需先完成）

---

## 任務清單

### 建構子簽章更新

- [ ] 移除參數 `reset_mode`、`snooze_sec`
- [ ] 新增參數 `rest_count_mode: RestCountMode`
- [ ] 新增內部狀態變數：`_rest_accumulated`、`_rest_started_at`、`_state_before_pause`

### 移除舊方法

- [ ] 刪除 `on_reminder_dismissed()`

### 新增方法：`start_rest(now)`

- [ ] 從 `REMINDING` 狀態進入 `RESTING`，送出 `REST_STARTED`
- [ ] 初始化 `_rest_started_at = now`、`_rest_accumulated = 0`

### 新增方法：`confirm_return(now)`

- [ ] 從 `AWAITING_RETURN` 進入 `WORKING`，送出 `REST_ENDED` + `WORK_STARTED`
- [ ] 重置工作計時（`work_elapsed = 0`、`_last_t = now`）

### RESTING 狀態邏輯（`update()` 內）

- [ ] `PRESENCE` 模式：僅在 `not present` 時累計 `_rest_accumulated += dt`；中途回座暫停累計不重來
- [ ] `FIXED` 模式：`satisfied = (now - _rest_started_at) >= required_rest`（不論在不在）
- [ ] `satisfied and present` → 轉 `AWAITING_RETURN`，送出 `RETURN_PROMPT`
- [ ] `satisfied and not present` → 維持 `RESTING`（等待回座）

### AWAITING_RETURN 狀態邏輯（`update()` 內）

- [ ] 任何 `update()` 都不改變狀態（不計時、不自動確認）

### REMINDING 重複邏輯清理

- [ ] 移除 reset_mode 分支，統一為「若在場且距上次提醒 ≥ repeat_interval → 送 REMINDER_REPEATED」
- [ ] 提醒中若直接離座 → 轉 `RESTING`，送出 `REST_STARTED`

### 暫停凍結修正（需求 5 bug fix）

- [ ] `pause(now)`：記住 `_state_before_pause = self._state`；設 `_paused = True`
- [ ] `resume(now)`：`_last_t = now`（重設基準）；`_paused = False`；還原 `_state_before_pause`
- [ ] `update()`：若 `_paused` 直接 `return []`（防禦性 no-op）
- [ ] `snapshot()`：若 `_paused` 回報 `state = SUSPENDED`

### snapshot() 擴充

- [ ] 填入 `rest_remaining_sec`（FIXED 模式剩餘時間）
- [ ] 填入 `rest_elapsed_sec`（PRESENCE 模式已累計）

---

## 單元測試（`tests/test_timer_engine.py`）

- [ ] 測試 1：工作達門檻 → 事件含 `REMINDER_TRIGGERED`、`state == REMINDING`
- [ ] 測試 2：提醒中持續在場 → 每 `repeat_interval` 送 `REMINDER_REPEATED`（無 reset_mode 分支）
- [ ] 測試 3：提醒中呼叫 `start_rest` → `state == RESTING`、事件含 `REST_STARTED`
- [ ] 測試 4：提醒中直接離座（present=False）→ `state == RESTING`、事件含 `REST_STARTED`
- [ ] 測試 5：PRESENCE 模式離座累計達 required_rest 後回座 → `RETURN_PROMPT`；中途回座暫停累計（不重來）
- [ ] 測試 6：FIXED 模式按 start_rest 後經 required_rest → 滿足；回座 → `RETURN_PROMPT`
- [ ] 測試 7：`AWAITING_RETURN` 期間 `update()` 不改狀態；`confirm_return` → `REST_ENDED + WORK_STARTED`、`work_elapsed == 0`
- [ ] 測試 8（需求5）：working 累計 4s → `pause(5)` → `resume(60)` → `update(present, 60.1)` 後 `work_elapsed ≈ 4s`（不含暫停 55s）；暫停期間 `snapshot.state == SUSPENDED`
- [ ] 測試 9：AWAY 未達 reset_threshold 回座續計；達門檻 → `WORK_ENDED(ended_by="reset")`、`state == IDLE`
- [ ] 測試 10：RESTING 時 `snapshot.rest_remaining_sec` / `rest_elapsed_sec` 數值正確

---

## 驗收

- [ ] `rtk pytest tests/test_timer_engine.py -v` 全通過
