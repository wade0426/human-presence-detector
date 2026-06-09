# 人體辨識休息提醒系統 — 詳細設計文檔 (Detailed Design)

| 項目 | 內容 |
|---|---|
| 對應需求 | `docs/proposal.md` (v1.0 MVP) |
| 版本 | v1.0 |
| 日期 | 2026-06-09 |
| 文檔性質 | 設計文檔(介面簽章 + 核心演算法虛擬碼 + 測試要點),非最終程式碼 |

---

## 1. 設計目標與原則

1. **核心邏輯與 GUI 解耦**:在場判定、計時狀態機等核心邏輯寫成**純 Python**,不依賴 PySide6;時間、輸入皆以參數注入。核心不需開視窗即可單元測試。
2. **單一背景執行緒 + Qt signal**:一條背景執行緒跑「擷取→偵測→判定→計時」迴圈,結果以 Qt signal 丟回 UI 執行緒。
3. **模塊單一職責、可獨立測試**:模塊間以**第 4 節的共用資料契約**溝通,彼此不直接相依實作細節。
4. **相依方向單向**:`UI → Worker → Core`。Core(純邏輯)不反向相依 Worker / UI。

### 1.1 分層

| 層 | 模塊 | 是否依賴 Qt | 測試方式 |
|---|---|---|---|
| **核心純邏輯** | `presence`、`timer_engine`、`config`、`types` | ❌ | 純單元測試(無 I/O、無 mock) |
| **I/O 介面卡** | `capture/video_source`、`detection/detector`、`logging_store` | ❌ | mock / 暫存 DB / 整合測試 |
| **Qt 介面卡** | `app/worker` | ✅(signal) | pytest-qt 煙霧測試 |
| **Qt UI** | `ui/*`、`reminder/*` | ✅ | pytest-qt / 手動 |
| **組裝** | `main` | ✅ | 手動 |

---

## 2. 模塊相依圖

```
                 ┌──────────────────────────── main.py(組裝) ───────────────────────────┐
                 │                                                                       │
                 ▼                                                                       ▼
   ┌─────────────────────────┐  signals   ┌───────────────────────────────────────────────┐
   │   app/worker.py         │──────────▶ │ ui/main_window · ui/settings · ui/tray          │
   │ (QObject,背景執行緒)    │            │ reminder/{popup,toast,floating}                 │
   └───────────┬─────────────┘            └───────────────────────────────────────────────┘
               │ 呼叫(純 Python,可獨立測)
   ┌───────────┼───────────────┬───────────────┬───────────────┬─────────────────┐
   ▼           ▼               ▼               ▼               ▼                 ▼
capture/     detection/     presence.py    timer_engine.py  logging_store.py   config.py
video_source detector       (純邏輯⭐)      (純邏輯⭐)        (SQLite)          (dataclass)
   └───────────┴───────────────┴───────────────┴───────────────┴─────────────────┘
                                   全部使用 ▶  types.py(共用資料契約)
```

**重點**:`presence`、`timer_engine`、`config`、`types` 完全不 import PySide6 / worker / ui,因此可在無 GUI 環境下被 pytest 直接測試。

---

## 3. 建議檔案結構

```
src/
├─ types.py                共用資料契約(dataclass / enum)
├─ config.py               設定載入 / 驗證 / 儲存
├─ capture/
│  └─ video_source.py      VideoSource 抽象 + RTSP / Webcam + 重連包裝 + 工廠
├─ detection/
│  └─ detector.py          PersonDetector(YOLOv8 封裝)
├─ presence.py             PresenceEvaluator(ROI + 大小 + 去抖動)⭐
├─ timer_engine.py         TimerEngine(工作/休息狀態機)⭐
├─ logging_store.py        SessionStore(SQLite 寫入)
├─ app/
│  └─ worker.py            DetectionWorker(背景執行緒,發 Qt signal)
├─ reminder/
│  ├─ base.py              Reminder 介面 + ReminderContext
│  ├─ popup.py             PopupReminder(圖片/影片 + 音效)
│  ├─ toast.py             ToastReminder(系統通知)
│  ├─ floating.py          FloatingReminder(置頂倒數)
│  └─ factory.py           create_reminder(cfg)
├─ ui/
│  ├─ main_window.py       MainWindow(即時預覽 + 偵測框 + ROI + 計時)
│  ├─ settings.py          SettingsDialog
│  └─ tray.py              TrayIcon
└─ main.py                 進入點:組裝 + 啟動 Qt 事件迴圈

tests/
├─ test_config.py          test_presence.py        test_timer_engine.py
├─ test_video_source.py    test_detector.py        test_logging_store.py
└─ test_worker.py(pytest-qt)
```

---

## 4. 共用資料契約 `types.py`

所有跨模塊傳遞的資料都定義在此,作為模塊間「介面」的具體型別。全部為純 Python。

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import numpy as np  # 僅型別標註用途

# ---- 幾何 / 偵測 ----
@dataclass(frozen=True)
class BBox:
    """正規化座標(0~1),原點左上。"""
    x: float
    y: float
    w: float
    h: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)

@dataclass(frozen=True)
class Detection:
    bbox: BBox            # 正規化
    confidence: float

@dataclass(frozen=True)
class Frame:
    image: np.ndarray     # BGR
    width: int
    height: int
    timestamp: float      # 取得時間(秒)

# ---- 計時狀態機 ----
class TimerState(Enum):
    IDLE = "idle"
    WORKING = "working"
    PAUSED = "paused"
    REMINDING = "reminding"

class ResetMode(Enum):
    DETECTION = "detection"   # 模式1:離開達 R 才重置
    DISMISS = "dismiss"       # 模式2:點掉即重置
    SNOOZE = "snooze"         # 模式3:貪睡,離開達 R 才真正重置

class TimerEventType(Enum):
    WORK_STARTED = "work_started"
    WORK_ENDED = "work_ended"          # 附 duration_sec, ended_by
    REST_ENDED = "rest_ended"          # 附 duration_sec
    REMINDER_TRIGGERED = "reminder_triggered"
    REMINDER_REPEATED = "reminder_repeated"

@dataclass(frozen=True)
class TimerEvent:
    type: TimerEventType
    at: float
    duration_sec: float = 0.0
    ended_by: str = ""     # 'reset' | 'rest_done' | 'dismiss'

@dataclass(frozen=True)
class TimerSnapshot:
    """供 UI 顯示用的當前快照。"""
    state: TimerState
    work_elapsed_sec: float
    away_elapsed_sec: float
    remaining_to_reminder_sec: float
    reminder_active: bool

# ---- 提醒 ----
@dataclass(frozen=True)
class ReminderContext:
    work_minutes: int
    media_path: str
    media_type: str        # 'image' | 'video'
    sound_path: str
```

**測試要點**:`BBox.center` 計算正確;dataclass 為 `frozen`(不可變,方便比較與測試)。

---

## 5. 模塊詳細設計

### 5.1 `config.py` — 設定載入 / 驗證 / 儲存(純邏輯)

**職責**:把 `config.yaml` 載入為**具型別的 dataclass**,做範圍/格式驗證,並可寫回。對外提供不可變的 `AppConfig`。

**對外介面**

```python
from dataclasses import dataclass
from src.types import BBox, ResetMode

@dataclass
class SourceConfig:
    type: str = "rtsp"               # 'rtsp' | 'webcam'
    rtsp_url: str = ""
    webcam_index: int = 0
    reconnect_interval_sec: float = 5.0

@dataclass
class DetectionConfig:
    model_path: str = "data/model/yolov8n.pt"
    interval_sec: float = 1.0
    confidence: float = 0.4
    device: str = "auto"             # 'auto' | 'cpu' | 'cuda'

@dataclass
class PresenceConfig:
    roi: BBox = BBox(0.30, 0.20, 0.40, 0.70)
    min_box_height_ratio: float = 0.25
    debounce_count: int = 3

@dataclass
class TimerConfig:
    work_threshold_min: float = 45.0   # N
    reset_threshold_min: float = 5.0   # M
    required_rest_min: float = 5.0     # R

@dataclass
class PopupConfig:
    media_path: str = "data/assets/rest_placeholder.png"
    media_type: str = "image"          # 'image' | 'video'
    sound_path: str = ""

@dataclass
class FloatingConfig:
    position: str = "top-right"

@dataclass
class ReminderConfig:
    method: str = "popup"              # 'popup' | 'toast' | 'floating'
    reset_mode: ResetMode = ResetMode.DETECTION
    repeat_interval_min: float = 2.0
    snooze_min: float = 5.0
    popup: PopupConfig = PopupConfig()
    floating: FloatingConfig = FloatingConfig()

@dataclass
class LoggingConfig:
    enabled: bool = True
    db_path: str = "data/records.sqlite"

@dataclass
class UIConfig:
    start_minimized: bool = False

@dataclass
class AppConfig:
    source: SourceConfig = SourceConfig()
    detection: DetectionConfig = DetectionConfig()
    presence: PresenceConfig = PresenceConfig()
    timer: TimerConfig = TimerConfig()
    reminder: ReminderConfig = ReminderConfig()
    logging: LoggingConfig = LoggingConfig()
    ui: UIConfig = UIConfig()

class ConfigError(Exception): ...

def load_config(path: str) -> AppConfig: ...
def save_config(config: AppConfig, path: str) -> None: ...
def validate(raw: dict) -> list[str]: ...   # 回傳錯誤訊息清單,空清單代表通過
```

**核心演算法(虛擬碼)**

```
load_config(path):
    if not exists(path): return AppConfig()            # 全預設
    raw = yaml.safe_load(path)
    errors = validate(raw)
    if errors: raise ConfigError(errors)
    return _from_dict(raw)        # 缺漏欄位以 dataclass 預設補齊;roi list→BBox;reset_mode str→ResetMode

validate(raw):
    errors = []
    檢查 source.type ∈ {rtsp, webcam};rtsp 時 rtsp_url 非空且像 URL
    檢查 0 < confidence ≤ 1;0 < min_box_height_ratio ≤ 1;debounce_count ≥ 1
    檢查 work/reset/required 皆 > 0
    檢查 reminder.method ∈ {popup,toast,floating};reset_mode ∈ ResetMode
    檢查 media_type ∈ {image, video}
    return errors
```

**相依**:`pyyaml`、`types`。
**測試要點**:
- 不存在的路徑 → 全預設 `AppConfig`。
- 缺漏欄位 → 以預設補齊。
- 非法值(confidence=2、type='x'、rtsp 無 url)→ `validate` 回傳對應錯誤。
- `save_config` 後 `load_config` 還原一致(round-trip);`roi`↔`BBox`、`ResetMode`↔字串轉換正確。

---

### 5.2 `capture/video_source.py` — 影像來源(I/O 介面卡)

**職責**:把「RTSP / Webcam」抽象成統一介面,並提供**斷線自動重連**包裝。上層不需知道來源型別。

**對外介面**

```python
from typing import Protocol, Optional, Callable
from src.types import Frame
from src.config import SourceConfig

class VideoSource(Protocol):
    def open(self) -> None: ...
    def read(self) -> Optional[Frame]: ...   # 失敗回 None
    def release(self) -> None: ...
    @property
    def is_opened(self) -> bool: ...

class WebcamSource:
    def __init__(self, index: int): ...

class RTSPSource:
    def __init__(self, url: str): ...

class ReconnectingSource:
    """包裝任一 VideoSource;read 失敗時依間隔自動重開。"""
    def __init__(self, inner: VideoSource, reconnect_interval_sec: float,
                 clock: Callable[[], float] = time.monotonic): ...
    def read(self) -> Optional[Frame]: ...   # 重連中回 None

def create_source(cfg: SourceConfig,
                  clock: Callable[[], float] = time.monotonic) -> VideoSource: ...
```

**核心演算法(虛擬碼)**

```
WebcamSource/RTSPSource.read():
    ok, img = self._cap.read()
    if not ok: return None
    return Frame(img, width, height, clock())

ReconnectingSource.read():
    if not inner.is_opened:
        if clock() - self._last_attempt < interval: return None   # 還沒到重試時間
        self._last_attempt = clock()
        try: inner.open()
        except: return None
    frame = inner.read()
    if frame is None:
        inner.release()            # 標記為斷線,下次觸發重連
    return frame

create_source(cfg):
    inner = WebcamSource(cfg.webcam_index) if cfg.type=='webcam' else RTSPSource(cfg.rtsp_url)
    return ReconnectingSource(inner, cfg.reconnect_interval_sec, clock)
```

**相依**:`opencv-python`(`cv2.VideoCapture`,RTSP 用 `cv2.CAP_FFMPEG`)、`types`、`config`。
**測試要點**(用**假 inner source**,不碰真實攝影機):
- `ReconnectingSource`:inner 未開 → 第一次 read 觸發 open;open 失敗 → 回 None 且不超過間隔頻率重試;read 回 None → 呼叫 release(下次重連)。
- `create_source`:`type='webcam'` 建 `WebcamSource`、`type='rtsp'` 建 `RTSPSource`,外層皆包 `ReconnectingSource`。
- (整合,選配)真實 webcam 能取得一張 `Frame`。

---

### 5.3 `detection/detector.py` — 人體偵測(I/O 介面卡)

**職責**:封裝 YOLOv8,輸入 `Frame`,輸出**正規化**的 person `Detection` 清單。

**對外介面**

```python
from src.types import Frame, Detection

class PersonDetector:
    def __init__(self, model_path: str, confidence: float, device: str = "auto"): ...
    def detect(self, frame: Frame) -> list[Detection]: ...
    # 測試縫(seam):實際推論集中於此,單元測試時 mock 它
    def _infer(self, image) -> list[tuple[float, float, float, float, float]]:
        """回傳 [(x1,y1,x2,y2,conf), ...](像素座標,已過濾為 person)。"""
```

**核心演算法(虛擬碼)**

```
__init__:
    self.device = _resolve_device(device)      # auto→ cuda if torch.cuda.is_available() else cpu
    self.model = None                           # 延遲載入

detect(frame):
    if self.model is None: self.model = YOLO(model_path); self.model.to(self.device)
    raw = self._infer(frame.image)              # 內部呼叫 model(image, classes=[0], conf=confidence, verbose=False)
    dets = []
    for (x1,y1,x2,y2,conf) in raw:
        bbox = BBox(x1/frame.width, y1/frame.height,
                    (x2-x1)/frame.width, (y2-y1)/frame.height)
        dets.append(Detection(bbox, conf))
    return dets
```

**相依**:`ultralytics`(YOLOv8)、`torch`(裝置判斷)、`types`。
**測試要點**:
- **mock `_infer`** 回固定像素框 → 驗證 `detect` 正規化計算正確(框轉 0~1)、信心保留。
- `_resolve_device`:`auto` 在無 CUDA 時得 `cpu`。
- (整合,選配)用 `yolov8n.pt` 對一張含人照片實跑,至少一個 person。

---

### 5.4 `presence.py` — 在場判定(純邏輯 ⭐)

**職責**:依 ROI + 大小門檻判斷「是否在場」,並做去抖動,輸出穩定的布林狀態。無 I/O、無 Qt。

**對外介面**

```python
from src.types import Detection, BBox

class PresenceEvaluator:
    def __init__(self, roi: BBox, min_box_height_ratio: float, debounce_count: int): ...
    def update(self, detections: list[Detection]) -> bool:
        """輸入當下偵測,回傳『去抖動後』的在場布林。"""
    def set_roi(self, roi: BBox) -> None: ...     # UI 改 ROI 時即時套用
    @property
    def stable_present(self) -> bool: ...
```

**核心演算法(虛擬碼)**

```
_qualifies(d):
    cx, cy = d.bbox.center
    in_roi = roi.x <= cx <= roi.x+roi.w and roi.y <= cy <= roi.y+roi.h
    big_enough = d.bbox.h >= min_box_height_ratio
    return in_roi and big_enough

update(detections):
    raw = any(_qualifies(d) for d in detections)     # 多人時任一人滿足即在場
    if raw == self.stable:
        self._pending = None; self._count = 0
    else:
        if raw == self._pending: self._count += 1
        else: self._pending = raw; self._count = 1
        if self._count >= debounce_count:
            self.stable = raw; self._pending = None; self._count = 0
    return self.stable
```

**相依**:`types`。
**測試要點**(純資料、最完整):
- 連續 < `debounce_count` 次的相反訊號**不**翻轉狀態;達次數才翻轉。
- ROI 邊界:中心剛好在框內/框外。
- 大小門檻:框高 = / < / > `min_box_height_ratio`。
- 空 `detections` → 視為離開(需經去抖動)。
- 多偵測:其中一個合格即在場。
- `set_roi` 後立即以新 ROI 判定。

---

### 5.5 `timer_engine.py` — 工作/休息狀態機(純邏輯 ⭐⭐ 系統心臟)

**職責**:依「在場/離開」與**注入的時間**推進狀態機,維護工作計時,並回傳事件(觸發提醒、結束工作段、結束休息段)。完全純函數式驅動,可注入假時鐘做完整測試。

**對外介面**

```python
from typing import Callable
from src.types import TimerState, TimerEvent, TimerSnapshot, ResetMode

class TimerEngine:
    def __init__(self,
                 work_threshold_sec: float,     # N(秒;由 TimerConfig.min*60)
                 reset_threshold_sec: float,     # M
                 required_rest_sec: float,       # R
                 reset_mode: ResetMode,
                 repeat_interval_sec: float,     # 模式1/3 重複提醒間隔
                 snooze_sec: float): ...
    def update(self, present: bool, now: float) -> list[TimerEvent]:
        """每個偵測週期呼叫一次;回傳本次發生的事件。"""
    def on_reminder_dismissed(self, now: float) -> list[TimerEvent]:
        """UI 上使用者點掉提醒時呼叫(模式2/3 有作用)。"""
    def snapshot(self, now: float) -> TimerSnapshot: ...
    @property
    def state(self) -> TimerState: ...
```

**內部狀態**:`state, work_elapsed, last_t, away_since, rest_start_t, work_start_t, reminder_last_t, snooze_until`。

**核心演算法(虛擬碼)** — 對應 proposal §6 狀態轉移表

```
update(present, now):
    events = []
    dt = (now - last_t) if last_t is not None else 0
    last_t = now

    if state == IDLE:
        if present:
            if rest_start_t is not None:                       # 結束上一段休息
                events += REST_ENDED(now - rest_start_t); rest_start_t = None
            state = WORKING; work_elapsed = 0; work_start_t = now
            events += WORK_STARTED

    elif state == WORKING:
        if present:
            work_elapsed += dt
            if work_elapsed >= N:
                state = REMINDING; reminder_last_t = now; away_since = None; snooze_until = None
                events += REMINDER_TRIGGERED
        else:
            state = PAUSED; away_since = now                   # 凍結 work_elapsed

    elif state == PAUSED:
        if present:                                            # 回來(away < M,否則早已重置)
            state = WORKING; away_since = None                 # 不補計離開時間
        else:
            if (now - away_since) >= M:                        # 視為已休息→重置
                events += WORK_ENDED(work_elapsed, ended_by='reset')
                rest_start_t = away_since                      # 休息自離開起算
                state = IDLE; work_elapsed = 0; away_since = None

    elif state == REMINDING:
        if present:
            if reset_mode == DISMISS:
                pass                                           # 等使用者點掉(見 on_reminder_dismissed)
            elif reset_mode == SNOOZE and snooze_until and now < snooze_until:
                pass                                           # 貪睡中,不重複提醒
            else:                                              # DETECTION 或貪睡到期
                if (now - reminder_last_t) >= repeat_interval:
                    reminder_last_t = now; events += REMINDER_REPEATED
            work_elapsed += dt                                 # 持續累計(顯示加班)
            away_since = None
        else:                                                  # 離開→可能完成休息
            if away_since is None: away_since = now
            if (now - away_since) >= R:                        # 休息足夠→重置
                events += WORK_ENDED(work_elapsed, ended_by='rest_done')
                rest_start_t = away_since
                state = IDLE; work_elapsed = 0; away_since = None
                reminder_last_t = None; snooze_until = None
    return events

on_reminder_dismissed(now):
    if state != REMINDING: return []
    if reset_mode == DISMISS:
        ev = [WORK_ENDED(work_elapsed, ended_by='dismiss')]
        state = WORKING; work_elapsed = 0; work_start_t = now
        return ev + [WORK_STARTED]
    elif reset_mode == SNOOZE:
        snooze_until = now + snooze_sec; return []             # 暫時隱藏,離開達 R 仍會重置
    else: # DETECTION
        reminder_last_t = now; return []                       # 只是關掉這次,之後仍依間隔重複

snapshot(now):
    remaining = max(0, N - work_elapsed) if state in (WORKING,) else 0
    away = (now - away_since) if away_since else 0
    return TimerSnapshot(state, work_elapsed, away, remaining, reminder_active=(state==REMINDING))
```

**相依**:`types`。
**測試要點**(注入小秒數假時鐘,情境最完整 —— 本模塊測試覆蓋率最高):
1. 連續在場累計達 N → 收到 `REMINDER_TRIGGERED`。
2. 短暫離開(< M)再回來 → 狀態回 `WORKING`,`work_elapsed` **不含**離開時間(暫停保留)。
3. 離開達 M → `WORK_ENDED(ended_by='reset')`,計時歸零;再回來 → `REST_ENDED` 且 `WORK_STARTED`。
4. 模式1:提醒後持續在場 → 每 `repeat_interval` 收到一次 `REMINDER_REPEATED`;離開達 R → `WORK_ENDED(ended_by='rest_done')`。
5. 模式2:`on_reminder_dismissed` → `WORK_ENDED(ended_by='dismiss')` + `WORK_STARTED`,立即新一輪。
6. 模式3:`on_reminder_dismissed` → 貪睡期間不再提醒;貪睡到期仍在場 → 再次 `REMINDER_REPEATED`;離開達 R → 真正重置。
7. `snapshot`:各狀態下 `remaining_to_reminder_sec`、`reminder_active` 正確。

---

### 5.6 `logging_store.py` — 記錄寫入(I/O 介面卡)

**職責**:把工作/休息段寫入 SQLite。MVP 只負責寫入。

> **執行緒注意**:SQLite 連線具執行緒親和性。`SessionStore` 由**背景 worker 執行緒**建立並使用,不跨執行緒共享連線。

**對外介面**

```python
from datetime import datetime

class SessionStore:
    def __init__(self, db_path: str): ...
    def init_schema(self) -> None: ...
    def log_session(self, type: str, start_ts: datetime, end_ts: datetime,
                    duration_sec: int, ended_by: str) -> int: ...   # 回 row id
    def close(self) -> None: ...
```

**Schema**(同 proposal §9.2)

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,            -- 'work' | 'rest'
    start_ts TEXT NOT NULL,        -- ISO8601
    end_ts TEXT,
    duration_sec INTEGER,
    ended_by TEXT
);
```

**相依**:`sqlite3`(標準庫)。
**測試要點**:用 `db_path=':memory:'` 或 `tmp_path`;`init_schema` 可重複呼叫不報錯;`log_session` 寫入後查得回相同欄位;`type` 接受 'work'/'rest'。

---

### 5.7 `app/worker.py` — 背景工作執行緒(Qt 介面卡)

**職責**:組裝核心物件,在**單一背景執行緒**跑主迴圈;把畫面、在場、計時、提醒、連線狀態以 **Qt signal** 丟回 UI 執行緒;把計時事件轉成記錄寫入。本身為薄接線,重邏輯都在已測過的核心。

**對外介面**

```python
from PySide6.QtCore import QObject, Signal
from src.types import Frame, TimerSnapshot, ReminderContext

class DetectionWorker(QObject):
    frame_ready = Signal(object)          # Frame(供預覽,可節流)
    presence_changed = Signal(bool)
    timer_updated = Signal(object)        # TimerSnapshot
    reminder_show = Signal(object)        # ReminderContext
    reminder_repeat = Signal(object)      # ReminderContext
    connection_status = Signal(str)       # 'connected' | 'reconnecting'

    def __init__(self, source, detector, presence_evaluator, timer_engine,
                 store, detection_interval_sec: float, reminder_context: ReminderContext,
                 clock=time.monotonic): ...
    def run(self) -> None: ...            # 迴圈,放進 QThread 執行
    def stop(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def dismiss_reminder(self) -> None: ...   # 轉呼叫 timer_engine.on_reminder_dismissed
    def set_roi(self, roi) -> None: ...       # 轉呼叫 presence_evaluator.set_roi
```

**核心演算法(虛擬碼)**

```
run():
    store.init_schema()
    while not self._stop:
        if self._paused: sleep(0.1); continue
        t0 = clock()
        frame = source.read()
        if frame is None:
            emit connection_status('reconnecting'); sleep(0.2); continue
        emit connection_status('connected')
        emit frame_ready(frame)
        dets = detector.detect(frame)
        present = presence_evaluator.update(dets)
        emit presence_changed(present)
        for ev in timer_engine.update(present, clock()):
            _dispatch(ev)                         # 見下
        emit timer_updated(timer_engine.snapshot(clock()))
        sleep(max(0, detection_interval - (clock()-t0)))   # 控制偵測頻率

# worker 維護工作段起始「牆鐘時間」;timer_engine 用單調時鐘,DB 需要 datetime
_work_start_dt: datetime | None = None

_dispatch(ev):
    now_dt = datetime.now()
    if ev.type == REMINDER_TRIGGERED: emit reminder_show(reminder_context)
    elif ev.type == REMINDER_REPEATED: emit reminder_repeat(reminder_context)
    elif ev.type == WORK_STARTED: self._work_start_dt = now_dt
    elif ev.type == WORK_ENDED:
        store.log_session('work', self._work_start_dt or now_dt, now_dt,
                          int(ev.duration_sec), ev.ended_by)
    elif ev.type == REST_ENDED:                     # 休息長度由引擎算好
        store.log_session('rest', now_dt - timedelta(seconds=ev.duration_sec), now_dt,
                          int(ev.duration_sec), '')

dismiss_reminder():
    for ev in timer_engine.on_reminder_dismissed(clock()): _dispatch(ev)
```

**相依**:`PySide6.QtCore`、所有核心模塊。
**測試要點**(pytest-qt,薄接線煙霧測試):
- 餵入假 `source`(回固定 `Frame`)、假 `detector`(回固定 `Detection`)→ 跑數圈後有發出 `frame_ready` / `presence_changed` / `timer_updated`。
- `source.read()` 回 None → 發出 `connection_status('reconnecting')`,迴圈不崩潰。
- 觸發提醒情境 → 發出 `reminder_show`。

---

### 5.8 `reminder/` — 提醒元件(Qt UI)

**職責**:三種提醒方式,共用介面,可由工廠依設定建立。

**對外介面**

```python
# base.py
from typing import Protocol
from PySide6.QtCore import Signal
from src.types import ReminderContext

class Reminder(Protocol):
    dismissed: Signal                 # 使用者點掉時發出
    def show(self, ctx: ReminderContext) -> None: ...
    def hide(self) -> None: ...

# popup.py   PopupReminder(QDialog)：依 media_type 用 QLabel(圖) 或 QMediaPlayer+QVideoWidget(影片)
#            播放 sound_path(QSoundEffect)；按「我要休息」→ emit dismissed
# toast.py   ToastReminder：QSystemTrayIcon.showMessage（或 plyer 備援）
# floating.py FloatingReminder(QWidget, FramelessWindowHint|WindowStaysOnTopHint)：
#            常駐置頂倒數；show 時閃爍/變色
# factory.py
def create_reminder(cfg: "ReminderConfig", tray=None) -> Reminder: ...   # 依 cfg.method 回對應實作
```

**相依**:`PySide6`(Widgets / Multimedia / Core)、`types`、`config`。
**測試要點**:`create_reminder` 依 `method` 回正確型別;PopupReminder 在 `media_type='image'` / `'video'` 走不同顯示路徑(pytest-qt 煙霧);按鈕點擊發出 `dismissed`。

> **實作期資產**:於 `data/assets/rest_placeholder.png` 建立預設假圖(proposal §12 風險已註明 `/data` 被 `.gitignore` 忽略)。

---

### 5.9 `ui/` — 主視窗 / 設定 / 系統匣(Qt UI)

**`MainWindow(QMainWindow)`**
- 顯示即時影像預覽(`QLabel` 繪製 `Frame`),疊加**偵測框、ROI 框線、狀態與計時**。
- 在預覽上**拖拉框選 ROI** → 轉正規化 `BBox` → `worker.set_roi()` 並寫回設定。
- 可最小化至系統匣。
- Slots:`on_frame_ready(Frame)`、`on_presence_changed(bool)`、`on_timer_updated(TimerSnapshot)`、`on_connection_status(str)`。

```python
class MainWindow(QMainWindow):
    roi_changed = Signal(object)      # BBox
    def __init__(self, config: AppConfig): ...
    def on_frame_ready(self, frame): ...
    def on_timer_updated(self, snapshot): ...
```

**`SettingsDialog(QDialog)`**
- 表單涵蓋所有設定欄位;載入自 `AppConfig`,儲存呼叫 `config.save_config` 並套用到 worker。
- `accepted` 時發出 `config_changed(AppConfig)`。

**`TrayIcon(QSystemTrayIcon)`**
- 選單:開啟主視窗 / 暫停·繼續 / 結束。
- 圖示或提示反映目前狀態(工作中 / 離開 / 提醒中)。

**相依**:`PySide6.QtWidgets/QtGui/QtCore`、`config`、`types`。
**測試要點**:以 pytest-qt 做煙霧測試(可建立、ROI 拖拉換算正規化座標正確);其餘以手動驗收為主。

---

### 5.10 `main.py` — 進入點(組裝)

**職責**:把設定→核心→worker→UI 接線,啟動 Qt 事件迴圈。

**核心流程(虛擬碼)**

```
main():
    app = QApplication()
    cfg = load_config("config.yaml")

    source   = create_source(cfg.source)
    detector = PersonDetector(cfg.detection.model_path, cfg.detection.confidence, cfg.detection.device)
    presence = PresenceEvaluator(cfg.presence.roi, cfg.presence.min_box_height_ratio, cfg.presence.debounce_count)
    timer    = TimerEngine(cfg.timer.work_threshold_min*60, cfg.timer.reset_threshold_min*60,
                           cfg.timer.required_rest_min*60, cfg.reminder.reset_mode,
                           cfg.reminder.repeat_interval_min*60, cfg.reminder.snooze_min*60)
    store    = SessionStore(cfg.logging.db_path)
    ctx      = ReminderContext(int(cfg.timer.work_threshold_min), cfg.reminder.popup.media_path,
                               cfg.reminder.popup.media_type, cfg.reminder.popup.sound_path)

    worker = DetectionWorker(source, detector, presence, timer, store,
                             cfg.detection.interval_sec, ctx)
    thread = QThread(); worker.moveToThread(thread); thread.started.connect(worker.run)

    window   = MainWindow(cfg)
    tray     = TrayIcon(...)
    reminder = create_reminder(cfg.reminder, tray)

    # 接線(signal → slot)
    worker.frame_ready.connect(window.on_frame_ready)
    worker.presence_changed.connect(window.on_presence_changed)
    worker.timer_updated.connect(window.on_timer_updated)
    worker.connection_status.connect(window.on_connection_status)
    worker.reminder_show.connect(reminder.show)
    worker.reminder_repeat.connect(reminder.show)
    reminder.dismissed.connect(worker.dismiss_reminder)
    window.roi_changed.connect(worker.set_roi)

    thread.start()
    window.show() if not cfg.ui.start_minimized else tray.show()
    app.exec()
```

**測試要點**:以手動啟動驗收(屬組裝層,邏輯已於各模塊測過)。

---

## 6. 主要時序

### 6.1 偵測主迴圈(每個偵測週期,預設 1 秒)

```
背景執行緒(worker.run)                         UI 執行緒
   │ source.read() → Frame                        │
   │ detector.detect(Frame) → [Detection]         │
   │ presence.update(...) → present:bool          │
   │ timer.update(present, now) → [TimerEvent]    │
   │   ├─ REMINDER_TRIGGERED ──signal──▶ reminder.show(ctx)
   │   ├─ WORK_ENDED ─────────────────▶ store.log_session('work', ...)
   │   └─ REST_ENDED ─────────────────▶ store.log_session('rest', ...)
   │ emit frame_ready/presence/timer ──signal──▶ MainWindow 更新預覽+計時
   │ sleep 至滿足偵測間隔                         │
```

### 6.2 提醒與重置(模式1 預設)

```
work_elapsed 達 N → REMINDER_TRIGGERED → 彈出提醒
   ├─ 使用者仍在場：每 repeat_interval 再提醒(REMINDER_REPEATED)
   └─ 使用者離開達 R → WORK_ENDED(rest_done) → 歸零 → 回 IDLE
        └─ 再回座位 → REST_ENDED + WORK_STARTED → 新一輪
```

---

## 7. 測試策略總表

| 模塊 | 類型 | 框架 / 手法 | 重點 |
|---|---|---|---|
| `types` | 純 | pytest | dataclass 計算(center)、不可變 |
| `config` | 純 | pytest | 驗證、預設補齊、round-trip |
| `presence` ⭐ | 純 | pytest | ROI/大小/去抖動,完整情境 |
| `timer_engine` ⭐⭐ | 純 | pytest + 假時鐘 | 全狀態轉移 + 三種重置模式(覆蓋率最高) |
| `video_source` | I/O | pytest + 假 inner | 重連邏輯、工廠選型 |
| `detector` | I/O | pytest + mock `_infer` | 正規化、信心過濾、裝置判斷 |
| `logging_store` | I/O | pytest + `:memory:` | schema、寫入查回 |
| `app/worker` | Qt | pytest-qt + 假核心 | 有發出對應 signal、None 不崩潰 |
| `reminder/*` | Qt | pytest-qt | 工廠選型、dismiss 訊號 |
| `ui/*` | Qt | pytest-qt / 手動 | 建立、ROI 換算;其餘手動 |
| `main` | 組裝 | 手動 | 端到端啟動 |

**框架**:`pytest`(全模塊)、`pytest-qt`(Qt 層)。**原則**:重邏輯集中在純模塊用純單元測試;Qt 層僅薄接線做煙霧測試。

---

## 8. 需求追溯(proposal FR → 模塊)

| 需求 | 對應模塊 |
|---|---|
| FR-1 影像來源(RTSP/webcam/重連) | `capture/video_source` |
| FR-2 人體偵測(YOLOv8/間隔/信心/裝置/執行緒) | `detection/detector` + `app/worker` |
| FR-3 在場判定(ROI+大小+去抖動+多人) | `presence` |
| FR-4 計時狀態機(N/M/R) | `timer_engine` |
| FR-5 提醒(三種/圖片影片/音效) | `reminder/*` + `app/worker` |
| FR-6 提醒後重置(三模式) | `timer_engine`(模式邏輯)+ `reminder`(dismiss) |
| FR-7 主視窗(預覽/疊加/框 ROI) | `ui/main_window` |
| FR-8 系統匣 | `ui/tray` |
| FR-9 設定管理(UI+持久化+驗證) | `config` + `ui/settings` |
| FR-10 記錄寫檔(SQLite) | `logging_store` + `app/worker` |
| 非功能:RTSP 重連 | `capture/video_source` |
| 非功能:偵測不卡 UI | `app/worker`(背景執行緒) |

---

## 9. 待確認 / 風險

| 項目 | 說明 |
|---|---|
| `pytest-qt` 相依 | Qt 層測試需安裝 `pytest-qt`;若不想引入,Qt 層改為純手動驗收。 |
| SQLite 執行緒親和性 | `SessionStore` 僅在 worker 執行緒建立/使用(已於 §5.6 註明)。 |
| 影片提醒編解碼 | `PopupReminder` 播影片依賴系統 Qt Multimedia 後端,需於實作期確認 mp4/h264 可播。 |
| `frame_ready` 頻率 | 預覽若吃資源可在 worker 端節流(例如每隔數次才 emit)。 |
| GPU 環境 | `device='cuda'` 需另裝對應 PyTorch CUDA 版本,否則自動退回 CPU。 |
```