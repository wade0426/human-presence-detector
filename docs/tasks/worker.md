# 背景工作執行緒 `app/worker.py`

> **對應檔案**：`src/app/worker.py`、`tests/test_worker.py`  
> **前置條件**：[[types]]、[[video-source]]、[[detector]]、[[presence]]、[[timer-engine]]、[[logging-store]]  
> **相依**：`PySide6.QtCore`（QObject、Signal）、所有核心模塊

## 任務

- [ ] **W1** 建立 `src/app/worker.py`，定義 `DetectionWorker(QObject)` 的 signal 介面：
  ```python
  class DetectionWorker(QObject):
      frame_ready = Signal(object)        # Frame
      presence_changed = Signal(bool)
      timer_updated = Signal(object)      # TimerSnapshot
      reminder_show = Signal(object)      # ReminderContext
      reminder_repeat = Signal(object)    # ReminderContext
      connection_status = Signal(str)     # 'connected' | 'reconnecting'
  ```
  以及 `__init__` 接收 `source, detector, presence_evaluator, timer_engine, store, detection_interval_sec, reminder_context, clock=time.monotonic`

- [ ] **W2** 實作 `run()` 主迴圈（照 `docs/detailed-design.md` §5.7 虛擬碼）：
  - `store.init_schema()`
  - while loop：讀 frame → emit `frame_ready` → 偵測 → 判在場 → emit `presence_changed` → `timer_engine.update` → `_dispatch` → emit `timer_updated`
  - `source.read()` 回 `None` → emit `connection_status('reconnecting')`，不崩潰
  - sleep 至滿足 `detection_interval_sec`

- [ ] **W3** 實作 `_dispatch(ev: TimerEvent)`：
  - `REMINDER_TRIGGERED` → emit `reminder_show(reminder_context)`
  - `REMINDER_REPEATED` → emit `reminder_repeat(reminder_context)`
  - `WORK_STARTED` → 記錄 `_work_start_dt = datetime.now()`
  - `WORK_ENDED` → `store.log_session('work', _work_start_dt, datetime.now(), int(ev.duration_sec), ev.ended_by)`
  - `REST_ENDED` → `store.log_session('rest', now_dt - timedelta(seconds=ev.duration_sec), now_dt, int(ev.duration_sec), '')`

- [ ] **W4** 實作控制方法：
  - `stop()`：設 `_stop = True`
  - `pause()` / `resume()`：設 `_paused` flag（暫停時 loop sleep 0.1s）
  - `dismiss_reminder()`：呼叫 `timer_engine.on_reminder_dismissed(clock())` 並 `_dispatch` 每個事件
  - `set_roi(roi: BBox)`：呼叫 `presence_evaluator.set_roi(roi)`

- [ ] **W5** 建立 `tests/test_worker.py`（pytest-qt），使用假 source / detector 測試：
  - 假 source 回固定 Frame，假 detector 回空 Detection list → 跑 3 圈後收到 `frame_ready` signal
  - `source.read()` 回 `None` → 發出 `connection_status` signal 值為 `'reconnecting'`，不崩潰
  - 假 detector 回覆符合 ROI 的 Detection，且計時超過 N → 發出 `reminder_show` signal

- [ ] **W6** 執行 `rtk pytest tests/test_worker.py -v` 確認全部通過

- [ ] **W7** `git commit -m "feat: add detection worker thread with Qt signals"`
