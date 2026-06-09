# 共用資料契約 `types.py`

> **對應檔案**：`src/types.py`、`tests/test_types.py`  
> **前置條件**：[[environment]]  
> **相依**：無（純 Python，不 import 任何本地模塊）

## 任務

- [ ] **T1** 建立 `src/types.py`，完整照 `docs/detailed-design.md` §4 的定義，包含：
  - `BBox(frozen dataclass)`：`x, y, w, h: float`，`center` property
  - `Detection(frozen dataclass)`：`bbox: BBox, confidence: float`
  - `Frame(frozen dataclass)`：`image: np.ndarray, width, height: int, timestamp: float`
  - `TimerState(Enum)`：IDLE / WORKING / PAUSED / REMINDING
  - `ResetMode(Enum)`：DETECTION / DISMISS / SNOOZE
  - `TimerEventType(Enum)`：WORK_STARTED / WORK_ENDED / REST_ENDED / REMINDER_TRIGGERED / REMINDER_REPEATED
  - `TimerEvent(frozen dataclass)`：`type, at, duration_sec=0.0, ended_by=""`
  - `TimerSnapshot(frozen dataclass)`：`state, work_elapsed_sec, away_elapsed_sec, remaining_to_reminder_sec, reminder_active`
  - `ReminderContext(frozen dataclass)`：`work_minutes, media_path, media_type, sound_path`

- [ ] **T2** 建立 `tests/test_types.py`，測試以下情境：
  - `BBox(0.0, 0.0, 1.0, 1.0).center == (0.5, 0.5)`
  - `BBox(0.1, 0.2, 0.4, 0.6).center == (0.3, 0.5)`
  - `BBox` 為 frozen（嘗試修改 x 應引發 `FrozenInstanceError`）

- [ ] **T3** 執行 `rtk pytest tests/test_types.py -v` 確認全部通過

- [ ] **T4** `git commit -m "feat: add shared types contract"`
