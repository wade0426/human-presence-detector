# 計時狀態機 `timer_engine.py`

> **對應檔案**：`src/timer_engine.py`、`tests/test_timer_engine.py`  
> **前置條件**：[[types]]  
> **相依**：`src.types.TimerState`、`TimerEvent`、`TimerSnapshot`、`ResetMode`（純 Python，不依賴 Qt）

## 任務

- [ ] **TE1** 建立 `src/timer_engine.py`，定義 `TimerEngine` 介面與內部狀態變數（照 `docs/detailed-design.md` §5.5）：
  ```python
  class TimerEngine:
      def __init__(self, work_threshold_sec, reset_threshold_sec,
                   required_rest_sec, reset_mode, repeat_interval_sec, snooze_sec): ...
      def update(self, present: bool, now: float) -> list[TimerEvent]: ...
      def on_reminder_dismissed(self, now: float) -> list[TimerEvent]: ...
      def snapshot(self, now: float) -> TimerSnapshot: ...
      @property
      def state(self) -> TimerState: ...
  ```
  內部狀態：`state, work_elapsed, last_t, away_since, rest_start_t, work_start_t, reminder_last_t, snooze_until`

- [ ] **TE2** 實作 `update` 中 IDLE → WORKING 轉移：
  - 在場時：若有 `rest_start_t`，發出 `REST_ENDED`；切換至 WORKING，發出 `WORK_STARTED`，重置 `work_elapsed = 0`

- [ ] **TE3** 實作 `update` 中 WORKING 狀態：
  - 在場：`work_elapsed += dt`；達到 `work_threshold_sec` → 切換 REMINDING，發出 `REMINDER_TRIGGERED`
  - 離開：切換 PAUSED，記錄 `away_since`

- [ ] **TE4** 實作 `update` 中 PAUSED 狀態：
  - 回來（在場）：切換 WORKING，清除 `away_since`（**不補計**離開時間）
  - 繼續離開且 `(now - away_since) >= reset_threshold_sec`：發出 `WORK_ENDED(ended_by='reset')`，設 `rest_start_t = away_since`，切換 IDLE

- [ ] **TE5** 實作 `update` 中 REMINDING 狀態（三種 reset_mode）：
  - 在場時：DISMISS 模式等使用者點掉；SNOOZE 模式在貪睡期間不重複提醒；DETECTION/貪睡到期 → 每 `repeat_interval_sec` 發出 `REMINDER_REPEATED`；`work_elapsed += dt`
  - 離開時：記錄 `away_since`；`(now - away_since) >= required_rest_sec` → 發出 `WORK_ENDED(ended_by='rest_done')`，設 `rest_start_t`，切換 IDLE

- [ ] **TE6** 實作 `on_reminder_dismissed`（三種 reset_mode）：
  - DISMISS：發出 `WORK_ENDED(ended_by='dismiss')` + `WORK_STARTED`，切換 WORKING，`work_elapsed = 0`
  - SNOOZE：設 `snooze_until = now + snooze_sec`
  - DETECTION：更新 `reminder_last_t = now`（只是關掉這次提醒視窗）

- [ ] **TE7** 實作 `snapshot(now) -> TimerSnapshot`：
  - `remaining_to_reminder_sec = max(0, N - work_elapsed)` 僅在 WORKING 時有意義，其餘為 0
  - `away_elapsed_sec = (now - away_since) if away_since else 0`
  - `reminder_active = (state == REMINDING)`

- [ ] **TE8** 建立 `tests/test_timer_engine.py`，使用注入假時鐘（直接傳入 `now` 參數），測試以下情境：
  - 連續在場累計達 N → 收到 `REMINDER_TRIGGERED`
  - 短暫離開（< M）再回來 → 狀態回 WORKING，`work_elapsed` **不含**離開時間
  - 離開達 M → `WORK_ENDED(ended_by='reset')`，計時歸零；再回來 → `REST_ENDED` + `WORK_STARTED`
  - 模式1（DETECTION）：提醒後持續在場 → 每 `repeat_interval_sec` 收到一次 `REMINDER_REPEATED`；離開達 R → `WORK_ENDED(ended_by='rest_done')`
  - 模式2（DISMISS）：呼叫 `on_reminder_dismissed` → `WORK_ENDED(ended_by='dismiss')` + `WORK_STARTED`，立即新一輪
  - 模式3（SNOOZE）：`on_reminder_dismissed` 後貪睡期間不再提醒；貪睡到期仍在場 → 再次 `REMINDER_REPEATED`；離開達 R → 真正重置
  - `snapshot`：各狀態下 `remaining_to_reminder_sec`、`reminder_active` 正確

- [ ] **TE9** 執行 `rtk pytest tests/test_timer_engine.py -v` 確認全部通過

- [ ] **TE10** `git commit -m "feat: add timer engine state machine"`
