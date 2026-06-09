# M4 `src/app/connection_state.py` — 連線狀態模型

**目標**：定義 UI 用的連線狀態枚舉，並提供 worker 字串映射、語意色彩角色、圖示鍵的純函式。

**涉及檔案**：
- 新增：`src/app/connection_state.py`
- 新增：`tests/test_connection_state.py`

**相依**：無（純枚舉 + 純函式）。

---

## 任務清單

- [ ] **1. 建立 `src/app/connection_state.py`，定義枚舉**

  ```python
  from __future__ import annotations
  from enum import Enum

  class ConnectionState(Enum):
      IDLE = "idle"
      CONNECTING = "connecting"
      CONNECTED = "connected"
      RECONNECTING = "reconnecting"
      NO_SIGNAL = "no_signal"
      ERROR = "error"
  ```

- [ ] **2. 實作 `from_status()`**

  ```python
  _STATUS_MAP: dict[str, ConnectionState] = {
      "connecting":   ConnectionState.CONNECTING,
      "connected":    ConnectionState.CONNECTED,
      "reconnecting": ConnectionState.RECONNECTING,
      "no_signal":    ConnectionState.NO_SIGNAL,
  }

  def from_status(status: str) -> ConnectionState:
      """Worker 發出的字串 → ConnectionState。未知字串 → IDLE。"""
      return _STATUS_MAP.get(status, ConnectionState.IDLE)
  ```

- [ ] **3. 實作 `severity()`**

  ```python
  _SEVERITY: dict[ConnectionState, str] = {
      ConnectionState.IDLE:        "neutral",
      ConnectionState.CONNECTING:  "info",
      ConnectionState.CONNECTED:   "success",
      ConnectionState.RECONNECTING: "warning",
      ConnectionState.NO_SIGNAL:   "warning",
      ConnectionState.ERROR:       "danger",
  }

  def severity(state: ConnectionState) -> str:
      """回傳語意色彩角色，供 M8 QSS 上色。"""
      return _SEVERITY[state]
  ```

- [ ] **4. 實作 `icon_key()`**

  ```python
  _ICON_KEY: dict[ConnectionState, str] = {
      ConnectionState.IDLE:        "conn-idle",
      ConnectionState.CONNECTING:  "conn-connecting",
      ConnectionState.CONNECTED:   "conn-connected",
      ConnectionState.RECONNECTING: "conn-reconnecting",
      ConnectionState.NO_SIGNAL:   "conn-no-signal",
      ConnectionState.ERROR:       "conn-error",
  }

  def icon_key(state: ConnectionState) -> str:
      """回傳圖示鍵，確保每個狀態都有圖示（不只靠顏色）。"""
      return _ICON_KEY[state]
  ```

- [ ] **5. 新增 `tests/test_connection_state.py`**

  ```python
  from src.app.connection_state import ConnectionState, from_status, severity, icon_key

  def test_from_status_known():
      assert from_status("connecting")   == ConnectionState.CONNECTING
      assert from_status("connected")    == ConnectionState.CONNECTED
      assert from_status("reconnecting") == ConnectionState.RECONNECTING
      assert from_status("no_signal")    == ConnectionState.NO_SIGNAL

  def test_from_status_unknown_returns_idle():
      assert from_status("unknown_xyz") == ConnectionState.IDLE
      assert from_status("") == ConnectionState.IDLE

  def test_severity_all_states_have_value():
      for state in ConnectionState:
          result = severity(state)
          assert result in ("neutral", "info", "success", "warning", "danger")

  def test_icon_key_all_states_non_empty():
      for state in ConnectionState:
          key = icon_key(state)
          assert isinstance(key, str) and len(key) > 0

  def test_error_not_mapped_via_from_status():
      # ERROR 由主視窗收到 failed 訊號時直接設定，不經 from_status
      assert from_status("error") == ConnectionState.IDLE
  ```

- [ ] **6. 執行測試確認通過**

  ```bash
  rtk pytest tests/test_connection_state.py -v
  ```

- [ ] **7. 更新 M3 的 `CONN_TEXT` 使用 `ConnectionState` 鍵（若 M3 已完成）**

  在 `src/ui/strings.py` 中，將 `CONN_TEXT` 的型別改為：
  ```python
  from src.app.connection_state import ConnectionState

  CONN_TEXT: dict[ConnectionState, str] = {
      ConnectionState.IDLE:        "待機",
      ConnectionState.CONNECTING:  "連線中",
      ConnectionState.CONNECTED:   "已連線",
      ConnectionState.RECONNECTING: "重新連線中",
      ConnectionState.NO_SIGNAL:   "收不到影像",
      ConnectionState.ERROR:       "發生錯誤",
  }
  ```
  同步更新 `tests/test_strings.py` 中的 `test_conn_text_covers_all_states`：
  ```python
  def test_conn_text_covers_all_states():
      for state in ConnectionState:
          assert state in strings.CONN_TEXT
  ```

- [ ] **8. 執行全部測試確認通過**

  ```bash
  rtk pytest tests/test_connection_state.py tests/test_strings.py -v
  ```

- [ ] **9. Commit**

  ```bash
  rtk git add src/app/connection_state.py tests/test_connection_state.py src/ui/strings.py tests/test_strings.py
  rtk git commit -m "feat(M4): 新增連線狀態模型 connection_state.py"
  ```
