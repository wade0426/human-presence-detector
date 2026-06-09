# M3 `src/ui/strings.py` — UI 文案集中

**目標**：集中所有面向使用者的繁中字串，對應 proposal §11，利於一致性與日後 i18n。

**涉及檔案**：
- 新增：`src/ui/strings.py`
- 新增：`tests/test_strings.py`

**相依**：`src/types.py`（`TimerState`）、`src/app/connection_state.py`（`ConnectionState`，M4）；無 Qt 相依。

> **注意**：本模塊依賴 M4 的 `ConnectionState`。若 M4 尚未完成，先以字串鍵的 dict 佔位（`CONN_TEXT: dict[str, str]`），M4 完成後再改為 `dict[ConnectionState, str]`。

---

## 任務清單

- [ ] **1. 建立 `src/ui/strings.py`，填入設定相關字串**

  ```python
  from __future__ import annotations

  # ── 設定視窗 ──────────────────────────────────────────────────
  SETTINGS_TITLE = "設定"
  SETTINGS_SAVED_RESTART = "設定已儲存。部分變更需要重新啟動程式後才會生效。"
  SETTINGS_SAVED_OK = "知道了"
  SETTINGS_SAVE = "儲存變更"
  SETTINGS_CANCEL = "取消"

  # ── 欄位驗證錯誤 ──────────────────────────────────────────────
  ERR_RTSP_URL_EMPTY = "請先填入 RTSP 串流位址。"
  ERR_CONFIDENCE_RANGE = "把握度必須介於 0（不含）到 1 之間。"
  ERR_BOX_RATIO_RANGE = "高度比例必須介於 0（不含）到 1 之間。"
  ERR_DEBOUNCE_MIN = "去抖動次數必須為大於等於 1 的整數。"
  ERR_MINUTE_RANGE = "分鐘數必須介於 0.1 到 9999 之間。"
  ```

- [ ] **2. 新增連線狀態字串（依賴 M4，先用字串鍵佔位）**

  ```python
  # ── 連線 / 狀態 ───────────────────────────────────────────────
  # key 對應 ConnectionState.value（M4 完成後改為 dict[ConnectionState, str]）
  CONN_TEXT: dict[str, str] = {
      "idle":        "待機",
      "connecting":  "連線中",
      "connected":   "已連線",
      "reconnecting": "重新連線中",
      "no_signal":   "收不到影像",
      "error":       "發生錯誤",
  }
  CONN_NO_SIGNAL = "目前收不到影像。請確認攝影機或串流來源後再試一次。"
  CONN_RECONNECTING = "連線中斷，正在重新連線…"
  CONN_RETRY = "重試"
  CONN_ERROR_PREFIX = "錯誤："
  ```

- [ ] **3. 新增計時狀態字串**

  ```python
  from src.types import TimerState

  # ── 計時狀態 ──────────────────────────────────────────────────
  STATE_TEXT: dict[TimerState, str] = {
      TimerState.IDLE:      "待機",
      TimerState.WORKING:   "工作中",
      TimerState.PAUSED:    "短暫離開",
      TimerState.REMINDING: "提醒中",
  }
  ```

- [ ] **4. 新增提醒與今日彙總字串**

  ```python
  # ── 提醒 ──────────────────────────────────────────────────────
  REMIND_TITLE = "該休息一下了"
  REMIND_BODY = "你已連續工作 {minutes} 分鐘。"
  REMIND_START_REST = "開始休息"
  REMIND_ACK = "我知道了"
  REMIND_SNOOZE = "再 {minutes} 分鐘"
  REMIND_CLOSE = "關閉"

  # ── 系統匣 ────────────────────────────────────────────────────
  TRAY_OPEN = "開啟主視窗"
  TRAY_PAUSE = "暫停偵測"
  TRAY_RESUME = "繼續偵測"
  TRAY_SETTINGS = "設定"
  TRAY_QUIT = "結束"

  # ── 今日彙總 ──────────────────────────────────────────────────
  TODAY_EMPTY = "今天還沒有紀錄，開始工作後就會出現在這裡。"
  TODAY_WORK_LABEL = "今日工作"
  TODAY_REST_LABEL = "休息次數"

  # ── 動作列 ────────────────────────────────────────────────────
  ACTION_EDIT_ROI = "編輯 ROI"
  ACTION_PAUSE = "暫停"
  ACTION_RESUME = "繼續"
  ACTION_SETTINGS = "設定"
  ```

- [ ] **5. 新增 `tests/test_strings.py`**

  ```python
  from src.types import TimerState
  from src.ui import strings

  def test_conn_text_covers_all_states():
      expected_keys = {"idle", "connecting", "connected", "reconnecting", "no_signal", "error"}
      assert set(strings.CONN_TEXT.keys()) == expected_keys

  def test_state_text_covers_all_timer_states():
      for state in TimerState:
          assert state in strings.STATE_TEXT
          assert strings.STATE_TEXT[state]  # 非空字串

  def test_remind_body_format():
      result = strings.REMIND_BODY.format(minutes=30)
      assert "30" in result

  def test_remind_snooze_format():
      result = strings.REMIND_SNOOZE.format(minutes=5)
      assert "5" in result
  ```

- [ ] **6. 執行測試確認通過**

  ```bash
  rtk pytest tests/test_strings.py -v
  ```

- [ ] **7. Commit**

  ```bash
  rtk git add src/ui/strings.py tests/test_strings.py
  rtk git commit -m "feat(M3): 新增 UI 文案集中模塊 strings.py"
  ```
