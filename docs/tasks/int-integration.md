# INT：整合與接線

> 對應需求：需求一、二、三的最終接線（FR-1.x／FR-2.4／FR-2.5／FR-3.1／FR-3.7）
> 對應設計：`docs/detailed-design.md` §8
> 依賴模塊：[[m1b-return-prompt-sound]]、[[m2b-clear-data-service]]、[[m2c-clear-data-dialog]]、[[m3c-force-lock-controller]]、[[m4-tooltips]]
> 異動檔案：
> - 修改 `src/ui/main_window.py`
> - 修改 `src/main.py`
> - 擴充 `tests/test_ui.py`
> - 擴充 `tests/test_main.py`

> 本模塊是最後一塊拼圖：把前面 12 個模塊的成品接成完整應用程式。所有子任務都應在對應模塊已完成後才進行。

---

## 任務清單

- [ ] **任務 1：`MainWindow` 新增「清除資料」按鈕與 `clear_data_requested` 訊號**

  修改 `src/ui/main_window.py`：

  1. import 調整：
     ```python
     from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QPushButton, QVBoxLayout, QWidget
     ...
     from src.ui.strings import CLEAR_DATA_BUTTON, CONN_ERROR_PREFIX, CONN_TEXT
     ```

  2. 在類別屬性新增訊號：
     ```python
     class MainWindow(QMainWindow):
         roi_changed = Signal(object)
         request_pause = Signal(bool)
         request_settings = Signal()
         clear_data_requested = Signal()
     ```

  3. 在 `_build_ui()` 中建立按鈕並放入 `middle_bar`（與 `TodaySummaryView` 同列）：
     ```python
         self._summary = TodaySummaryView()
         self._actions = ActionBar()
         self._clear_data_btn = QPushButton(CLEAR_DATA_BUTTON)
         self._clear_data_btn.clicked.connect(self.clear_data_requested.emit)

         ...

         middle_bar = QHBoxLayout()
         middle_bar.addWidget(self._summary, stretch=1)
         middle_bar.addWidget(self._clear_data_btn)
     ```

  > 既有 `_refresh_base()` 直接作為「清除完成後刷新」的入口，不需新增方法（§8.1）。

- [ ] **任務 2：`main.py` 接線——需求一（回來提示音效）**

  修改 `src/main.py`，將：
  ```python
      return_prompt_dialog = ReturnPromptDialog()
  ```
  改為：
  ```python
      return_prompt_dialog = ReturnPromptDialog(return_sound=cfg.reminder.return_sound)  # Req 1
  ```

  > 依賴 [[m1b-return-prompt-sound]] 的建構子簽章（`return_sound`/`player`/`parent` 皆為關鍵字參數，`player=None` 時內部自行建立）。

- [ ] **任務 3：`main.py` 接線——需求二（清除資料，兩入口共用）**

  1. 新增 import：
     ```python
     from src.app.clear_data import ClearDataService
     from src.ui.clear_data_dialog import run_clear_data_flow
     ```

  2. 在 `settings = SettingsWindow(cfg, "config.yaml", window)` 之後加入：
     ```python
         # Req 2: 清除資料（單一處理器，兩入口共用）
         clear_service = ClearDataService(store, "config.yaml")

         def _run_clear_data() -> None:
             run_clear_data_flow(
                 window, clear_service, on_done=lambda _result: window._refresh_base()
             )

         window.clear_data_requested.connect(_run_clear_data)
         settings.clear_data_requested.connect(_run_clear_data)
     ```

  > 兩個入口（主視窗 [[int-integration]] 任務 1 的按鈕、設定頁 [[m4-tooltips]] 任務 5 的按鈕）共用同一個 `_run_clear_data`，確保行為一致。`run_clear_data_flow` 簽章見 [[m2c-clear-data-dialog]]。

- [ ] **任務 4：`main.py` 接線——需求三（強制鎖定，僅在啟用時建立）**

  1. 新增 import：
     ```python
     from src.app.force_lock_controller import ForceLockController
     ```

  2. 在 `_build_worker()` 之後、`main()` 之前新增可測試小工廠：
     ```python
     def _maybe_build_force_lock(cfg: AppConfig) -> ForceLockController | None:
         if not cfg.force_lock.enabled:
             return None
         return ForceLockController(cfg.force_lock)
     ```

  3. 在 `main()` 中（接續任務 3 的程式碼之後）加入：
     ```python
         # Req 3: 強制鎖定（僅在 enabled 時建立並接線，停用時零額外負擔）
         force_lock_controller = _maybe_build_force_lock(cfg)
         if force_lock_controller is not None:
             worker.timer_updated.connect(force_lock_controller.on_timer_updated)
     ```

  > `force_lock.enabled is False`（預設值）時，`_maybe_build_force_lock` 回傳 `None`，**完全不建立** `ForceLockController` 也不接線（FR-3.1／FR-3.7）。`force_lock_controller` 變數持有參考至 `main()` 結束（App 生命週期），避免被 GC。

- [ ] **任務 5：撰寫測試**

  `tests/test_ui.py`（擴充，qt）：
  ```python
  def test_main_window_emits_clear_requested(qtbot: pytest.QtBot, tmp_path: object) -> None:
      from src.ui.main_window import MainWindow

      window = MainWindow(
          AppConfig(),
          FakeSummaryStore(),
          config_path=str(tmp_path / "main-window.yaml"),
      )
      qtbot.addWidget(window)

      with qtbot.waitSignal(window.clear_data_requested, timeout=1000):
          qtbot.mouseClick(window._clear_data_btn, Qt.MouseButton.LeftButton)
  ```

  `tests/test_main.py`（擴充）：
  ```python
  def test_maybe_build_force_lock_returns_none_when_disabled() -> None:
      from src.config import AppConfig, ForceLockConfig
      from src.main import _maybe_build_force_lock

      cfg = AppConfig(force_lock=ForceLockConfig(enabled=False))

      assert _maybe_build_force_lock(cfg) is None


  @pytest.mark.qt
  def test_maybe_build_force_lock_returns_controller_when_enabled(qtbot: pytest.QtBot) -> None:
      from src.app.force_lock_controller import ForceLockController
      from src.config import AppConfig, ForceLockConfig
      from src.main import _maybe_build_force_lock

      cfg = AppConfig(force_lock=ForceLockConfig(enabled=True))

      controller = _maybe_build_force_lock(cfg)

      assert isinstance(controller, ForceLockController)
  ```

  - `test_main_window_emits_clear_requested`：點擊主視窗的「清除資料」按鈕 → `clear_data_requested` 發出。
  - `test_maybe_build_force_lock_returns_none_when_disabled`：`force_lock.enabled=False`（預設）→ `None`，不需 `qtbot`（不建立任何 `QObject`）。
  - `test_maybe_build_force_lock_returns_controller_when_enabled`：`force_lock.enabled=True` → 回傳 `ForceLockController` 實例（需 `qtbot` 提供 `QApplication`）。

---

## 完成定義（Definition of Done）

- [ ] `MainWindow` 有 `clear_data_requested` 訊號與「清除資料」按鈕（位於 `TodaySummaryView` 同列）
- [ ] `main.py`：`ReturnPromptDialog` 注入 `cfg.reminder.return_sound`；清除資料兩入口共用同一處理器；`_maybe_build_force_lock` 依設定決定是否建立並接線
- [ ] 3 個測試新增並通過
- [ ] `rtk pytest tests/test_ui.py tests/test_main.py` 全數通過
- [ ] `rtk pytest` 全專案測試通過（整合驗證）
- [ ] `rtk ruff check src/ui/main_window.py src/main.py` 無錯誤
- [ ] `rtk mypy src cli` 無新增錯誤
