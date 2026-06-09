# 人體辨識休息提醒系統 — 詳細設計文檔

## 1. 文件資訊

| 項目 | 內容 |
|---|---|
| 文件名稱 | 設定頁面與 UI/UX 強化 詳細設計（detailed design） |
| 上游文件 | `docs/proposal.md`（需求文檔）、`docs/apple_ui_ux_development_guide.md`（設計原則） |
| 適用專案 | human-presence-detector（PySide6 / Windows 桌面） |
| 文檔深度 | 模塊級介面細節（職責 / 公開介面簽章 / 相依 / 資料結構 / 行為時序 / 獨立測試策略） |
| 狀態 | 待審閱 / 待實作 |

---

## 2. 目的與範圍

本文件把 `proposal.md` 的六大範圍（設定頁面、主視窗、系統匣與提醒、執行品質、主題、無障礙）拆解為**相互獨立、可獨立測試**的軟體模塊，給出每個模塊的公開介面、相依、資料結構、行為時序與測試策略。

**範圍界定**

- 本文件只詳述「本次會新增或修改」的模塊。
- 未變更的核心模塊（`detection/detector.py`、`presence.py`、`timer_engine.py`、`capture/video_source.py`）僅作為**穩定相依**被引用，不在此重新設計，且**不更動其行為**（呼應 proposal 非目標）。

---

## 3. 既有架構與可測風格回顧

現有程式碼採乾淨分層，本設計全面沿用：

| 層 | 模塊 | 特性 |
|---|---|---|
| 核心純邏輯 | `types`、`config`、`presence`、`timer_engine` | 無 Qt 相依、純函式 / 純狀態機，易單元測試 |
| I/O 介面卡 | `capture/video_source`、`detection/detector`、`logging_store` | 以 `Protocol` 定義介面、建構式注入相依、`clock` callable 可注入 |
| Qt 接線 | `app/worker`（`DetectionWorker`） | `QObject` + 訊號群，邏輯與 UI 解耦 |
| Qt UI | `reminder/*`、`ui/*` | 以訊號對外溝通；用 `pytest-qt` 測試 |
| 入口 | `main.py` | 只負責組裝與接線 |

**可測風格約定（新模塊一律遵守）**

1. 純資料 / 純邏輯與 Qt 解耦：能用 `pytest` 直接測的就不要綁 `QWidget`。
2. 相依以建構式注入；時間以 `clock: Callable[[], float]` 或顯式 `now` 參數注入。
3. UI 元件對外只暴露**訊號 + 少量 setter slot**，內部狀態不外洩。
4. 每個模塊都要能回答：做什麼、怎麼用、相依誰。

---

## 4. 既有缺陷修正清單（本次一併處理）

| 編號 | 缺陷 | 位置 | 修正模塊 |
|---|---|---|---|
| D1 | `toggle_action` 只接 `worker.pause`，暫停後無法繼續 | `main.py:97` | M11 / M13 |
| D2 | `FloatingReminder` 宣告 `dismissed` 卻從不發射 | `reminder/floating.py` | M12 |
| D3 | `worker.failed` 直接 `app.quit`，一拋例外即關閉程式 | `main.py:90` | M7 / M13 |
| D4 | ROI 變更只 `emit`、未寫回 `config.yaml` | `main_window.py:_on_roi_selected` | M10 |
| D5 | `SettingsDialog.config_changed` 為未接線的死訊號 | `settings.py` / `main.py` | M9 / M13 |
| D6 | 設定計時欄位無範圍/步進、上限被預設 99.99 卡住 | `settings.py` | M2 / M9 |
| D7 | 提醒圖片以 `QPixmap(path)` 直載，毀損即 `libpng` 錯誤 | `reminder/popup.py` | M12 |
| D8 | 系統匣 `QIcon()` 為空（`No Icon set`） | `tray.py` | M11 |

---

## 5. 模塊總覽與相依關係

```text
                         main.py (M13, 組裝/接線)
   ┌───────────────┬───────────┬───────────┬──────────────┬───────────────┐
   ▼               ▼           ▼           ▼              ▼               ▼
logging_setup   theme(M8)   DetectionWorker(M7)   MainWindow(M10)   SettingsWindow(M9)   TrayIcon(M11)
   (M5)            │            │  使用            │  使用              │  使用              + reminder factory
                   │            ▼                  ▼                   ▼                   → Popup/Toast/Floating(M12)
                   │   video_source/detector/   connection_state(M4)  settings_schema(M2)        │ 使用
                   │   presence/timer_engine     strings(M3)          config(M1)           media(M12) / strings(M3)
                   │   logging_store(M6)         logging_store(M6,讀)  strings(M3)
                   │
   純模塊(無 Qt)：config(M1)、settings_schema(M2)、strings(M3)、connection_state(M4)、theme tokens(M8 部分)
```

**相依方向原則**：UI 模塊可相依純模塊；純模塊**不得**相依任何 Qt 或 UI 模塊。`settings_schema(M2)` 只相依 `config` 的 dataclass 結構；`connection_state(M4)`、`strings(M3)` 零相依。

**模塊索引**

| # | 模塊 / 檔案 | 動作 | 層 |
|---|---|---|---|
| M1 | `src/config.py` | 修改 | 核心純邏輯 |
| M2 | `src/ui/settings_schema.py` | 新增 | 純資料 |
| M3 | `src/ui/strings.py` | 新增 | 純資料 |
| M4 | `src/app/connection_state.py` | 新增 | 純邏輯 |
| M5 | `src/logging_setup.py` | 新增 | 基礎設施 |
| M6 | `src/logging_store.py` | 修改 | I/O 介面卡 |
| M7 | `src/app/worker.py` | 修改 | Qt 接線 |
| M8 | `src/ui/theme.py` | 新增 | Qt UI（含純決策） |
| M9 | `src/ui/settings.py` | 重構 | Qt UI |
| M10 | `src/ui/main_window.py` + `src/ui/widgets/*` | 重構+新增 | Qt UI |
| M11 | `src/ui/tray.py` | 修改 | Qt UI |
| M12 | `src/reminder/media.py` + `src/reminder/*` | 新增+重構 | Qt UI |
| M13 | `src/main.py` | 修改 | 入口 |
| A1 | 後備圖示 / 預設媒體 | 新增 | 資產 |

---

## 6. 逐模塊詳細設計

### M1 `config.py`：分鐘欄位驗證強化

**職責**　在既有 `validate()` 加入「分鐘欄位 0.1 ~ 9999」的範圍檢查，作為設定持久化與設定頁存檔的唯一真實驗證來源。

**公開介面（變更點）**

```python
# 新增模組常數
MINUTE_MIN: float = 0.1
MINUTE_MAX: float = 9999.0

# validate() 內新增：對下列鍵強制 MINUTE_MIN <= x <= MINUTE_MAX
#   timer.work_threshold_min / timer.reset_threshold_min / timer.required_rest_min
#   reminder.repeat_interval_min / reminder.snooze_min
def validate(raw: dict[str, Any]) -> list[str]: ...   # 簽章不變，錯誤訊息增加
```

- 既有 `timer.*` 的 `> 0` 檢查改為呼叫既有 `_in_range(value, min_value=MINUTE_MIN, max_value=MINUTE_MAX, include_min=True)`。
- 新增 `reminder.repeat_interval_min`、`reminder.snooze_min` 的同範圍檢查（目前完全未驗證）。
- 錯誤字串格式維持 `"<dotted.key> must satisfy 0.1 <= value <= 9999"`，供 M9 對應到欄位。

**相依**　無新增。

**行為時序要點**　`load_config()` 與 M9 存檔前都會呼叫 `validate()`；任一錯誤即 `ConfigError` / 阻擋存檔。

**獨立測試策略**　純函式表驅動：對每個分鐘鍵測 `0.09`（拒）、`0.1`（收）、`9999`（收）、`9999.1`（拒）、非數值（拒）；確認錯誤字串含對應鍵。

---

### M2 `ui/settings_schema.py`：設定欄位中繼資料（新增）

**職責**　以**純資料**集中描述每個設定欄位（標籤、提示、控制項型別、範圍、分類、是否需重啟），讓設定頁完全由資料驅動；並提供以「點路徑」讀寫 `AppConfig` 的工具，避免 UI 散落硬編欄位。

**公開介面**

```python
class WidgetKind(Enum):
    TEXT = "text"; INT = "int"; FLOAT = "float"
    CHOICE = "choice"; PATH = "path"; BOOL = "bool"

@dataclass(frozen=True)
class FieldSpec:
    key: str                      # 點路徑，如 "timer.work_threshold_min"
    label: str                    # 顯示名稱
    hint: str                     # 欄位下方常駐說明（FR-1.3）
    widget: WidgetKind
    category: str                 # 基本/偵測/提醒/紀錄/進階
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    decimals: int | None = None
    choices: tuple[str, ...] | None = None

CATEGORIES: tuple[str, ...] = ("基本", "偵測", "提醒", "紀錄", "進階")
SCHEMA: tuple[FieldSpec, ...]     # 涵蓋 §proposal 9 全部欄位（不含 presence.roi）

def fields_for(category: str) -> tuple[FieldSpec, ...]: ...
def get_value(cfg: AppConfig, key: str) -> Any: ...           # 走點路徑取值
def set_value(cfg: AppConfig, key: str, value: Any) -> AppConfig: ...  # 回傳更新後副本
```

- `set_value` 以 `dataclasses.replace` 逐層重建巢狀 dataclass，回傳**新的** `AppConfig`（不可變風格）。
- `reminder.reset_mode` 以 `choices=("detection","dismiss","snooze")` 表示；存回時由 M9 轉回 `ResetMode`。
- 5 個分鐘欄位於 schema 內固定 `minimum=0.1, maximum=9999, step=0.1, decimals=1`，與 M1 的真實驗證一致（schema 控制 UI 體驗，M1 控制資料正確性，兩者皆需通過）。

**相依**　`src/config.py`（僅 dataclass 結構）、`src/types.py`（`ResetMode` 值）。無 Qt。

**獨立測試策略**

- **完整性**：對預設 `AppConfig()`，`SCHEMA` 內每個 `key` 都能被 `get_value` 解析、且 `set_value` round-trip 不丟值。
- **涵蓋率**：除 `presence.roi` 外，`AppConfig` 全部葉節點都出現在 `SCHEMA`（用反射列舉 dataclass 欄位比對，防止日後漏設）。
- **分鐘欄位**：5 個鍵的 `minimum/maximum/step/decimals` 等於 `0.1/9999/0.1/1`。

---

### M3 `ui/strings.py`：文案集中（新增）

**職責**　集中所有面向使用者的繁中字串（按鈕、狀態、提示、錯誤、提醒），對應 proposal §11，利於一致性與日後 i18n。

**公開介面（節錄）**

```python
# 設定
SETTINGS_TITLE = "設定"
SETTINGS_SAVED_RESTART = "設定已儲存。部分變更需要重新啟動程式後才會生效。"
SETTINGS_SAVED_OK = "知道了"
ERR_RTSP_URL_EMPTY = "請先填入 RTSP 串流位址。"

# 連線/狀態（鍵對應 M4 ConnectionState）
CONN_TEXT: dict["ConnectionState", str]   # 待機/連線中/已連線/重新連線中/收不到影像/發生錯誤
CONN_NO_SIGNAL = "目前收不到影像。請確認攝影機或串流來源後再試一次。"
CONN_RECONNECTING = "連線中斷，正在重新連線…"

# 計時狀態
STATE_TEXT: dict["TimerState", str]       # 待機/工作中/短暫離開/提醒中

# 提醒
REMIND_TITLE = "該休息一下了"
REMIND_BODY = "你已連續工作 {minutes} 分鐘。"
REMIND_START_REST = "開始休息"
REMIND_ACK = "我知道了"
REMIND_SNOOZE = "再 {minutes} 分鐘"
REMIND_CLOSE = "關閉"

# 今日彙總
TODAY_EMPTY = "今天還沒有紀錄，開始工作後就會出現在這裡。"
```

**相依**　型別提示參照 `types.TimerState` 與 M4 `ConnectionState`（僅型別，避免迴圈相依：實作上以字串鍵或延遲匯入處理）。無 Qt。

**獨立測試策略**　斷言 `CONN_TEXT`、`STATE_TEXT` 對每個 enum 成員都有鍵；含參數的字串 `.format(...)` 不丟 `KeyError`。

---

### M4 `app/connection_state.py`：連線狀態模型（新增）

**職責**　定義 UI 用的連線狀態枚舉，並把 worker 發出的原始字串**純函式**映射為狀態，供主視窗 `ConnectionBadge` 呈現（文字 + 圖示 + 語意色，FR-2.6、不只靠顏色）。

**公開介面**

```python
class ConnectionState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    NO_SIGNAL = "no_signal"
    ERROR = "error"

def from_status(status: str) -> ConnectionState: ...   # worker 字串 → 狀態
def severity(state: ConnectionState) -> str: ...        # "neutral"|"info"|"success"|"warning"|"danger"
def icon_key(state: ConnectionState) -> str: ...        # 對應 M8 主題圖示鍵
```

- `from_status` 映射：`connecting→CONNECTING`、`connected→CONNECTED`、`reconnecting→RECONNECTING`、`no_signal→NO_SIGNAL`，未知 → `IDLE`；`ERROR` 由主視窗在收到 `failed` 訊號時直接設定，不經 `from_status`。
- `severity` 提供語意色彩角色（M8 QSS 以此上色）；`icon_key` 確保每個狀態都有圖示（達成「不只靠顏色」）。

**相依**　無（純枚舉 + 純函式）。

**獨立測試策略**　對所有已知字串驗證映射；未知字串 → `IDLE`；每個 `ConnectionState` 都有非空 `severity` 與 `icon_key`。

---

### M5 `logging_setup.py`：應用程式 log 與解碼噪音壓制（新增）

**職責**　(a) 設定可輪替的應用程式 log 檔（FR-4.2）；(b) 壓制 OpenCV / FFmpeg 解碼噪音（FR-4.1）。

**公開介面**

```python
def setup_logging(log_dir: str = "data/logs",
                  level: int = logging.INFO,
                  max_bytes: int = 1_000_000,
                  backup_count: int = 3) -> logging.Logger: ...

def suppress_decoder_noise() -> None: ...
```

- `setup_logging`：建立 `log_dir`，掛 `RotatingFileHandler(app.log)`，設定格式 `時間 等級 模塊 訊息`，回傳 root logger。
- `suppress_decoder_noise`：
  - `os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")`（quiet）。
  - 若可匯入：`cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)`。
- **順序約束（重要）**：`suppress_decoder_noise()` 必須在 `create_source()` / 任何 `cv2.VideoCapture` 開啟**之前**呼叫（env 於開啟 FFMPEG capture 時被讀取）。故 M13 在 `main()` 最前段呼叫本模塊。

**相依**　標準庫 `logging`、`os`；`cv2`（容錯匯入，缺少時只設 env）。

**獨立測試策略**　以 `tmp_path` 呼叫 `setup_logging`，斷言 root logger 掛上 `RotatingFileHandler` 且檔案產生、等級正確；呼叫 `suppress_decoder_noise()` 後 `os.environ["OPENCV_FFMPEG_LOGLEVEL"] == "-8"`（`cv2` 部分用 monkeypatch 驗證有呼叫到，或缺 `cv2` 時不拋例外）。

---

### M6 `logging_store.py`：今日彙總唯讀查詢（修改）

**職責**　在 `SessionStore` 新增唯讀彙總方法，供主視窗顯示今日工作時長與休息次數（FR-2.3）。**不更動**既有寫入路徑與 schema。

**公開介面（新增）**

```python
@dataclass(frozen=True)
class TodaySummary:
    work_seconds: int
    rest_count: int
    work_sessions: int

class SessionStore:
    ...
    def today_summary(self, now: datetime | None = None) -> TodaySummary: ...
```

- SQL（單句、依本地日期過濾）：

```sql
SELECT type, COALESCE(SUM(duration_sec), 0), COUNT(*)
FROM sessions
WHERE date(start_ts) = date(:today)
GROUP BY type;
```

- `start_ts` 以 ISO 字串存放，SQLite `date()` 可直接解析。`now` 預設 `datetime.now()`，便於測試注入固定日期。
- **執行緒**：沿用既有「每執行緒一條連線」機制——主執行緒呼叫 `today_summary` 會取得自己的連線（讀取已提交資料）。worker 在另一執行緒寫入；讀寫分屬不同連線，互不阻塞。

**相依**　`sqlite3`、`datetime`（皆既有）。

**獨立測試策略**　以暫存 DB `init_schema()` 後插入跨日 work/rest 列，固定 `now`，斷言 `work_seconds`、`rest_count`、`work_sessions` 僅計入當日；空資料庫回傳 `TodaySummary(0,0,0)`。

---

### M7 `app/worker.py`：豐富連線狀態（修改）

**職責**　把 `connection_status` 的詞彙從 `connected/reconnecting` 擴充為 UI 可區分的狀態，並維持 `failed` 為「回報、不自行結束」。**嚴禁更動**偵測 / 在場 / 計時的呼叫與行為。

**公開介面（訊號不變，語意擴充）**

```python
class DetectionWorker(QObject):
    frame_ready = Signal(object)        # Frame
    presence_changed = Signal(bool)
    timer_updated = Signal(object)      # TimerSnapshot
    reminder_show = Signal(object)      # ReminderContext
    reminder_repeat = Signal(object)
    connection_status = Signal(str)     # 新增可發出 "connecting"/"no_signal"
    failed = Signal(str)
    # 方法不變：run/stop/pause/resume/dismiss_reminder/set_roi
```

- `run()` 進入主迴圈前先 `connection_status.emit("connecting")`。
- 讀格時的狀態映射（只改這段發射邏輯）：

| 條件 | 發出 |
|---|---|
| `frame is None` 且 `source.is_opened is False` | `"reconnecting"` |
| `frame is None` 且 `source.is_opened is True` | `"no_signal"` |
| `frame` 正常 | `"connected"` |

- `is_opened` 取自 `ReconnectingSource`（既有）。例外仍 `failed.emit(str(exc))`（不在 worker 內結束程式）。
- 與 M4 對齊：UI 端 `from_status()` 直接消化上述字串。

**相依**　不變（`video_source`/`detector`/`presence`/`timer_engine`/`logging_store` 介面卡）。

**獨立測試策略**　沿用既有 `test_worker` 假件風格：注入可控 `is_opened` 與 `read()` 回傳序列的假 source，斷言發出的 `connection_status` 序列為 `connecting → no_signal/reconnecting → connected`；偵測 / 計時呼叫次數與既有測試一致（確保未改核心行為）。

---

### M8 `ui/theme.py`：主題管理（新增）

**職責**　偵測 Windows 系統深 / 淺色、提供兩套語意 token 與對應 QSS、套用到 `QApplication`（FR-5）。把「決定主題」（純）與「套用 QSS」（Qt）拆開以利測試。

**公開介面**

```python
class ColorScheme(Enum):
    LIGHT = "light"; DARK = "dark"

@dataclass(frozen=True)
class ThemeTokens:
    bg: str; surface: str; border: str
    text_primary: str; text_secondary: str
    accent: str; success: str; warning: str; danger: str; info: str

LIGHT_TOKENS: ThemeTokens
DARK_TOKENS: ThemeTokens

def detect_scheme(app: QApplication) -> ColorScheme: ...   # 純決策（見下）
def tokens_for(scheme: ColorScheme) -> ThemeTokens: ...
def build_qss(tokens: ThemeTokens) -> str: ...             # 純字串組裝

class ThemeManager:
    def __init__(self, app: QApplication) -> None: ...
    def apply(self) -> None: ...                # detect → build → app.setStyleSheet
    def current(self) -> ColorScheme: ...
    def watch_system_changes(self) -> None: ... # 連 styleHints().colorSchemeChanged 重套（選配）
```

- `detect_scheme`：優先用 `app.styleHints().colorScheme()`（PySide6 6.5+，回傳 `Qt.ColorScheme.Dark/Light`）；無法判定時退回讀登錄檔 `HKCU\…\Themes\Personalize\AppsUseLightTheme`，再退回 `LIGHT`。
- **語意色彩角色**：widget 以 `setProperty("role", "danger"|"warning"|...)` 標記，QSS 用 `[role="danger"]` 上色；狀態一律「文字 + 圖示 + 色」三者並用（FR-6.3）。

**相依**　`PySide6`（`QApplication`/`QStyleHints`）；登錄檔退路用標準庫 `winreg`。`ThemeTokens`/`build_qss` 部分為純邏輯。

**獨立測試策略**

- 純部分：`tokens_for` 對 `LIGHT/DARK` 回傳不同 token；`build_qss(tokens)` 產出的字串包含 token 色值與關鍵選擇器。
- `detect_scheme`：注入假 `app.styleHints()` 回傳 Dark → 得 `DARK`；styleHints 不可用時走登錄檔退路（monkeypatch `winreg`）。

---

### M9 `ui/settings.py`：設定視窗重構

**職責**　以側邊欄分類 + 資料驅動表單實作完整設定頁（FR-1 全項）：逐欄說明、分鐘欄位 0.1~9999、就近驗證、儲存後重啟提示、來源型別切換顯隱、鍵盤可達；移除死訊號（D5）。

**公開介面**

```python
class SettingsWindow(QDialog):
    def __init__(self, config: AppConfig,
                 config_path: str = "config.yaml",
                 parent: QWidget | None = None) -> None: ...
    # 無 config_changed（採手動重啟，不做即時套用）
```

**內部結構**

- 版面：`QHBoxLayout`〔左 `QListWidget`（`CATEGORIES`）｜右 `QStackedWidget`（每分類一頁 `QFormLayout`）〕＋底部 `QDialogButtonBox(Save|Cancel)`。
- 由 `settings_schema.SCHEMA`（M2）建立每個欄位控制項：

| `WidgetKind` | Qt 控制項 | 設定 |
|---|---|---|
| FLOAT | `QDoubleSpinBox` | `setRange(min,max)`、`setSingleStep(step)`、`setDecimals(decimals)` |
| INT | `QSpinBox` | `setRange/​setMinimum` |
| TEXT | `QLineEdit` | — |
| PATH | `QLineEdit` + `QPushButton("瀏覽")` → `QFileDialog` | — |
| CHOICE | `QComboBox` | `addItems(choices)` |
| BOOL | `QCheckBox` | — |

- 每欄位下方加一個 `QLabel`（`role="secondary"`）顯示 `FieldSpec.hint`（FR-1.3）。
- **來源型別切換（FR-1.7）**：監聽 `source.type` 的 `QComboBox.currentTextChanged`，`rtsp` 時啟用 `rtsp_url`、淡化 `webcam_index`，反之亦然。
- **儲存流程（FR-1.5/1.6）**：
  1. 走訪控制項 → 用 `settings_schema.set_value` 疊出候選 `AppConfig` → 用 `_serialize_app_config` 轉 dict。
  2. 呼叫 `config.validate(dict)`（M1）。
  3. 有錯：解析錯誤字串的鍵前綴，將對應欄位的 hint 標籤轉 `role="danger"` 並顯示訊息（如 `ERR_RTSP_URL_EMPTY`），**不關閉視窗**。
  4. 無錯：`save_config(updated, config_path)` → `QMessageBox.information(SETTINGS_SAVED_RESTART)` → `accept()`。
- **鍵盤可達（FR-1.9）**：`Tab` 巡覽、`Save` 為 default、`Esc` → `reject`；`QListWidget` 可上下鍵切換分類。

**相依**　M2（schema/讀寫）、M1（validate/save）、M3（文案）、M8（主題繼承）。

**獨立測試策略（pytest-qt）**

- 以暫存 `config_path` + 預設 `AppConfig` 建構，斷言各控制項初值等於設定值、分鐘欄位的 range/step/decimals 正確。
- 設無效值（`work=0`）按 Save：`config_path` **未**被寫、顯示錯誤、視窗未關。
- 設有效值按 Save（monkeypatch `QMessageBox`）：檔案被寫且 YAML 內容符合預期、出現重啟提示、視窗關閉。
- 切 `source.type` → 對應欄位啟用狀態改變。

---

### M10 `ui/main_window.py` + `ui/widgets/*`：主視窗重構與子元件拆分

**職責**　以「內容優先」重整主視窗（FR-2），並拆成數個**可獨立測試**的子元件。

**子元件（各一檔，`src/ui/widgets/`）**

```python
class PreviewView(QWidget):
    roi_committed = Signal(object)            # BBox，放開滑鼠且處於編輯模式時
    def set_frame(self, frame: Frame) -> None: ...
    def set_roi(self, roi: BBox) -> None: ...
    def set_edit_mode(self, on: bool) -> None: ...     # 非編輯模式不可拖曳
    def set_overlay_text(self, text: str) -> None: ...

class StatusStrip(QWidget):
    def update_snapshot(self, snap: TimerSnapshot, work_threshold_sec: float) -> None: ...
    # 顯示：狀態文字 + mm:ss + QProgressBar(0..threshold)

class ConnectionBadge(QWidget):
    def set_state(self, state: ConnectionState) -> None: ...   # 文字+圖示+語意色

class TodaySummaryView(QWidget):
    def set_summary(self, summary: TodaySummary | None) -> None: ...  # None/0 → 空狀態文案

class ActionBar(QWidget):
    edit_roi_toggled = Signal(bool)
    pause_toggled = Signal(bool)
    open_settings = Signal()
```

**`MainWindow`（組裝者）**

```python
class MainWindow(QMainWindow):
    roi_changed = Signal(object)        # BBox → worker.set_roi
    request_pause = Signal(bool)        # → worker.pause/resume
    request_settings = Signal()

    def __init__(self, config: AppConfig, store: SessionStore,
                 config_path: str = "config.yaml") -> None: ...

    # slots（沿用既有名稱以降低接線變動）
    def on_frame_ready(self, frame: Frame) -> None: ...
    def on_presence_changed(self, present: bool) -> None: ...
    def on_timer_updated(self, snap: TimerSnapshot) -> None: ...
    def on_connection_status(self, status: str) -> None: ...   # → ConnectionState 經 M4
    def on_failed(self, message: str) -> None: ...             # → ConnectionBadge=ERROR（D3）
    def closeEvent(self, e: QCloseEvent) -> None: ...          # 隱藏到匣（維持）
```

- **版面**（內容優先）：中央 `PreviewView`（主角）；下方 `StatusStrip`；頂列右側 `ConnectionBadge`；`TodaySummaryView` 置於狀態列旁或下方；底部 `ActionBar`。
- **進度條**：`MainWindow` 持有 `work_threshold_sec = config.timer.work_threshold_min * 60`，傳給 `StatusStrip.update_snapshot`。
- **ROI 寫回（FR-2.5、修 D4）**：`PreviewView.roi_committed` →
  1. `updated = set_value(self._config, "presence.roi", roi)`（或直接 `replace`）。
  2. `save_config(updated, self._config_path)`（放開滑鼠才寫、頻率低）。
  3. `self.roi_changed.emit(roi)` → worker 即時套用。
- **今日彙總刷新**：建構時持 `store`；用 `QTimer`（如 30s）呼叫 `store.today_summary()` → `TodaySummaryView.set_summary`；首次顯示即刷新一次。
- **編輯 ROI 模式**：`ActionBar.edit_roi_toggled` → `PreviewView.set_edit_mode`（預設關閉，只有開啟才可框選）。

**相依**　M4（狀態映射）、M3（文案）、M6（今日彙總，唯讀）、`types`、M8（主題）。

**獨立測試策略（pytest-qt）**

- 子元件各自建構後餵資料：`StatusStrip` 給不同 `TimerSnapshot` → 文字 / 進度值正確；`ConnectionBadge` 給每個狀態 → 有文字且非僅靠色（圖示鍵非空）；`TodaySummaryView` 給 `TodaySummary(0,0,0)` → 顯示空狀態；`PreviewView` 在非編輯模式拖曳 → **不**發 `roi_committed`，編輯模式拖曳 → 發一次。
- `MainWindow`：注入假 `store`，呼叫 `on_connection_status("no_signal")` → badge 文字為「收不到影像」；`on_failed(...)` → badge=ERROR；模擬 `roi_committed` → `config_path` 被寫且 `roi_changed` 發射。

---

### M11 `ui/tray.py`：系統匣圖示與 toggle 修正（修改）

**職責**　提供真實圖示（修 D8）、依狀態更新 tooltip、把 toggle 修正為真正的暫停 / 繼續（修 D1）。

**公開介面**

```python
class TrayIcon(QSystemTrayIcon):
    def __init__(self, parent: QWidget | None = None) -> None: ...   # 以 A1 後備圖示初始化
    def bind_window(self, window: QWidget) -> None: ...
    def set_timer_state(self, state: TimerState) -> None: ...          # 更新 tooltip（記住最後狀態）
    def set_connection(self, state: ConnectionState) -> None: ...      # 更新 tooltip（記住最後連線）
    def set_paused(self, paused: bool) -> None: ...                    # 切換 toggle_action 文字
    # actions: open_action / toggle_action / settings_action / quit_action
```

- 圖示：呼叫 A1 `make_app_icon()` 取得程式內繪製的 `QIcon`，確保非空。
- `set_paused(True)` → `toggle_action.setText("繼續偵測")`；`False` → `"暫停偵測"`。實際 pause/resume 由 M13 接線（見下），tray 只負責文字與發出 action。

**相依**　`types.TimerState`、M4 `ConnectionState`、A1 圖示、M3 文案。

**獨立測試策略**　建構後 `icon().isNull() is False`；`set_timer_state` / `set_connection` 後 `toolTip()` 含對應狀態字樣；`set_paused(True/False)` 後 `toggle_action.text()` 對應變化。

---

### M12 `reminder/media.py` + `reminder/*`：提醒統一與媒體降級

**職責**　(a) 媒體載入優雅降級（FR-3.5、修 D7）；(b) 三種提醒視覺 / 文案統一、按鈕依 `reset_mode` 呈現（沿用單一 `dismissed` 契約）；(c) 修 `FloatingReminder` 補發 `dismissed`（D2）。

**M12a `reminder/media.py`（新增）**

```python
def load_pixmap(path: str, *, fallback_text: str = REMIND_TITLE) -> QPixmap: ...
#   QPixmap(path)；若 path 空 / 不存在 / isNull → 以 QPainter 繪製含 fallback_text 的預設圖
def is_playable_video(path: str) -> bool: ...      # 副檔名 + 存在性粗篩
def safe_sound_url(path: str) -> QUrl | None: ...  # 空或不存在 → None（不播放、不報錯）
```

**M12b `ReminderContext` 擴充（`types.py`，附加欄位、向後相容）**

```python
@dataclass(frozen=True)
class ReminderContext:
    work_minutes: int
    media_path: str
    media_type: str
    sound_path: str
    reset_mode: str = "detection"     # 新增：供提醒選擇按鈕
    snooze_minutes: int = 5           # 新增：再 N 分鐘的 N
```

> 僅新增欄位、給預設值，不改 `TimerEngine` 任何行為（符合非目標）。由 M13 在組裝 `ReminderContext` 時帶入 `cfg.reminder.reset_mode.value` 與 `int(cfg.reminder.snooze_min)`。

**M12c 按鈕 → 動作對應（單一 `dismissed` 契約下的真實語意）**

| `reset_mode` | 主要按鈕 | 次要按鈕 | 按下主要鈕的效果（經 `dismissed` → `TimerEngine.on_reminder_dismissed`） |
|---|---|---|---|
| `dismiss` | 開始休息 | 關閉 | 立即 `WORK_ENDED`＋`WORK_STARTED`，計時重置並重新開始 |
| `snooze` | 再 N 分鐘 | 關閉 | 設定 `snooze_until`，N 分鐘後再次提醒 |
| `detection` | 我知道了 | 關閉 | 暫停「重複提醒」；**真正重置需離開 ROI 達休息門檻**（系統以在場為準） |

- 「關閉」= 只 `hide()` 視窗、**不**發 `dismissed`；依 `TimerEngine` 既有重複邏輯可能再次出現（如 `detection` 模式）。此為「沿用單一契約 + 不改計時核心」的必然取捨，已於此明列以免文案誤導。
- 三種提醒共用 M3 文案與 M8 語意色；`PopupReminder` 以 `media.load_pixmap` / `is_playable_video` 取代直載。

**各提醒變更**

```python
class PopupReminder(QDialog):     # 重構：媒體走 media.py；按鈕集依 ctx.reset_mode 決定
    dismissed = Signal()
class ToastReminder(QObject):     # 文案統一；維持「顯示即 dismissed」（toast 無法承載按鈕）
    dismissed = Signal()
class FloatingReminder(QWidget):  # 修 D2：mousePressEvent → dismissed.emit()
    dismissed = Signal()
# factory.create_reminder(cfg, tray) 介面不變
```

**相依**　`PySide6`（Widgets/Multimedia/Gui）、M3 文案、M8 語意色、`types.ReminderContext`。

**獨立測試策略**

- `media.load_pixmap`：空字串 / 不存在 / 故意毀損檔 → 回傳 `not isNull()` 的預設圖；正常圖 → 載入成功。`safe_sound_url("")` → `None`。
- `PopupReminder`（pytest-qt）：給 `reset_mode="snooze", snooze_minutes=5` → 出現「再 5 分鐘」鈕，按下 → 發 `dismissed`；給毀損 `media_path` → 不拋例外且顯示預設圖。
- `FloatingReminder`：模擬點擊 → 發出 `dismissed`（回歸測試 D2）。

---

### M13 `main.py`：組裝與接線（修改）

**職責**　把上述模塊接成可運行的應用；修正 D1 / D3 / D5 的接線；確保 logging / 主題 / store 的建立順序正確。

**關鍵變更**

```python
def main() -> int:
    setup_logging(); suppress_decoder_noise()           # M5，必須最早（在 create_source 前）
    app = QApplication.instance() or QApplication(sys.argv)
    ThemeManager(app).apply()                           # M8
    cfg = load_config("config.yaml")

    store = SessionStore(cfg.logging.db_path)           # 由 main 建立，注入給 worker 與 window
    worker = _build_worker(cfg, store)                  # _build_worker 改為接受 store
    thread = QThread(); worker.moveToThread(thread); thread.started.connect(worker.run)

    window = MainWindow(cfg, store)                     # M10，注入 store 供今日彙總
    tray = TrayIcon(); tray.bind_window(window)
    reminder = create_reminder(cfg.reminder, tray)
    settings = SettingsWindow(cfg, "config.yaml", window)   # M9（無 config_changed）

    # 影像/狀態
    worker.frame_ready.connect(window.on_frame_ready)
    worker.presence_changed.connect(window.on_presence_changed)
    worker.timer_updated.connect(window.on_timer_updated)
    worker.timer_updated.connect(lambda s: tray.set_timer_state(s.state))
    worker.connection_status.connect(window.on_connection_status)
    worker.connection_status.connect(lambda st: tray.set_connection(from_status(st)))
    worker.failed.connect(window.on_failed)             # D3：改為錯誤狀態，不再 app.quit
    # 提醒
    worker.reminder_show.connect(reminder.show)
    worker.reminder_repeat.connect(reminder.show)
    reminder.dismissed.connect(worker.dismiss_reminder)
    # ROI / 動作
    window.roi_changed.connect(worker.set_roi)
    window.request_settings.connect(settings.show)
    window.request_pause.connect(lambda p: worker.pause() if p else worker.resume())
    # 系統匣（D1：真正 toggle）
    tray.settings_action.triggered.connect(settings.show)
    tray.toggle_action.triggered.connect(_toggle_pause)   # 內部翻轉 paused 並 tray.set_paused / worker.pause|resume
    tray.quit_action.triggered.connect(app.quit)
    app.aboutToQuit.connect(lambda: _shutdown_worker_thread(worker, thread))
    ...
```

- `_build_worker(cfg, store)`：簽章加入 `store`；`ReminderContext` 帶入 `reset_mode=cfg.reminder.reset_mode.value`、`snooze_minutes=int(cfg.reminder.snooze_min)`（M12b）。
- 移除 `worker.failed → app.quit`；改接 `window.on_failed`（D3）。
- `_toggle_pause`：維護單一 `paused` 旗標，呼叫 `worker.pause()/resume()` 並同步 `tray.set_paused()` 與 `ActionBar`（D1）。

**相依**　全部模塊。

**獨立測試策略**　`main.py` 以「接線」為主，採輕量整合測試：可抽出 `build_app(cfg, store, ...)` 純接線函式回傳已連接的物件群，斷言關鍵連線存在（如 `worker.failed` 接到 `window.on_failed`、未接 `app.quit`）；端到端啟動仍以手動驗收為準。

---

### A1 後備圖示 / 預設媒體（新增）

**職責**　因 `data/` 被 `.gitignore` 忽略，提供**程式內繪製**的後備圖示與預設提醒畫面，確保缺資產檔也能運作（修 D8、配合 D7）。

**公開介面**

```python
# src/ui/icons.py
def make_app_icon(scheme: ColorScheme | None = None) -> QIcon: ...   # 以 QPainter 畫簡單字符/圖形
```

- 系統匣與視窗圖示優先用 `data/assets/` 的檔案；不存在則用 `make_app_icon()`。
- 提醒預設畫面由 M12a `load_pixmap` 的繪製分支提供。

**獨立測試策略**　`make_app_icon()` 回傳 `not isNull()` 的 `QIcon`；不依賴任何外部檔案。

---

## 7. 關鍵流程時序

**(1) 啟動**
```
main: setup_logging → suppress_decoder_noise → QApplication → ThemeManager.apply
    → load_config → SessionStore → build_worker(store) → MainWindow(store)/Tray/Settings
    → 接線 → thread.start → worker.run（emit "connecting"）
```

**(2) 設定儲存（FR-1.5/1.6）**
```
使用者改值 → 按 Save → set_value 疊 AppConfig → validate(dict)
   ├─ 有錯 → 欄位 role=danger + 訊息（視窗不關）
   └─ 無錯 → save_config → QMessageBox「重啟後生效」→ accept
```

**(3) ROI 編輯（FR-2.5、修 D4）**
```
ActionBar 編輯ROI on → PreviewView 可框選 → 放開滑鼠 → roi_committed(BBox)
   → MainWindow: save_config(roi) + roi_changed → worker.set_roi（即時）
```

**(4) 連線狀態（FR-2.6）**
```
worker 讀格 → emit connecting/connected/reconnecting/no_signal
   → MainWindow.on_connection_status → from_status → ConnectionBadge(文字+圖示+色)
worker 例外 → failed → MainWindow.on_failed → ConnectionBadge=ERROR（程式續活）
```

**(5) 提醒（沿用單一 dismissed 契約）**
```
TimerEngine REMINDER_TRIGGERED → worker.reminder_show(ctx) → reminder.show
   → 使用者按鈕 → dismissed → worker.dismiss_reminder → TimerEngine.on_reminder_dismissed
     （行為依 reset_mode：dismiss=重置 / snooze=貪睡 / detection=暫停重複）
```

---

## 8. 設定 schema 資料結構（M2 SCHEMA 對照）

> 完整欄位、控制項、範圍、提示文字同 `proposal.md` §9；以下為 schema 欄位的形式化摘要（分類 → 鍵 → WidgetKind → 範圍/選項）。

- **基本**：`source.type`(CHOICE rtsp/webcam)、`source.rtsp_url`(TEXT)、`source.webcam_index`(INT≥0)、`timer.work_threshold_min`/`timer.reset_threshold_min`/`timer.required_rest_min`(FLOAT 0.1~9999/0.1/1)
- **偵測**：`detection.confidence`(FLOAT 0~1/0.05)、`presence.min_box_height_ratio`(FLOAT 0~1/0.05)、`presence.debounce_count`(INT≥1)、`detection.interval_sec`(FLOAT>0)
- **提醒**：`reminder.method`(CHOICE)、`reminder.reset_mode`(CHOICE)、`reminder.repeat_interval_min`/`reminder.snooze_min`(FLOAT 0.1~9999/0.1/1)、`reminder.popup.media_path`(PATH)、`reminder.popup.media_type`(CHOICE image/video)、`reminder.popup.sound_path`(PATH)、`reminder.floating.position`(CHOICE 四角)
- **紀錄**：`logging.enabled`(BOOL)、`logging.db_path`(PATH)
- **進階**：`detection.model_path`(PATH)、`detection.device`(CHOICE auto/cpu/cuda)、`source.reconnect_interval_sec`(FLOAT>0)、`ui.start_minimized`(BOOL)

> 註：`reminder.floating.position` 目前 config 驗證僅 `top-right`；擴為四角需同步在 `config.validate` 加入選項檢查（列為 §11 待辦）。

---

## 9. 主題 token 與 QSS 結構（M8）

- **Token 角色**：`bg / surface / border / text_primary / text_secondary / accent / success / warning / danger / info`，淺深各一套。
- **語意對應**：連線狀態 severity（M4）→ 色角色：`CONNECTED→success`、`RECONNECTING/NO_SIGNAL→warning`、`ERROR→danger`、`CONNECTING→info`、`IDLE→neutral`。
- **QSS organize**：以 `QWidget#objectName` 與 `[role="..."]` 屬性選擇器套色；狀態同時設文字與圖示（不只靠顏色）。
- **套用點**：`ThemeManager.apply()` 在 `QApplication` 層 `setStyleSheet`，全 app 繼承；可選 `watch_system_changes` 即時重套。

---

## 10. 測試計畫總表

| 模塊 | 測試型別 | 手法 / 假件 | 重點斷言 |
|---|---|---|---|
| M1 config | 單元 | 表驅動 | 分鐘鍵 0.1/9999 邊界、錯誤字串 |
| M2 schema | 單元 | 反射列舉 dataclass | 涵蓋率、get/set round-trip |
| M3 strings | 單元 | — | enum 鍵齊全、format 不丟 |
| M4 connection_state | 單元 | — | 映射、severity/icon 非空 |
| M5 logging_setup | 單元 | tmp_path / monkeypatch | handler/等級/env |
| M6 today_summary | 單元 | 暫存 DB + 固定 now | 當日彙總、空回傳 |
| M7 worker | 單元 | 假 source（控制 is_opened/read） | 狀態序列、核心呼叫不變 |
| M8 theme | 單元 | 假 styleHints / winreg | 決策、QSS 內容 |
| M9 settings | pytest-qt | 暫存 config_path / patch QMessageBox | 填值、擋無效、寫檔、重啟提示 |
| M10 main/widgets | pytest-qt | 假 store / 模擬事件 | 子元件呈現、ROI 寫回、錯誤狀態 |
| M11 tray | pytest-qt | — | 圖示非空、tooltip、toggle 文字 |
| M12 media/reminder | 單元 + pytest-qt | 毀損檔 / 模擬點擊 | 降級、按鈕集、floating dismissed |
| M13 main | 輕量整合 | `build_app` 純接線 | 關鍵連線存在、failed 不接 quit |

---

## 11. 對既有測試的影響與待辦

- `test_worker.py`：新增「狀態序列」案例；確認既有偵測 / 計時呼叫斷言不變。
- `test_config.py`：新增分鐘欄位邊界案例；若擴 `floating.position` 選項驗證，需同步補測。
- `test_ui.py`：隨 `SettingsDialog → SettingsWindow`、`MainWindow` 重構調整；新增子元件測試檔。
- `test_reminder.py`：新增 `media` 降級與 `FloatingReminder.dismissed` 回歸。
- 維持 `ruff` / `mypy --strict` 綠燈；新模塊一律加型別註記。
- **待辦**：`reminder.floating.position` 四角選項需在 `config.validate` 補檢查（proposal §14 已列）。

---

## 12. 風險與未決事項

- 主題即時切換在部分 Windows 版本未必即時反映；先保證「啟動時套用」，即時切換為選配。
- `OPENCV_FFMPEG_LOGLEVEL` 實際生效程度依 OpenCV / FFmpeg 版本，需實機確認；設計上已保證「最早設定」。
- 單一 `dismissed` 契約下，`detection` 模式按鈕只能「暫停重複提醒」，真正重置仍靠離開 ROI；若日後要按鈕級顯式語意，需改採「顯式動作訊號」方案（本次未採）。
- 今日彙總跨執行緒讀寫採各自連線；若日後寫入頻繁，考慮開啟 WAL。

---

## 13. 追溯表（FR → 模塊）

| 需求 | 對應模塊 |
|---|---|
| FR-1 設定頁面 | M1、M2、M3、M9 |
| FR-2 主視窗 | M4、M6、M7、M10、M13 |
| FR-3 系統匣與提醒 | M3、M11、M12、A1 |
| FR-4 執行品質 | M4、M5、M7、M12、M13 |
| FR-5 主題 | M8、M13 |
| FR-6 無障礙 | M3、M8、M9、M10、M11（跨 UI） |
| 既有缺陷 D1–D8 | M7、M9、M10、M11、M12、M13 |
