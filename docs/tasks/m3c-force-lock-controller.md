# M3c：鎖定控制器

> 對應需求：`docs/proposal.md` 需求三（FR-3.2～FR-3.5）
> 對應設計：`docs/detailed-design.md` §5.3
> 依賴模塊：[[m0-config]]（`ForceLockConfig`）、[[m3a-screen-lock]]（`screen_lock.lock_screen`）、[[m3b-force-lock-policy]]（`ForceLockPolicy`）、[[m3d-force-lock-window]]（`ForceLockCountdownWindow`）
> 異動檔案：
> - 新增 `src/app/force_lock_controller.py`
> - 新增 `tests/test_force_lock_controller.py`

> 串接 `worker.timer_updated`（快照）→ `ForceLockPolicy` 決策 → 依 `warning_mode` 執行「立即鎖定」或「倒數警示後鎖定」。是 [[int-integration]] 接線的對象。

---

## 任務清單

- [ ] **任務 1：建立 `ForceLockController`**

  新增 `src/app/force_lock_controller.py`：

  ```python
  from __future__ import annotations

  from typing import Callable

  from PySide6.QtCore import QObject

  from src.app import screen_lock
  from src.app.force_lock import ForceLockPolicy
  from src.config import ForceLockConfig
  from src.types import TimerSnapshot
  from src.ui.force_lock_window import ForceLockCountdownWindow


  class ForceLockController(QObject):
      def __init__(
          self,
          config: ForceLockConfig,
          *,
          lock_fn: Callable[[], bool] = screen_lock.lock_screen,
          window_factory: Callable[[int, bool], ForceLockCountdownWindow] | None = None,
          parent: QObject | None = None,
      ) -> None:
          super().__init__(parent)
          self._config = config
          self._policy = ForceLockPolicy(config)
          self._lock_fn = lock_fn
          self._window_factory = window_factory or ForceLockCountdownWindow
          self._countdown_window: ForceLockCountdownWindow | None = None

      def on_timer_updated(self, snap: TimerSnapshot) -> None:
          if self._policy.observe(snap):
              self._begin_lock_flow()

      def _begin_lock_flow(self) -> None:
          mode = self._config.warning_mode
          if mode == "immediate":
              self._lock_fn()
              return

          cancellable = mode == "countdown_cancel"
          win = self._window_factory(self._config.countdown_sec, cancellable)
          win.expired.connect(self._on_countdown_expired)
          win.cancelled.connect(self._on_countdown_cancelled)
          self._countdown_window = win
          win.start()

      def _on_countdown_expired(self) -> None:
          self._countdown_window = None
          self._lock_fn()

      def _on_countdown_cancelled(self) -> None:
          self._countdown_window = None
  ```

  行為要點（§5.3、`ForceLockConfig.warning_mode` 三值見 [[m0-config]]）：
  - `warning_mode == "immediate"`：直接呼叫 `lock_fn()`，不建立任何視窗。
  - `warning_mode == "countdown_cancel"`：建立 `ForceLockCountdownWindow(countdown_sec, cancellable=True)`；`expired` → 鎖定；`cancelled` → 僅清除參考，不鎖定。
  - `warning_mode == "countdown_only"`：同上但 `cancellable=False`（視窗仍會顯示，但無取消鈕；`ForceLockCountdownWindow` 本身已處理「無取消鈕」UI，本模塊只需傳入 `cancellable=False`）。
  - 持有 `self._countdown_window` 參考避免視窗被 GC；流程結束後清成 `None`。

  > 執行緒注意：`worker.timer_updated` 由偵測執行緒 `emit`，但 `ForceLockController` 屬主執行緒物件 → Qt 以 queued connection 在主執行緒執行 `on_timer_updated`，鎖定／視窗皆在主執行緒，安全。本模塊不需額外處理執行緒切換。

- [ ] **任務 2：撰寫測試（`tests/test_force_lock_controller.py`，qt）**

  ```python
  from __future__ import annotations

  import pytest
  from PySide6.QtCore import QObject, Signal

  from src.app.force_lock_controller import ForceLockController
  from src.config import ForceLockConfig
  from src.types import TimerSnapshot, TimerState


  class FakeCountdownWindow(QObject):
      expired = Signal()
      cancelled = Signal()

      def __init__(self, seconds: int, cancellable: bool) -> None:
          super().__init__()
          self.seconds = seconds
          self.cancellable = cancellable
          self.started = False

      def start(self) -> None:
          self.started = True


  def _resting_snapshot() -> TimerSnapshot:
      return TimerSnapshot(
          state=TimerState.RESTING,
          work_elapsed_sec=0.0,
          away_elapsed_sec=0.0,
          remaining_to_reminder_sec=0.0,
          reminder_active=False,
      )


  def _working_snapshot() -> TimerSnapshot:
      return TimerSnapshot(
          state=TimerState.WORKING,
          work_elapsed_sec=0.0,
          away_elapsed_sec=0.0,
          remaining_to_reminder_sec=600.0,
          reminder_active=False,
      )


  def test_immediate_locks_on_trigger(qtbot: pytest.QtBot) -> None:
      calls: list[None] = []
      config = ForceLockConfig(enabled=True, trigger="on_rest", warning_mode="immediate")
      controller = ForceLockController(config, lock_fn=lambda: calls.append(None) or True)

      controller.on_timer_updated(_resting_snapshot())

      assert len(calls) == 1


  def test_no_lock_when_policy_not_fired(qtbot: pytest.QtBot) -> None:
      calls: list[None] = []
      config = ForceLockConfig(enabled=True, trigger="on_rest", warning_mode="immediate")
      controller = ForceLockController(config, lock_fn=lambda: calls.append(None) or True)

      controller.on_timer_updated(_working_snapshot())

      assert calls == []


  def test_countdown_cancel_does_not_lock(qtbot: pytest.QtBot) -> None:
      calls: list[None] = []
      config = ForceLockConfig(
          enabled=True, trigger="on_rest", warning_mode="countdown_cancel", countdown_sec=5
      )
      controller = ForceLockController(
          config,
          lock_fn=lambda: calls.append(None) or True,
          window_factory=FakeCountdownWindow,
      )

      controller.on_timer_updated(_resting_snapshot())
      window = controller._countdown_window
      assert isinstance(window, FakeCountdownWindow)
      assert window.cancellable is True
      assert window.started is True

      window.cancelled.emit()

      assert calls == []
      assert controller._countdown_window is None


  def test_countdown_expire_locks(qtbot: pytest.QtBot) -> None:
      calls: list[None] = []
      config = ForceLockConfig(
          enabled=True, trigger="on_rest", warning_mode="countdown_only", countdown_sec=5
      )
      controller = ForceLockController(
          config,
          lock_fn=lambda: calls.append(None) or True,
          window_factory=FakeCountdownWindow,
      )

      controller.on_timer_updated(_resting_snapshot())
      window = controller._countdown_window
      assert isinstance(window, FakeCountdownWindow)
      assert window.cancellable is False

      window.expired.emit()

      assert len(calls) == 1
      assert controller._countdown_window is None
  ```

  - `test_immediate_locks_on_trigger`：`warning_mode="immediate"` + `trigger="on_rest"` 觸發快照 → `lock_fn` 被呼叫一次。
  - `test_no_lock_when_policy_not_fired`：非觸發快照（`WORKING`）→ `lock_fn` 不被呼叫。
  - `test_countdown_cancel_does_not_lock`：注入假視窗，`cancellable=True`、`start()` 被呼叫；發出 `cancelled` → `lock_fn` 不被呼叫，`_countdown_window` 清空。
  - `test_countdown_expire_locks`：`warning_mode="countdown_only"` → 假視窗 `cancellable=False`；發出 `expired` → `lock_fn` 被呼叫一次，`_countdown_window` 清空。

  > 預設 `window_factory=None` 時會使用真實 [[m3d-force-lock-window]] 的 `ForceLockCountdownWindow`；測試一律以 `FakeCountdownWindow` 注入，避免彈出真實視窗。

---

## 完成定義（Definition of Done）

- [ ] `ForceLockController.__init__`/`on_timer_updated` 介面與 §5.3 一致，`lock_fn`/`window_factory` 可注入
- [ ] `immediate`/`countdown_cancel`/`countdown_only` 三種 `warning_mode` 行為符合任務 1 描述
- [ ] 4 個測試新增並通過
- [ ] `rtk pytest tests/test_force_lock_controller.py` 全數通過
- [ ] `rtk ruff check src/app/force_lock_controller.py` 無錯誤
- [ ] `rtk mypy src/app/force_lock_controller.py` 無錯誤
