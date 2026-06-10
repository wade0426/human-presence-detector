# M3d：倒數警示視窗

> 對應需求：`docs/proposal.md` 需求三（FR-3.3 `countdown_*` 模式、§3.6 新增字串）
> 對應設計：`docs/detailed-design.md` §5.4
> 依賴模塊：無（[[m3c-force-lock-controller]] 依賴本模塊）
> 異動檔案：
> - 修改 `src/ui/strings.py`（新增字串）
> - 新增 `src/ui/force_lock_window.py`
> - 新增 `tests/test_force_lock_window.py`

---

## 任務清單

- [ ] **任務 1：於 `src/ui/strings.py` 新增字串**

  ```python
  # Force lock (M3)
  FORCE_LOCK_COUNTDOWN = "{seconds} 秒後將鎖定畫面，請準備休息。"
  FORCE_LOCK_CANCEL = "取消本次鎖定"
  ```

  完成後執行 [[m5-text-fixes]] 的掃描測試確認新字串未引入 `》`。

- [ ] **任務 2：建立 `ForceLockCountdownWindow`**

  新增 `src/ui/force_lock_window.py`：

  ```python
  from __future__ import annotations

  from PySide6.QtCore import Qt, QTimer, Signal
  from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

  from src.ui import strings


  class ForceLockCountdownWindow(QWidget):
      expired = Signal()
      cancelled = Signal()

      def __init__(
          self, seconds: int, cancellable: bool, parent: QWidget | None = None
      ) -> None:
          super().__init__(parent)
          self.setWindowFlags(
              Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTop
          )

          self._remaining = seconds
          self._label = QLabel(strings.FORCE_LOCK_COUNTDOWN.format(seconds=self._remaining))

          layout = QVBoxLayout(self)
          layout.addWidget(self._label)

          if cancellable:
              cancel_btn = QPushButton(strings.FORCE_LOCK_CANCEL)
              cancel_btn.clicked.connect(self._on_cancel)
              layout.addWidget(cancel_btn)

          self._timer = QTimer(self)
          self._timer.setInterval(1000)
          self._timer.timeout.connect(self._on_tick)

      def start(self) -> None:
          self._center_on_screen()
          self.show()
          self._timer.start()

      def _on_tick(self) -> None:
          self._remaining -= 1
          if self._remaining <= 0:
              self._timer.stop()
              self.expired.emit()
              self.hide()
              return
          self._label.setText(strings.FORCE_LOCK_COUNTDOWN.format(seconds=self._remaining))

      def _on_cancel(self) -> None:
          self._timer.stop()
          self.cancelled.emit()
          self.hide()

      def _center_on_screen(self) -> None:
          screen = QApplication.primaryScreen()
          if screen is None:
              return
          geo = screen.geometry()
          self.adjustSize()
          self.move(
              geo.center().x() - self.width() // 2,
              geo.center().y() - self.height() // 2,
          )
  ```

  行為要點（FR-3.3、§5.4）：
  - `FramelessWindowHint | WindowStaysOnTop`；置於主螢幕中央。
  - 標籤顯示 `FORCE_LOCK_COUNTDOWN.format(seconds=剩餘)`；每秒以 `QTimer` 遞減。
  - `cancellable=True` 時顯示「取消本次鎖定」按鈕（`FORCE_LOCK_CANCEL`）→ 點擊 emit `cancelled` 並 `hide()`。
  - 倒數到 0 → emit `expired` 並 `hide()`。

- [ ] **任務 3：撰寫測試（`tests/test_force_lock_window.py`，qt）**

  - `test_cancel_button_visible_only_when_cancellable`：`cancellable=True` 時可找到文字為 `FORCE_LOCK_CANCEL` 的 `QPushButton`；`cancellable=False` 時找不到。
  - `test_emits_cancelled_on_click`：`cancellable=True`，`win.start()` 後用 `qtbot.mouseClick` 點擊取消鈕，`qtbot.waitSignal(win.cancelled, timeout=1000)` 應收到訊號。
  - `test_emits_expired_after_countdown`：`seconds=1`，`win.start()` 後 `qtbot.waitSignal(win.expired, timeout=3000)` 應在約 1 秒後收到訊號。

---

## 完成定義（Definition of Done）

- [ ] `src/ui/strings.py` 新增 `FORCE_LOCK_COUNTDOWN`、`FORCE_LOCK_CANCEL`
- [ ] `ForceLockCountdownWindow` 介面（`expired`/`cancelled`/`__init__`/`start`）與設計文件一致
- [ ] 3 個測試新增並通過
- [ ] `rtk pytest tests/test_force_lock_window.py` 全數通過
- [ ] `rtk ruff check src/ui/force_lock_window.py` 無錯誤
