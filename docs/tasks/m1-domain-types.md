# M1 Domain 型別

**涉及檔案**：`src/types.py`、`src/config.py`（RestCountMode 列舉）

**相依**：無（M2–M9 全部相依 M1，**請最先完成**）

---

## 任務清單

### TimerState 擴充（`src/types.py`）

- [ ] 將 `TimerState.PAUSED` 更名為 `AWAY`（值改為 `"away"`）
- [ ] 新增 `TimerState.RESTING = "resting"`
- [ ] 新增 `TimerState.AWAITING_RETURN = "awaiting_return"`
- [ ] 新增 `TimerState.SUSPENDED = "suspended"`

### TimerEventType 擴充（`src/types.py`）

- [ ] 新增 `TimerEventType.REST_STARTED`
- [ ] 新增 `TimerEventType.RETURN_PROMPT`

### RestCountMode 新增（`src/config.py` 或 `src/types.py`）

- [ ] 新增 `class RestCountMode(Enum): PRESENCE = "presence"; FIXED = "fixed"`

### ResetMode 移除（`src/types.py`）

- [ ] 刪除 `class ResetMode`（以全域搜尋確認所有引用點一併移除）

### ReminderContext 更新（`src/types.py`）

- [ ] 移除 `ReminderContext.reset_mode` 欄位
- [ ] 移除 `ReminderContext.snooze_minutes` 欄位

### TimerSnapshot 擴充（`src/types.py`）

- [ ] 新增欄位 `rest_remaining_sec: float = 0.0`（FIXED 模式休息倒數）
- [ ] 新增欄位 `rest_elapsed_sec: float = 0.0`（PRESENCE 模式已休息累計）

### strings.py 補齊狀態文字（`src/ui/strings.py`）

- [ ] `STATE_TEXT` 新增 `RESTING: "休息中"`
- [ ] `STATE_TEXT` 新增 `AWAITING_RETURN: "待機"`（沿用「待機」）
- [ ] `STATE_TEXT` 新增 `SUSPENDED: "已暫停"`
- [ ] `STATE_TEXT` 的 `AWAY` key 由原 `PAUSED` 更名（若 key 是字串或列舉值）
- [ ] 新增 `PRESENCE_YES = "有人"`
- [ ] 新增 `PRESENCE_NO = "無人"`

### 全域更名 PAUSED → AWAY

- [ ] 以全域搜尋找出所有引用 `TimerState.PAUSED` / `"paused"` 的地方，改為 `AWAY` / `"away"`
  - 重點檔案：`src/ui/strings.py`、`src/timer_engine.py`、`tests/`、`src/ui/widgets/`、`src/app/tray.py`

---

## 驗收

- [ ] `python -c "from src.types import TimerState, RestCountMode; print(list(TimerState))"` 輸出含新成員
- [ ] `python -c "from src.types import ReminderContext; import inspect; print(inspect.fields(ReminderContext))"` 無 reset_mode/snooze 欄位
- [ ] `rtk pytest tests/` 全通過（無因更名引起的 import 錯誤）
