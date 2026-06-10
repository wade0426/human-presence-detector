# M3b：鎖定決策（純邏輯）

> 對應需求：`docs/proposal.md` 需求三（FR-3.2～FR-3.5、§3.4 觸發判定規格）
> 對應設計：`docs/detailed-design.md` §5.2
> 依賴模塊：[[m0-config]]（`ForceLockConfig`）、`src/types.py`（`TimerSnapshot`、`TimerState`，無需修改）
> 異動檔案：
> - 新增 `src/app/force_lock.py`
> - 新增 `tests/test_force_lock.py`

> **無 Qt、無副作用**——本模塊只依資料決策，不呼叫鎖定 API、不建立視窗。是 [[m3c-force-lock-controller]] 的決策核心。

---

## 任務清單

- [ ] **任務 1：建立 `ForceLockPolicy`**

  新增 `src/app/force_lock.py`：

  ```python
  from __future__ import annotations

  from src.config import ForceLockConfig
  from src.types import TimerSnapshot, TimerState


  class ForceLockPolicy:
      def __init__(self, config: ForceLockConfig) -> None:
          self._config = config
          self._fired = False
          self._threshold_sec = config.overtime_threshold_min * 60.0

      def observe(self, snap: TimerSnapshot) -> bool:
          if not self._config.enabled:
              return False

          if snap.state == TimerState.SUSPENDED:
              # 暫停期間凍結 _fired，避免暫停／恢復造成重複或漏觸發
              return False

          if self._config.trigger == "overtime":
              if snap.state != TimerState.REMINDING:
                  self._fired = False
                  return False
              if self._fired:
                  return False
              if snap.overtime_sec >= self._threshold_sec:
                  self._fired = True
                  return True
              return False

          # trigger == "on_rest"
          if snap.state != TimerState.RESTING:
              self._fired = False
              return False
          if self._fired:
              return False
          self._fired = True
          return True
  ```

- [ ] **任務 2：撰寫測試（`tests/test_force_lock.py`，純 pytest，無 Qt）**

  以手刻 `TimerSnapshot` 序列餵入 `policy.observe(snap)`，逐筆收集回傳值並比對期望序列。`TimerSnapshot` 必填欄位：`state`、`work_elapsed_sec`、`away_elapsed_sec`、`remaining_to_reminder_sec`、`reminder_active`（`overtime_sec`、`rest_*` 有預設值 `0.0`，依需要覆寫）。

  - `test_disabled_never_fires`：`ForceLockConfig(enabled=False)`，餵入任意（含會觸發的）序列 → 全部回傳 `False`。
  - `test_overtime_fires_once`：`ForceLockConfig(enabled=True, trigger="overtime", overtime_threshold_min=1.0)`，連續多筆 `state=REMINDING, overtime_sec=120`（超過 60 秒門檻）→ 只有第一筆 `True`，其餘 `False`。
  - `test_overtime_resets_next_cycle`：序列 `REMINDING(overtime>=threshold, 觸發=True) → RESTING(False) → WORKING(False) → REMINDING(overtime>=threshold 再次, 應為True)` → 第二次進入 `REMINDING` 且超門檻時應再次回 `True`。
  - `test_overtime_below_threshold_no_fire`：`state=REMINDING, overtime_sec < threshold` → `False`（且不影響後續判定）。
  - `test_on_rest_fires_on_entering_resting`：`ForceLockConfig(enabled=True, trigger="on_rest")`，序列 `WORKING(False) → RESTING(True) → RESTING(False, 同一週期第二筆)`。
  - `test_suspended_does_not_retrigger`：序列 `REMINDING(超門檻, True) → SUSPENDED(False) → REMINDING(超門檻, 應為 False，因 _fired 未被 SUSPENDED 重置)`。

  > 注入點：直接建構 `ForceLockConfig(...)`，無外部相依、無 `tmp_path`、無 `qtbot`。

---

## 完成定義（Definition of Done）

- [ ] `ForceLockPolicy.__init__`/`observe` 介面與 §5.2 決策表完全一致
- [ ] 6 個測試新增並通過
- [ ] `rtk pytest tests/test_force_lock.py` 全數通過
- [ ] `rtk ruff check src/app/force_lock.py` 無錯誤
- [ ] `rtk mypy src/app/force_lock.py` 無錯誤
