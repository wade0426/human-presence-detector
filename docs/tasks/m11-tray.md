# M11 `src/ui/tray.py` — 系統匣修正

**目標**：修正空圖示（D8）、實作 toggle 真正的暫停/繼續（D1）、新增 tooltip 狀態更新。

**涉及檔案**：
- 修改：`src/ui/tray.py`
- 修改：`tests/test_ui.py`

**相依**：A1 `icons.py`（`load_app_icon`）、M4 `ConnectionState`、M3 文案。

**前置條件**：A1、M3、M4 需先完成。

---

## 任務清單

- [ ] **1. 閱讀現有 `src/ui/tray.py` 確認現有介面**

  確認現有的：
  - `__init__` 建立方式
  - `bind_window()` 方法
  - 四個 action：`open_action`、`toggle_action`、`settings_action`、`quit_action`
  - `update_status()` 方法（若有）

- [ ] **2. 修正 `__init__`：使用 `load_app_icon()` 取代空圖示（修 D8）**

  找到 `QIcon()` 空建構或無設圖示的地方，改為：
  ```python
  from src.ui.icons import load_app_icon
  self.setIcon(load_app_icon())
  ```

- [ ] **3. 新增 `set_paused()` 方法（修 D1 文字同步）**

  ```python
  from src.ui import strings

  def set_paused(self, paused: bool) -> None:
      self._paused = paused
      if paused:
          self.toggle_action.setText(strings.TRAY_RESUME)
      else:
          self.toggle_action.setText(strings.TRAY_PAUSE)
  ```

  並在 `__init__` 設定初始文字：
  ```python
  self._paused = False
  self.toggle_action.setText(strings.TRAY_PAUSE)
  ```

- [ ] **4. 新增 `set_timer_state()` 和 `set_connection()` 更新 tooltip**

  ```python
  from src.types import TimerState
  from src.app.connection_state import ConnectionState
  from src.ui.strings import STATE_TEXT, CONN_TEXT

  def set_timer_state(self, state: TimerState) -> None:
      self._timer_state = state
      self._update_tooltip()

  def set_connection(self, state: ConnectionState) -> None:
      self._conn_state = state
      self._update_tooltip()

  def _update_tooltip(self) -> None:
      timer_text = STATE_TEXT.get(getattr(self, "_timer_state", TimerState.IDLE), "")
      conn_text = CONN_TEXT.get(getattr(self, "_conn_state", ConnectionState.IDLE), "")
      self.setToolTip(f"人體辨識提醒 — {conn_text} / {timer_text}")
  ```

  在 `__init__` 中初始化狀態變數：
  ```python
  self._timer_state = TimerState.IDLE
  self._conn_state = ConnectionState.IDLE
  ```

- [ ] **5. 新增 / 更新 `tests/test_ui.py` 的 TrayIcon 測試**

  ```python
  def test_tray_icon_not_null(qtbot):
      from src.ui.tray import TrayIcon
      tray = TrayIcon()
      assert not tray.icon().isNull()

  def test_tray_set_paused_changes_toggle_text(qtbot):
      from src.ui.tray import TrayIcon
      from src.ui import strings
      tray = TrayIcon()
      tray.set_paused(True)
      assert tray.toggle_action.text() == strings.TRAY_RESUME
      tray.set_paused(False)
      assert tray.toggle_action.text() == strings.TRAY_PAUSE

  def test_tray_tooltip_updates_with_state(qtbot):
      from src.ui.tray import TrayIcon
      from src.types import TimerState
      from src.app.connection_state import ConnectionState
      tray = TrayIcon()
      tray.set_timer_state(TimerState.WORKING)
      tray.set_connection(ConnectionState.CONNECTED)
      tooltip = tray.toolTip()
      assert "工作中" in tooltip
      assert "已連線" in tooltip
  ```

- [ ] **6. 執行測試確認通過**

  ```bash
  rtk pytest tests/test_ui.py -k "tray" -v
  ```

- [ ] **7. Commit**

  ```bash
  rtk git add src/ui/tray.py tests/test_ui.py
  rtk git commit -m "fix(M11): 修正系統匣圖示空值、toggle 文字、tooltip 狀態更新"
  ```
