# 模塊任務：提醒派發與顯示（FR-3）

> **對應需求**：FR-3（提醒彈窗時間文字）  
> **詳細設計**：`docs/detailed-design.md` §4.6  
> **涉及檔案**：`src/app/worker.py`、`src/reminder/popup.py`、`src/reminder/toast.py`、`src/ui/strings.py`  
> **測試檔**：`tests/test_reminder.py`、`tests/test_worker.py`（擴充）

---

## 任務清單

### 1. 修改 `src/app/worker.py`：`_dispatch` 注入實際工作秒數

- [ ] 匯入 `dataclasses`
- [ ] 在 `REMINDER_TRIGGERED` 與 `REMINDER_REPEATED` 事件分支中：
  ```python
  snap = self._timer_engine.snapshot(self._clock())
  ctx = dataclasses.replace(self._reminder_context, work_elapsed_sec=snap.work_elapsed_sec)
  self.reminder_show.emit(ctx)
  ```
- [ ] 確認 `self._reminder_context` 維持為基底物件（不修改基底，每次以 `replace` 產生新物件）

### 2. 修改 `src/reminder/popup.py`：使用動態時間文字

- [ ] 匯入 `format_duration_zh` 自 `src/duration_format.py`
- [ ] 將 `message_label.setText(...)` 改為：
  ```python
  self.message_label.setText(
      strings.REMIND_BODY.format(duration=format_duration_zh(ctx.work_elapsed_sec))
  )
  ```

### 3. 修改 `src/reminder/toast.py`：使用動態時間文字

- [ ] 同上，匯入 `format_duration_zh` 並改用 `REMIND_BODY.format(duration=...)`
- [ ] `floating.py` **不修改**（倒數視窗，沿用 `ctx.work_minutes`）

### 4. 修改 `src/ui/strings.py`：更新文字模板

- [ ] 將 `REMIND_BODY` 從 `"你已連續工作 {minutes} 分鐘。"` 改為 `"你已連續工作 {duration}。"`
- [ ] 新增：`CONN_STREAM_ERROR = "影像異常，畫面可能延遲或中斷。"`（供 FR-6 使用）
- [ ] 新增：`CONN_TEXT[ConnectionState.STREAM_ERROR] = "影像異常"`（待 FR-6 的 `ConnectionState` 任務完成後確認此行可執行）

### 5. 擴充單元測試

- [ ] **`tests/test_reminder.py`**
  - [ ] 以 `ReminderContext(work_elapsed_sec=30)` 呼叫 `popup.show`，訊息含「30 秒」
  - [ ] 以 `ReminderContext(work_elapsed_sec=90)` 呼叫 `popup.show`，訊息含「1 分 30 秒」
  - [ ] 不含「0 分鐘」的字串
- [ ] **`tests/test_worker.py`**
  - [ ] 門檻 0.5 分鐘觸發提醒，worker 發出的 `ctx.work_elapsed_sec ≈ 30`，訊息不含「0 分鐘」
  - [ ] 重複提醒時，`ctx.work_elapsed_sec` 較前次大
- [ ] 執行 `rtk pytest tests/test_reminder.py tests/test_worker.py` 確認通過

---

## 驗收標準

- 彈窗顯示實際連續工作時間，不再固定顯示門檻值或「0 分鐘」（AC-3.1）
- 達 90 秒以分+秒呈現（AC-3.2）
- 重複提醒時數值遞增（AC-3.3）
- `floating.py` 行為不受影響
