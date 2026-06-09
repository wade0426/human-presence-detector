# M4 協調器

**涉及檔案**：`src/app/worker.py`、`tests/test_worker.py`

**相依**：M1、M2、M3（需先完成）

---

## 任務清單

### 訊號更新

- [ ] 新增 `return_prompt = Signal(object)`（載荷：`ReminderContext` 或 ctx）
- [ ] 移除 `frame_ready` 訊號（預覽改由 M9 QTimer 直接拉 grabber.latest()）
- [ ] 移除 `reminder_repeat` 訊號（與 `reminder_show` 合併，統一重複提醒）

### 建構子簽章更新

- [ ] 參數 `source` 改為 `frames: FrameProvider`
- [ ] 移除 `reset_mode`、`snooze_sec` 等相關參數

### run() 迴圈更新

- [ ] 將 `source.read()` 改為 `self._frames.latest()`
- [ ] `latest()` 回 `None` 時依 `self._frames.is_opened` 發送連線狀態訊號
- [ ] 暫停期間（`_paused == True`）idle 等待，不取影格、不偵測

### 新增方法：`start_rest()`

- [ ] 呼叫 `self._engine.start_rest(now)` 並 `_dispatch` 事件
- [ ] 不再有提醒相關訊號發出

### 新增方法：`confirm_return()`

- [ ] 呼叫 `self._engine.confirm_return(now)` 並 `_dispatch` 事件
- [ ] `_dispatch` 中若遇 `WORK_STARTED` → 可觸發 `timer_updated` 快照

### 修正 `pause()` / `resume()`

- [ ] `pause()`：呼叫 `self._engine.pause(now)`；設 `_paused = True`；立即 emit 一次 `timer_updated(SUSPENDED 快照)`（不等下一輪迴圈）
- [ ] `resume()`：呼叫 `self._engine.resume(now)`；清 `_paused = False`

### `_dispatch()` 更新

- [ ] `REMINDER_TRIGGERED` / `REMINDER_REPEATED` → emit `reminder_show(ctx)`
- [ ] `RETURN_PROMPT` → emit `return_prompt(ctx)`
- [ ] `WORK_ENDED` / `REST_ENDED` → `store.log_session(...)`
- [ ] 移除舊 `dismiss` / `snooze` 相關分支

### `stop()` 更新

- [ ] 不再呼叫 `source.release()`（改由 `grabber.stop()` 於 M9 統一釋放）

---

## 單元測試（`tests/test_worker.py`）

以 `FakeFrames`（實作 `FrameProvider`）、`FakeDetector`、`FakeStore`、`FakeClock` 注入。

- [ ] 測試 1：達門檻 → 發 `reminder_show`
- [ ] 測試 2：`start_rest()` → 後續 `timer_updated` 快照 `state == RESTING`；不再發提醒
- [ ] 測試 3：休息滿足後 `latest()` 返回帶人的影格 → 發 `return_prompt`
- [ ] 測試 4：`confirm_return()` → `store.log_session` 被呼叫一次（新一輪起算）
- [ ] 測試 5：`pause()` → 立即收到 `state == SUSPENDED` 的 `timer_updated`；暫停期間追加 update 不改變狀態
- [ ] 測試 6：連線狀態（`latest()` 回 None、`is_opened` 為 False/True）→ 對應 `connection_status` 訊號（斷言行為不變）
- [ ] 測試 7：`stop()` → `FakeFrames.release_calls == 0`（釋放由 grabber 負責，worker 不多做）

---

## 驗收

- [ ] `rtk pytest tests/test_worker.py -v` 全通過
