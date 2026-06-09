# 詳細設計文檔：人體辨識休息提醒系統 — UI/UX 與渲染改善

| 項目 | 內容 |
|---|---|
| 上游文件 | `docs/proposal.md`（需求文檔 v1.0） |
| 設計層級 | 介面層級（職責、對外介面、相依與資料流、關鍵邏輯虛擬碼） |
| 模塊劃分 | 依邏輯元件（非依需求編號），每元件可獨立測試 |
| 重大決策 | 移除 `reset_mode`（detection/dismiss/snooze）與 `snooze`，改採單一「開始休息 → 休息中 → 歡迎回來」統一流程 |

> 本文件不貼完整實作；關鍵邏輯以虛擬碼／條件描述呈現。型別簽章以 Python 標註，作為實作契約。

---

## 目錄

1. 設計目標與原則
2. 整體架構與相依關係
3. 核心狀態機（M2 的行為規格）
4. 模塊詳細設計（M1–M9）
5. 跨模塊訊號／事件對照表
6. 設定變更與資料遷移
7. 移除項與影響面（reset_mode / snooze）
8. 測試策略總覽
9. 風險與緩解
10. 待確認事項

---

## 1. 設計目標與原則

- **模塊獨立**：以邏輯元件切分，元件間透過明確介面（函式簽章、Qt Signal、Protocol）溝通；相依方向單向、無循環。
- **可獨立測試**：核心邏輯（狀態機、休息計算、暫停凍結）為純 Python、以注入時鐘（`clock: Callable[[], float]`）驅動，不依賴 Qt 或實體攝影機即可單元測試；UI 與 I/O 元件以假物件（Fake）注入相依。
- **單一真相來源**：計時、狀態、休息與暫停的「時間真相」全部集中在 `TimerEngine`，UI 只負責呈現快照（`TimerSnapshot`）。
- **最小破壞**：沿用既有架構（worker/thread、widgets、settings schema、reminder factory）；新增以新檔案為主，降低既有檔案改動面。

### 相依方向（由下而上，不可逆向）

```
src/types.py  (Domain 型別：列舉、dataclass)          ← 無相依
   ▲
src/timer_engine.py (狀態機，純邏輯)                   ← 只相依 types
src/capture/* (影像擷取，純邏輯/執行緒)                ← 只相依 types + cv2
   ▲
src/app/worker.py (協調器)                            ← 相依 types、timer_engine、capture(Protocol)
   ▲
src/ui/* , src/reminder/* (UI 呈現)                   ← 相依 types、strings、theme
   ▲
src/main.py (組裝/接線)                               ← 相依以上全部
```

UI 元件不可相依 worker/engine 的內部；只透過 `TimerSnapshot`、`bool present`、Qt Signal 互動。

---

## 2. 整體架構與相依關係

### 2.1 元件清單與需求對應

| 模塊 | 檔案 | 職責 | 涵蓋需求 |
|---|---|---|---|
| **M1 Domain 型別** | `src/types.py`、`src/config.py`(列舉) | 狀態列舉、事件列舉、快照、休息模式列舉、Context | 3,4,5,7 之共用型別 |
| **M2 計時/狀態機** | `src/timer_engine.py` | 工作/休息/提醒/暫停的狀態與時間真相 | 3,4,5,7 |
| **M3 影像擷取** | `src/capture/video_source.py`、`src/capture/frame_grabber.py`(新) | 高頻擷取、保留最新影格、最小緩衝 | 8 |
| **M4 協調器** | `src/app/worker.py` | 串接擷取→偵測→狀態機→訊號；暫停/開始休息/確認回來 | 1,3,4,5,8 |
| **M5 主視窗與狀態顯示** | `src/ui/main_window.py`、`status_strip.py`、`presence_badge.py`(新) | 人在徽章、狀態文字（含休息中/已暫停） | 1,7 |
| **M6 動作列與 ROI 編輯** | `action_bar.py`、`preview_view.py`、`theme.py` | 離開鈕、暫停鈕、ROI 編輯視覺回饋 | 2,5,6 |
| **M7 提醒/休息流程 UI** | `reminder/popup.py`、`reminder/return_prompt.py`(新)、`strings.py` | 單一「開始休息」彈窗、歡迎回來確認窗 | 3,4 |
| **M8 設定與結構** | `config.py`、`settings_schema.py`、`settings.py` | 新增 `rest_count_mode`、移除 reset_mode/snooze | 設定變更 |
| **M9 應用組裝** | `src/main.py` | 接線新訊號、預覽渲染計時器、離開確認 | 整合 |

### 2.2 執行緒模型與資料流

三條獨立節奏，彼此解耦（解決需求 8 的延遲/破圖根因）：

```
┌──────────────────────────────────────────────────────────────┐
│ (A) 擷取執行緒  FrameGrabber.thread                            │
│     loop: frame = source.read(); latest := frame (atomic)      │  ~來源原生 FPS、緩衝=1
└──────────────┬───────────────────────────────────┬────────────┘
               │ latest()                            │ latest()
               ▼                                     ▼
┌──────────────────────────┐        ┌────────────────────────────────────┐
│ (B) 預覽渲染 QTimer (UI)  │        │ (C) 偵測執行緒 DetectionWorker      │
│   ~33ms 拉 latest→畫面    │        │   ~interval_sec 拉 latest→偵測      │  解耦：預覽不再被偵測節流
│   （需求 8 即時預覽）     │        │   →presence→TimerEngine→Signals     │
└──────────────────────────┘        └────────────────┬───────────────────┘
                                                      │ Qt Signal（跨執行緒佇列）
                                                      ▼
                                          M5/M6/M7 UI（主執行緒）
```

- **(A) 擷取**：獨立 `threading.Thread`，持續解碼、只保留最新影格（丟棄積壓），避免讀到緩衝區舊格。
- **(B) 預覽**：UI 主執行緒 `QTimer`（預設 ~30fps），直接拉 `grabber.latest()` 渲染；與偵測頻率無關。
- **(C) 偵測**：既有 `DetectionWorker.run()`（在 `QThread`），改為每 `interval_sec` 拉一次 `latest()` 做偵測與狀態機推進。

> 暫停（需求 5）時：(B)(C) 皆停（畫面定格、不偵測），(A) 可一併停止以省資源；正確性關鍵在 `TimerEngine.resume(now)` 重設時間基準。

---

## 3. 核心狀態機（M2 行為規格）

### 3.1 狀態集

| 列舉 `TimerState` | 顯示文字（`STATE_TEXT`） | 意義 |
|---|---|---|
| `IDLE` | 待機 | 尚未開始 |
| `WORKING` | 工作中 | 計時中 |
| `AWAY`（原 `PAUSED` 更名） | 短暫離開 | 工作中暫時離座、未達重置門檻（自動） |
| `REMINDING` | 提醒中 | 達工作門檻、提醒中 |
| `RESTING`（新） | 休息中 | 已開始休息、倒數中 |
| `AWAITING_RETURN`（新） | 待機 | 休息完成、等待「歡迎回來」確認（不計時） |
| `SUSPENDED`（新） | 已暫停 | 手動暫停（凍結，凌駕其他狀態） |

> `AWAITING_RETURN` 內部需為獨立狀態（避免在確認前自動開始工作），但顯示文字沿用「待機」（proposal 假設 3）。

### 3.2 輸入（對外介面）

```python
class TimerEngine:
    def __init__(self, work_threshold_sec: float, reset_threshold_sec: float,
                 required_rest_sec: float, repeat_interval_sec: float,
                 rest_count_mode: RestCountMode) -> None: ...
        # 注意：移除 reset_mode、snooze_sec；新增 rest_count_mode

    # 週期推進（由偵測執行緒每 interval_sec 呼叫一次）
    def update(self, present: bool, now: float) -> list[TimerEvent]: ...

    # 使用者動作
    def start_rest(self, now: float) -> list[TimerEvent]: ...      # 取代 on_reminder_dismissed
    def confirm_return(self, now: float) -> list[TimerEvent]: ...  # 「開始新一輪」

    # 手動暫停（需求 5）
    def pause(self, now: float) -> None: ...
    def resume(self, now: float) -> None: ...

    # 唯讀
    def snapshot(self, now: float) -> TimerSnapshot: ...
    @property
    def state(self) -> TimerState: ...
```

### 3.3 狀態轉移表

| 來源狀態 | 觸發 | 條件 | 目標狀態 | 送出事件 |
|---|---|---|---|---|
| IDLE | update | present | WORKING | WORK_STARTED（＋若有前次離開：REST_ENDED） |
| IDLE | update | ¬present | IDLE | — |
| WORKING | update | present 且 work_elapsed＋dt ≥ work_threshold | REMINDING | REMINDER_TRIGGERED |
| WORKING | update | present 且未達門檻 | WORKING | —（累計 work_elapsed） |
| WORKING | update | ¬present | AWAY | — |
| AWAY | update | present | WORKING | — |
| AWAY | update | ¬present 且 away ≥ reset_threshold | IDLE | WORK_ENDED(ended_by="reset") |
| REMINDING | update | present 且 (now−reminder_last) ≥ repeat_interval | REMINDING | REMINDER_REPEATED |
| REMINDING | start_rest | — | RESTING | REST_STARTED |
| REMINDING | update | ¬present（直接離座視同開始休息） | RESTING | REST_STARTED |
| RESTING | update | 未滿足休息（依模式累計/倒數） | RESTING | — |
| RESTING | update | 休息已滿足 且 present | AWAITING_RETURN | RETURN_PROMPT |
| RESTING | update | 休息已滿足 且 ¬present | RESTING | —（等待回座） |
| AWAITING_RETURN | confirm_return | — | WORKING | REST_ENDED、WORK_STARTED |
| AWAITING_RETURN | update | 任意 | AWAITING_RETURN | —（不自動確認） |
| 任意作用中狀態 | pause | — | SUSPENDED（記住前狀態） | — |
| SUSPENDED | resume | — | 還原前狀態 | —（`_last_t := now`） |

### 3.4 休息滿足判定（需求對應「兩種模式」）

```text
進入 RESTING 時：rest_started_at := now；rest_accumulated := 0
每次 update(present, now) 於 RESTING：
    dt := now - _last_t
    if rest_count_mode == PRESENCE:
        if not present: rest_accumulated += dt        # 只累計離座時間
        # present 時暫停累計（中途回座 → 暫停倒數，不重來）
        satisfied := rest_accumulated >= required_rest
    elif rest_count_mode == FIXED:
        satisfied := (now - rest_started_at) >= required_rest   # 不論在不在
    if satisfied and present:
        → AWAITING_RETURN, emit RETURN_PROMPT
```

### 3.5 暫停凍結與 bug 修正（需求 5）

根因：暫停期間 worker 不呼叫 `update()`，`_last_t` 停在暫停前；恢復後首個 `dt = now − _last_t` 含整段暫停時間。

```python
def pause(self, now):
    self._state_before_pause = self._state
    self._paused = True
    # 不再累計時間；snapshot() 回報 SUSPENDED

def resume(self, now):
    self._paused = False
    self._last_t = now          # ★關鍵：重設基準，使下個 dt ≈ 0
    self._state = self._state_before_pause

def update(self, present, now):
    if self._paused:
        return []               # 暫停中為 no-op（防禦）
    ...

def snapshot(self, now):
    state = TimerState.SUSPENDED if self._paused else self._state
    ...
```

### 3.6 快照（`TimerSnapshot`）擴充

```python
@dataclass(frozen=True)
class TimerSnapshot:
    state: TimerState
    work_elapsed_sec: float
    away_elapsed_sec: float
    remaining_to_reminder_sec: float
    reminder_active: bool
    rest_remaining_sec: float = 0.0   # 新增：休息中倒數（FIXED 模式）
    rest_elapsed_sec: float = 0.0     # 新增：已休息時間（PRESENCE 模式累計）
```

---

## 4. 模塊詳細設計

每個模塊統一格式：**職責 / 涵蓋需求 / 對外介面 / 相依與資料流 / 關鍵邏輯 / 測試設計（邊界＋可注入相依＋案例清單）**。

---

### M1. Domain 型別（`src/types.py`、`src/config.py` 列舉）

- **職責**：定義跨模塊共用的列舉與資料結構，無行為。
- **涵蓋需求**：3,4,5,7（共用）。
- **對外介面（變更點）**：
  ```python
  class TimerState(Enum):
      IDLE="idle"; WORKING="working"; AWAY="away"; REMINDING="reminding"
      RESTING="resting"; AWAITING_RETURN="awaiting_return"; SUSPENDED="suspended"
      # 變更：PAUSED → AWAY（更名）；新增 RESTING/AWAITING_RETURN/SUSPENDED

  class TimerEventType(Enum):
      WORK_STARTED; WORK_ENDED; REST_STARTED(新); REST_ENDED
      REMINDER_TRIGGERED; REMINDER_REPEATED; RETURN_PROMPT(新)

  class RestCountMode(Enum):       # 新增
      PRESENCE="presence"; FIXED="fixed"

  # 移除：class ResetMode（detection/dismiss/snooze）

  @dataclass(frozen=True)
  class ReminderContext:           # 移除 reset_mode、snooze_minutes
      work_minutes: int
      media_path: str; media_type: str; sound_path: str
  ```
- **相依**：無（numpy 僅 Frame）。
- **測試設計**：
  - 邊界：純資料，驗證列舉值字串、dataclass 預設值。
  - 可注入相依：無。
  - 案例：`TimerState` 含新成員且字串值正確；`RestCountMode("presence"/"fixed")` 可建構；`ReminderContext` 不再有 reset_mode 欄位（型別契約）。

---

### M2. 計時/狀態機（`src/timer_engine.py`）

- **職責**：第 3 節全部行為的唯一實作；純邏輯、以 `now: float` 推進。
- **涵蓋需求**：3,4,5,7。
- **對外介面**：見 3.2。建構子簽章變更（移除 `reset_mode`、`snooze_sec`，新增 `rest_count_mode`）。
- **相依與資料流**：輸入 `present`（由 M4 從 M3 影格偵測而得）＋ `now`；輸出 `list[TimerEvent]` 與 `TimerSnapshot`。不相依 Qt。
- **關鍵邏輯**：3.4（休息判定）、3.5（暫停修正）、3.3（轉移表）。`start_rest()`/`confirm_return()` 取代舊 `on_reminder_dismissed()`。
- **測試設計**（`tests/test_timer_engine.py`，純單元、無 qt）：
  - 邊界：僅 `update/start_rest/confirm_return/pause/resume/snapshot` 對外；以離散 `now` 序列驅動。
  - 可注入相依：時間以參數 `now` 注入（不需 clock 物件）。
  - 案例清單（對應驗收標準）：
    1. 工作達門檻 → REMINDER_TRIGGERED、state=REMINDING。
    2. 提醒中持續在場 → 每 repeat_interval 一次 REMINDER_REPEATED（無 reset_mode 分支）。
    3. 提醒中按 `start_rest` → state=RESTING、REST_STARTED。
    4. 提醒中直接離座 → state=RESTING、REST_STARTED。
    5. PRESENCE 模式：離座累計達 required_rest 後回座 → RETURN_PROMPT、state=AWAITING_RETURN；中途回座會暫停累計（不重來）。
    6. FIXED 模式：按 start_rest 後不論在不在，經 required_rest → 滿足；回座 → RETURN_PROMPT。
    7. AWAITING_RETURN 期間 `update` 不改變狀態、不計時；`confirm_return` → REST_ENDED＋WORK_STARTED、work_elapsed=0、state=WORKING。
    8. **暫停凍結（需求 5）**：working 累計 4s → pause(5) → resume(60) → 下一 update(present, 60.x) 後 work_elapsed 仍≈4s（未含暫停 55s）；暫停期間 snapshot.state==SUSPENDED。
    9. AWAY：離座未達 reset_threshold 回座續計；達門檻 → WORK_ENDED(reset)、IDLE。
    10. snapshot 在 RESTING 回報 `rest_remaining_sec`/`rest_elapsed_sec` 正確。

---

### M3. 影像擷取（`src/capture/video_source.py` + 新 `frame_grabber.py`）

- **職責**：與 RTSP/Webcam 解碼解耦於偵測；持續擷取並保留「最新影格」，最小化緩衝。
- **涵蓋需求**：8。
- **對外介面**：
  ```python
  # video_source.py：RTSPSource.open() 內新增
  #   self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
  # 其餘 WebcamSource/RTSPSource/ReconnectingSource 介面不變

  class FrameProvider(Protocol):                 # 新增（worker 相依此抽象）
      def latest(self) -> Frame | None: ...
      @property
      def is_opened(self) -> bool: ...

  class FrameGrabber:                            # 新增 frame_grabber.py，實作 FrameProvider
      def __init__(self, source: VideoSource,
                   clock: Callable[[], float] = time.monotonic) -> None: ...
      def start(self) -> None: ...               # 啟動背景擷取執行緒
      def stop(self) -> None: ...                # 停止並 join、release source
      def latest(self) -> Frame | None: ...      # 執行緒安全、回傳最近一張
      @property
      def is_opened(self) -> bool: ...
  ```
- **相依與資料流**：包裝既有 `ReconnectingSource`（負責重連）。背景執行緒迴圈：`frame = source.read(); with lock: self._latest = frame`。消費者（預覽 QTimer、偵測 worker）呼叫 `latest()`。
- **關鍵邏輯（執行緒安全）**：以 `threading.Lock` 保護單一參考的原子替換；`Frame`（含 numpy 陣列）一經發布即視為不可變，消費者只讀不改，避免讀到半張影格（需求 8「破圖」之軟體面緩解）。`latest()` 在尚無影格或停止後回傳 `None`。
- **測試設計**（`tests/test_frame_grabber.py`，純單元、無 qt）：
  - 邊界：以 `FakeSource`（回傳預排影格序列）注入；不開實體攝影機。
  - 可注入相依：`source`、`clock`。
  - 案例：
    1. `start()` 後 `latest()` 回傳最後送入的影格（證明「保留最新、丟棄舊格」）。
    2. source 回傳 None 時 `latest()` 不拋例外、回傳前一張或 None；`is_opened` 正確委派。
    3. `stop()` 後執行緒結束、`source.release()` 被呼叫一次、`latest()` 回 None。
    4. 併發讀取（多執行緒呼叫 `latest()`）不拋例外（壓力測試）。
  - 註：`CAP_PROP_BUFFERSIZE=1` 屬實機行為，不在單元測試覆蓋，列入手動驗收（9.x）。

---

### M4. 協調器（`src/app/worker.py`）

- **職責**：串接 擷取(M3)→偵測→狀態機(M2)→Qt 訊號；轉發使用者動作（開始休息、確認回來、暫停）。
- **涵蓋需求**：1（發出 presence）、3/4（start_rest/confirm_return）、5（pause→engine）、8（取 latest 偵測、不再節流預覽）。
- **對外介面（變更）**：
  ```python
  class DetectionWorker(QObject):
      presence_changed = Signal(bool)        # （需求1）M5 接此更新人在徽章
      timer_updated = Signal(object)         # TimerSnapshot
      reminder_show = Signal(object)         # 提醒「開始休息」彈窗（含 repeat）
      return_prompt = Signal(object)         # 新增：歡迎回來確認窗
      connection_status = Signal(str)
      failed = Signal(str)
      # 移除：frame_ready（預覽改由 M9 的 QTimer 直接拉 M3.latest()）
      # 移除：reminder_repeat（與 reminder_show 合併）

      def __init__(self, frames: FrameProvider, detector, presence_evaluator,
                   timer_engine, store, detection_interval_sec, reminder_context,
                   clock=time.monotonic) -> None: ...   # source → frames(FrameProvider)

      def run(self) -> None: ...
      def stop(self) -> None: ...
      def pause(self) -> None: ...            # set _paused; engine.pause(now); 發一次 SUSPENDED 快照
      def resume(self) -> None: ...           # engine.resume(now); 清 _paused
      def start_rest(self) -> None: ...       # 呼叫 engine.start_rest → dispatch
      def confirm_return(self) -> None: ...   # 呼叫 engine.confirm_return → dispatch
      def set_roi(self, roi: BBox) -> None: ...
  ```
- **相依與資料流**：`run()` 迴圈每 `interval_sec`：`frame = self._frames.latest()`；None → 依 `is_opened` 發 `connecting/no_signal/reconnecting`；否則 `detector.detect`→`presence_evaluator.update`→`presence_changed.emit`→`engine.update`→`_dispatch`→`timer_updated.emit`。
- **關鍵邏輯**：
  - `_dispatch` 事件對映（見第 5 節）：`REMINDER_TRIGGERED/REPEATED → reminder_show`；`RETURN_PROMPT → return_prompt`；`WORK_ENDED/REST_ENDED → store.log_session`。
  - 暫停：`pause()` 不再只是 `sleep/continue` 後遺失時間，而是 `engine.pause(now)` 並發出一次 `timer_updated(SUSPENDED 快照)`；`run()` 迴圈在 `_paused` 時 idle，不取影格、不偵測。
- **測試設計**（`tests/test_worker.py`，`@pytest.mark.qt`，沿用現有 Fake）：
  - 邊界：以 `FakeSource`→包成 `FrameProvider`（新增 `FakeFrames` 或讓 FakeSource 直接實作 `latest/is_opened`）、`FakeDetector`、`FakeStore`、`FakeClock` 注入。
  - 可注入相依：`frames`、`detector`、`presence_evaluator`、`timer_engine`、`store`、`clock`。
  - 案例：
    1. 達門檻 → 發 `reminder_show`（取代舊 reminder_show 測試）。
    2. `start_rest()` → 不再發提醒、狀態進 RESTING（透過後續 `timer_updated` 快照驗證）。
    3. 休息滿足回座 → 發 `return_prompt`。
    4. `confirm_return()` → `store.log_session` 出現一筆 work（新一輪起算）。
    5. `pause()` → 立即收到一個 `state==SUSPENDED` 的 `timer_updated`；暫停期間不再有偵測造成的狀態前進。
    6. 既有連線狀態測試（connecting/no_signal/reconnecting）改以 `latest()`/`is_opened` 行為對應，斷言不變。
    7. `stop()` → 透過 grabber 釋放來源（`release_calls == 1`）。

---

### M5. 主視窗與狀態顯示（`main_window.py`、`status_strip.py`、新 `presence_badge.py`）

- **職責**：呈現「有沒有人」與計時狀態文字（含新狀態）。
- **涵蓋需求**：1、7。
- **對外介面**：
  ```python
  # 新 src/ui/widgets/presence_badge.py（仿 connection_badge.py）
  class PresenceBadge(QWidget):
      def set_present(self, present: bool) -> None: ...   # 綠●有人 / 灰○無人

  # main_window.py
  class MainWindow(QMainWindow):
      def on_presence_changed(self, present: bool) -> None:   # 改寫：更新 PresenceBadge（移除 del）
      def on_timer_updated(self, snap: TimerSnapshot) -> None: # 既有；StatusStrip 用新 STATE_TEXT
  ```
  ```python
  # strings.py：STATE_TEXT 補齊新狀態
  STATE_TEXT = {IDLE:"待機", WORKING:"工作中", AWAY:"短暫離開",
                REMINDING:"提醒中", RESTING:"休息中",
                AWAITING_RETURN:"待機", SUSPENDED:"已暫停"}
  PRESENCE_YES="有人"; PRESENCE_NO="無人"     # 新增
  ```
- **相依與資料流**：`worker.presence_changed → MainWindow.on_presence_changed → PresenceBadge`；`worker.timer_updated → StatusStrip.update_snapshot`。連線中斷時（M4 發 `no_signal/reconnecting`）由 `on_connection_status` 將 PresenceBadge 設為「無人」（proposal 假設 4）。
- **關鍵邏輯**：`StatusStrip` 在 `RESTING` 時可顯示 `rest_remaining_sec` 倒數（取代固定顯示 work_elapsed），其餘狀態維持原顯示。
- **測試設計**（`tests/test_ui.py`，`@pytest.mark.qt`）：
  - 邊界：直接呼叫 `set_present`/`update_snapshot`/`on_connection_status`，斷言可見文字。
  - 可注入相依：以建構假 `TimerSnapshot` 注入。
  - 案例：
    1. `set_present(True/False)` → 徽章文字「有人/無人」與顏色 role 切換。
    2. snapshot.state=RESTING → StatusStrip 顯示「休息中」。
    3. snapshot.state=SUSPENDED → 顯示「已暫停」。
    4. AWAY vs SUSPENDED 顯示文字可區分（短暫離開 / 已暫停）。
    5. `on_connection_status("no_signal")` → 人在徽章顯示「無人」。

---

### M6. 動作列與 ROI 編輯（`action_bar.py`、`preview_view.py`、`theme.py`）

- **職責**：離開鈕（需求2）、暫停鈕狀態（需求5 UI 面）、ROI 編輯視覺回饋（需求6）。
- **涵蓋需求**：2、5、6。
- **對外介面**：
  ```python
  class ActionBar(QWidget):
      edit_roi_toggled = Signal(bool)
      pause_toggled = Signal(bool)
      open_settings = Signal()
      request_quit = Signal()          # 新增：離開鈕
      def set_edit_active(self, on: bool) -> None: ...  # 切換按鈕文字/樣式

  # preview_view.py
  class PreviewView(QWidget):
      def set_edit_mode(self, on: bool) -> None: ...    # 既有；on 時顯示提示文字
  ```
  ```python
  # strings.py
  ACTION_QUIT="離開"; ACTION_EDIT_ROI_ACTIVE="完成編輯"
  ROI_HINT="拖曳以選取偵測區域"
  QUIT_CONFIRM_TITLE="離開"; QUIT_CONFIRM_BODY="確定要關閉系統嗎？"

  # theme.py：build_qss 新增 checked / danger 樣式
  #   QPushButton:checked { background:{accent 深色}; border:2px solid ...; }
  #   QPushButton[role="danger"] { background:{danger}; }
  ```
- **相依與資料流**：`edit_roi_toggled → MainWindow → PreviewView.set_edit_mode`（同時 ActionBar 自身 `set_edit_active` 改文字/樣式、PreviewView 顯示 `ROI_HINT`）。`request_quit → M9` 跳二次確認 → `app.quit`。
- **關鍵邏輯**：ROI 鈕為 `checkable`；`toggled(True)` → 文字「完成編輯」＋ `:checked` 樣式生效 ＋ 預覽顯示提示；`toggled(False)` 還原。離開鈕 `role="danger"` 置於右側 stretch 之後、設定鈕之前。
- **測試設計**（`tests/test_ui.py`/`test_theme.py`，qt）：
  - 邊界：以 `QSignalSpy`/直接呼叫驗證樣式屬性與文字。
  - 案例：
    1. ROI 鈕 toggled(True) → 文字==「完成編輯」、`isChecked()` 為真、PreviewView 提示可見。
    2. toggled(False) → 文字還原、提示消失。
    3. 點離開鈕 → 發 `request_quit`。
    4. `build_qss` 產生的樣式含 `QPushButton:checked` 與 `[role="danger"]` 規則（字串斷言）。

---

### M7. 提醒/休息流程 UI（`reminder/popup.py`、新 `reminder/return_prompt.py`、`strings.py`）

- **職責**：單一「開始休息」提醒彈窗（需求4）、歡迎回來確認窗（需求3）。
- **涵蓋需求**：3、4。
- **對外介面**：
  ```python
  class PopupReminder(QDialog):
      start_rest = Signal()                      # 取代 dismissed
      def show(self, ctx: ReminderContext | None = None) -> None: ...
      # 移除：close_button、_setup_buttons 的 reset_mode/snooze 分支
      # 僅保留單一按鈕 dismiss_button(文字「開始休息」) → emit start_rest → hide

  # 新 src/reminder/return_prompt.py
  class ReturnPromptDialog(QDialog):
      confirmed = Signal()                       # 「開始新一輪」
      def show_prompt(self, rest_minutes: int | None = None) -> None: ...
      def closeEvent(self, e) -> None: ...        # ignore：未確認前不可關閉（持續等待）
  ```
  ```python
  # strings.py
  REMIND_START_REST="開始休息"     # 既有，作為唯一動作鈕
  RETURN_TITLE="歡迎回來"; RETURN_BODY="休息結束，要開始新一輪工作嗎？"
  RETURN_CONFIRM="開始新一輪"
  # 移除：REMIND_ACK(我知道了)、REMIND_CLOSE(關閉)、REMIND_SNOOZE 之使用
  ```
- **相依與資料流**：`worker.reminder_show → PopupReminder.show`；`PopupReminder.start_rest → worker.start_rest`。`worker.return_prompt → ReturnPromptDialog.show_prompt`；`ReturnPromptDialog.confirmed → worker.confirm_return`。
- **關鍵邏輯**：`PopupReminder` 維持媒體（圖片/影片/音效）顯示邏輯不變，只精簡按鈕。`ReturnPromptDialog` 無媒體、單鈕、`closeEvent` 忽略關閉（呼應「一直等確認」）。
- **測試設計**（`tests/test_reminder.py`，qt）：
  - 邊界：建構 dialog、模擬點擊、斷言訊號與可見元件。
  - 案例：
    1. `PopupReminder` 僅一顆動作鈕、文字「開始休息」。
    2. 點「開始休息」→ 發 `start_rest`、視窗 hide。
    3. `ReturnPromptDialog` 點「開始新一輪」→ 發 `confirmed`。
    4. `ReturnPromptDialog.close()` → 視窗仍可見（closeEvent 被忽略）。
    5. `ReminderContext` 無 reset_mode/snooze 欄位仍能正常 `show`。

---

### M8. 設定與結構（`config.py`、`settings_schema.py`、`settings.py`）

- **職責**：新增 `rest_count_mode`；移除 reset_mode/snooze 之結構、驗證、UI 欄位與序列化。
- **涵蓋需求**：設定變更（支撐 M2 兩種休息模式）。
- **對外介面（變更）**：
  ```python
  # config.py
  @dataclass
  class TimerConfig:
      work_threshold_min: float = 45.0
      reset_threshold_min: float = 5.0
      required_rest_min: float = 5.0
      rest_count_mode: str = "presence"     # 新增（"presence" | "fixed"）

  @dataclass
  class ReminderConfig:
      method: str = "popup"
      repeat_interval_min: float = 2.0
      popup: PopupConfig = ...
      floating: FloatingConfig = ...
      # 移除：reset_mode、snooze_min

  # validate()：移除 reset_mode 驗證、移除 snooze_min 範圍檢查；
  #             新增 timer.rest_count_mode ∈ {"presence","fixed"} 檢查
  # _app_config_from_dict / _serialize_app_config：移除 reset_mode 讀寫；新增 rest_count_mode
  ```
  ```python
  # settings_schema.py：SCHEMA
  #   移除 FieldSpec("reminder.reset_mode", ...)、FieldSpec("reminder.snooze_min", ...)
  #   新增 FieldSpec("timer.rest_count_mode","休息計算方式",
  #                  "presence＝必須離座才算休息；fixed＝固定倒數。",
  #                  CHOICE, "基本", choices=("presence","fixed"))
  # settings.py：_get_widget_value 移除 reminder.reset_mode 的 ResetMode 特例
  ```
- **相依與資料流**：`main.py` 建構 `TimerEngine` 時改傳 `RestCountMode(cfg.timer.rest_count_mode)`；不再傳 `reset_mode`、`snooze_min`。
- **關鍵邏輯（資料遷移）**：舊 `config.yaml` 若仍含 `reminder.reset_mode`/`reminder.snooze_min`，因 loader 改用 `.get` 預設且不再讀取該鍵 → **被忽略不報錯**；下次 `save_config` 自然不再寫出。`validate()` 不得再因 `reset_mode` 觸發錯誤。
- **測試設計**（`tests/test_config.py`、`test_settings_schema.py`）：
  - 案例：
    1. 預設 `TimerConfig.rest_count_mode == "presence"`。
    2. `validate` 對 `rest_count_mode` 非法值報錯；合法值通過。
    3. 載入含舊 `reset_mode`/`snooze_min` 的 yaml → 不報錯、欄位被忽略。
    4. round-trip：save → load 後 `rest_count_mode` 保留、輸出不含 reset_mode/snooze。
    5. SCHEMA 不再含 reset_mode/snooze；含 rest_count_mode。

---

### M9. 應用組裝（`src/main.py`）

- **職責**：建立 M3 grabber、預覽 QTimer、接線新訊號、離開二次確認。
- **涵蓋需求**：整合 1,2,3,4,5,8。
- **對外介面**：無（組裝層）。
- **相依與資料流（接線變更）**：
  ```text
  grabber = FrameGrabber(create_source(cfg.source)); grabber.start()
  worker  = DetectionWorker(frames=grabber, ...)            # 注入 FrameProvider

  preview_timer = QTimer(33ms); preview_timer.timeout → window.on_frame_ready(grabber.latest())

  worker.presence_changed → window.on_presence_changed       # 需求1
  worker.timer_updated    → window.on_timer_updated / tray
  worker.reminder_show    → popup.show
  worker.return_prompt    → return_prompt.show_prompt        # 需求3
  popup.start_rest        → worker.start_rest                # 需求4
  return_prompt.confirmed → worker.confirm_return            # 需求3
  actions.request_quit    → _confirm_quit()                  # 需求2：QMessageBox.question → app.quit
  pause toggle            → worker.pause/resume（凍結）       # 需求5
  app.aboutToQuit         → grabber.stop(); _shutdown_worker_thread(...)
  ```
- **關鍵邏輯**：`_confirm_quit()` 以 `QMessageBox.question` 二次確認，確認才 `app.quit()`；退出時先 `grabber.stop()` 再停 worker thread，確保擷取執行緒 join、來源釋放。暫停時停 `preview_timer`（畫面定格）與 worker 偵測；恢復時重啟。
- **測試設計**：組裝層以整合/手動為主（見 9. 風險與 8. 策略）；可抽出 `_confirm_quit`、接線函式為可測純函式者優先單元化。

---

## 5. 跨模塊訊號／事件對照表

| 來源 | 訊號／事件 | 載荷 | 接收者 | 動作 |
|---|---|---|---|---|
| M2 | REMINDER_TRIGGERED / REPEATED | — | M4 `_dispatch` | emit `reminder_show(ctx)` |
| M2 | RETURN_PROMPT | — | M4 | emit `return_prompt(ctx)` |
| M2 | WORK_ENDED / REST_ENDED | duration, ended_by | M4 | `store.log_session(...)` |
| M4 | presence_changed | bool | M5 | PresenceBadge.set_present |
| M4 | timer_updated | TimerSnapshot | M5/Tray | StatusStrip / tooltip |
| M4 | reminder_show | ReminderContext | M7 PopupReminder | show（單鈕） |
| M4 | return_prompt | ctx | M7 ReturnPromptDialog | show_prompt |
| M7 PopupReminder | start_rest | — | M4 | `worker.start_rest()` |
| M7 ReturnPromptDialog | confirmed | — | M4 | `worker.confirm_return()` |
| M6 ActionBar | request_quit | — | M9 | 二次確認 → app.quit |
| M6 ActionBar | pause_toggled | bool | M9 | worker.pause/resume＋preview_timer 停/啟 |
| M3 FrameGrabber | latest()（拉取，非訊號） | Frame | M9 QTimer / M4 | 預覽渲染 / 偵測取樣 |

---

## 6. 設定變更與資料遷移

| 設定鍵 | 動作 | 預設 | 說明 |
|---|---|---|---|
| `timer.rest_count_mode` | 新增 | `presence` | `presence`＝離座才算休息（中途回座暫停累計）；`fixed`＝固定倒數 |
| `reminder.reset_mode` | 移除 | — | 統一流程取代；舊值載入時忽略 |
| `reminder.snooze_min` | 移除 | — | 無貪睡；舊值載入時忽略 |

遷移策略：向後相容（舊鍵被忽略、不報錯），無需轉檔腳本。

---

## 7. 移除項與影響面（reset_mode / snooze）

| 檔案 | 移除/變更 |
|---|---|
| `src/types.py` | 刪 `ResetMode`；`ReminderContext` 去 `reset_mode`/`snooze_minutes`；`TimerEventType` 移除僅服務 dismiss/snooze 的語意（保留 REST_ENDED） |
| `src/config.py` | `ReminderConfig` 去 `reset_mode`/`snooze_min`；`validate`/`_app_config_from_dict`/`_serialize_app_config` 同步 |
| `src/timer_engine.py` | 建構子去 `reset_mode`/`snooze_sec`；刪 `on_reminder_dismissed`；REMINDING 重複邏輯改為「無條件依 repeat_interval」 |
| `src/ui/settings_schema.py` | 刪 reset_mode/snooze 兩個 FieldSpec；加 rest_count_mode |
| `src/ui/settings.py` | `_get_widget_value` 去 ResetMode 特例 |
| `src/app/worker.py` | 去 `reminder_repeat`/`dismiss_reminder`；加 `start_rest`/`confirm_return`/`return_prompt` |
| `src/reminder/popup.py` | 去第二顆按鈕與 reset_mode 分支；`dismissed`→`start_rest` |
| `src/main.py` | 接線改用新訊號 |
| `tests/*` | `test_timer_engine.py` 去 dismiss/snooze 案例、改測 start_rest/confirm_return/pause；`test_config.py`/`test_settings_schema.py` 同步 |

---

## 8. 測試策略總覽

| 層級 | 對象 | 標記 | 重點 |
|---|---|---|---|
| 純單元（無 Qt） | M1 types、M2 timer_engine、M3 frame_grabber | 一般 | 狀態機全分支、休息兩模式、暫停凍結、最新影格保留 |
| Qt 單元 | M4 worker、M5/M6/M7 widgets/dialogs | `@pytest.mark.qt` | 訊號發送、文字/樣式、按鈕行為 |
| 整合/手動 | M9 接線、M3 實機 RTSP（緩衝/破圖/延遲） | 手動 | 端到端流程、RTSP 延遲與破圖實測 |

**需求 ↔ 模塊 ↔ 測試 對照**

| 需求 | 主模塊 | 關鍵測試 |
|---|---|---|
| 1 有沒有人 | M4,M5 | worker.presence_changed → PresenceBadge 文字 |
| 2 離開鈕 | M6,M9 | request_quit 發送、_confirm_quit 流程 |
| 3 回來確認 | M2,M4,M7 | RETURN_PROMPT、confirm_return、ReturnPromptDialog 不可關閉 |
| 4 單一按鈕 | M2,M7 | PopupReminder 單鈕、start_rest |
| 5 暫停凍結 | M2,M4 | resume 後 work_elapsed 不跳；SUSPENDED 快照 |
| 6 ROI 回饋 | M6 | toggled → 文字/樣式/提示 |
| 7 狀態文字 | M1,M5 | RESTING/SUSPENDED 顯示 |
| 8 RTSP | M3,M4,M9 | FrameGrabber 最新影格；手動實測延遲/破圖 |

---

## 9. 風險與緩解

1. **擷取執行緒生命週期**：未正確 `stop()`/join 會殘留執行緒或卡住釋放。緩解：`grabber.stop()` 於 `aboutToQuit` 最先呼叫、設逾時 join、`latest()` 停止後回 None。
2. **影格執行緒安全**：跨執行緒共享 numpy。緩解：鎖內原子替換參考、發布後不可變、消費者只讀。
3. **`CAP_PROP_BUFFERSIZE=1` 後端差異**：部分 FFMPEG 後端可能忽略此旗標。緩解：擷取執行緒「持續抽取最新格」本身即可壓低延遲；破圖殘留列入手動驗收，必要時開啟「未來選項」（tcp/硬解，超出本次範圍）。
4. **狀態機更名 `PAUSED→AWAY` 的回歸**：既有 `tests`、`tray.py`、`strings.STATE_TEXT` 皆引用。緩解：以全域搜尋逐處更新，並由單元測試守門。
5. **暫停 UI 與引擎同步**：暫停瞬間需即時顯示「已暫停」。緩解：`worker.pause()` 主動發一次 SUSPENDED 快照，不等下一輪迴圈。

---

## 10. 待確認事項

以下為實作時若遇邊界需回頭確認者（目前依 proposal 假設處理，不阻塞撰寫）：

1. 預覽渲染目標 FPS（暫定 ~30fps / 33ms）是否需可設定？目前**寫死、不開設定**。
2. `RESTING` 期間 StatusStrip 顯示倒數（FIXED）或已休息時間（PRESENCE）——目前依模式切換顯示；是否需統一格式待實作微調。
3. `floating.py` / `toast.py` 是否同步套用「開始休息／歡迎回來」新流程——本設計聚焦 `popup`；其餘提醒方式維持現狀，列為後續。
4. 工作中長時間離座（AWAY→reset）是否計入一次休息紀錄——沿用既有 REST_ENDED 記錄行為，不新增歡迎回來彈窗。
