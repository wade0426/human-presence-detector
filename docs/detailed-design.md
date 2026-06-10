# 詳細設計文檔：休息提醒系統功能擴充

> 文件狀態：詳細設計（介面層）
> 對應需求：`docs/proposal.md`（需求一～五）
> 層級：介面 / 模塊設計。本文描述「模塊職責、介面簽章、資料結構、依賴與注入點、流程、錯誤處理、單元測試設計」，僅以少量示意片段輔助，**不含完整實作程式碼**。

---

## 1. 設計原則與全域約束

1. **純邏輯與 Qt 分離**：每個有狀態判斷的功能，都拆成「純決策類別（無 Qt、可直接餵資料測試）」＋「薄 Qt 外殼（負責訊號、視窗、計時器、OS 呼叫）」。
2. **OS / 副作用可注入**：所有對外部系統的副作用（鎖定螢幕、播放音效）都以參數注入函式 / 物件，預設值為真實實作，測試時替換為假替身（fake）。
3. **設定於啟動時讀取一次**：與既有行為一致——設定存檔後需**重新啟動程式**才生效（沿用 `SETTINGS_SAVED_RESTART`）。控制器只在 `main()` 啟動時依 `AppConfig` 建立，**不需熱重載**。
4. **既有狀態機不變**：不修改 `TimerEngine`、`PresenceEvaluator`、偵測流程。新功能皆為「旁觀者」：訂閱既有訊號 / 快照，不回寫計時狀態（需求三 FR-3.5）。
5. **向後相容**：既有元件（如 `ReturnPromptDialog()`）的無參數建構方式必須維持可用，新參數一律有預設值。
6. **測試骨架沿用**：純邏輯用一般 `pytest`；Qt 元件用 `qtbot` + offscreen（`tests/conftest.py` 已設 `QT_QPA_PLATFORM=offscreen`）；訊號用 `qtbot.waitSignal`；Qt 測試標記 `@pytest.mark.qt`。

### 1.1 模塊地圖

| 模塊 | 檔案（新增 N／修改 M） | 對應需求 | Qt？ | 測試檔 |
| --- | --- | --- | --- | --- |
| M0 設定模型擴充 | `src/config.py` (M) | 一、三 | 否 | `tests/test_config.py` (M) |
| M1a 循環音效播放器 | `src/reminder/sound.py` (N) | 一 | 是 | `tests/test_return_sound.py` (N) |
| M1b 回來對話框音效 | `src/reminder/return_prompt.py` (M) | 一 | 是 | `tests/test_return_sound.py` (N) |
| M2a 紀錄清除方法 | `src/logging_store.py` (M) | 二 | 否 | `tests/test_logging_store.py` (M) |
| M2b 清除服務 | `src/app/clear_data.py` (N) | 二 | 否 | `tests/test_clear_data.py` (N) |
| M2c 清除對話框與流程 | `src/ui/clear_data_dialog.py` (N) | 二 | 是 | `tests/test_clear_data_dialog.py` (N) |
| M3a 平台鎖定函式 | `src/app/screen_lock.py` (N) | 三 | 否 | `tests/test_screen_lock.py` (N) |
| M3b 鎖定決策（純） | `src/app/force_lock.py` (N) | 三 | 否 | `tests/test_force_lock.py` (N) |
| M3c 鎖定控制器 | `src/app/force_lock_controller.py` (N) | 三 | 是 | `tests/test_force_lock_controller.py` (N) |
| M3d 倒數警示視窗 | `src/ui/force_lock_window.py` (N) | 三 | 是 | `tests/test_force_lock_window.py` (N) |
| M4 提示與 tooltip | `src/ui/settings_schema.py` (M)、`src/ui/settings.py` (M) | 四 | 部分 | `tests/test_settings_schema.py` (M)、`tests/test_ui.py` (M) |
| M5 文字修正 | `src/ui/strings.py` (M)、`src/ui/settings_schema.py` (M) | 五 | 否 | `tests/test_strings.py` (M) |
| INT 整合接線 | `src/main.py` (M)、`src/ui/main_window.py` (M) | 一～三 | 是 | `tests/test_main.py` (M)、`tests/test_ui.py` (M) |

### 1.2 依賴方向（高 → 低）

```
INT (main.py / main_window)
   ├── M1b ──> M1a, M0
   ├── M2c ──> M2b ──> M2a, M0
   └── M3c ──> M3b ──> M0, types ;  M3c ──> M3a ;  M3c ──> M3d
M4 ──> M0（描述新欄位）           M5 獨立（純文案）
```

- 低層模塊（M0、M1a、M2a、M2b、M3a、M3b、M5）皆**不依賴 Qt 事件迴圈**或彼此的 UI，可單獨匯入測試。
- Qt 外殼（M1b、M2c、M3c、M3d、M4）各自只依賴自己那層的純邏輯與注入點。

---

## 2. M0 — 設定模型擴充（`src/config.py`）

### 2.1 職責
新增需求一、三的設定資料類別、驗證規則與序列化；其餘模塊只讀取 `AppConfig`，不自行解析 YAML。

### 2.2 介面（新增資料類別）

```python
@dataclass
class ReturnSoundConfig:
    enabled: bool = False
    sound_path: str = "data/assets/Radar.mp3"

@dataclass
class ForceLockConfig:
    enabled: bool = False
    trigger: str = "overtime"          # "overtime" | "on_rest"
    overtime_threshold_min: float = 10.0
    warning_mode: str = "immediate"    # "countdown_cancel" | "countdown_only" | "immediate"
    countdown_sec: int = 10
```

掛載點：
- `ReminderConfig` 新增欄位 `return_sound: ReturnSoundConfig = field(default_factory=ReturnSoundConfig)`。
- `AppConfig` 新增頂層欄位 `force_lock: ForceLockConfig = field(default_factory=ForceLockConfig)`。

### 2.3 驗證（`validate()` 追加規則）

| 欄位 | 規則 | 錯誤訊息鍵（建議） |
| --- | --- | --- |
| `force_lock.trigger` | ∈ {overtime, on_rest} | `force_lock.trigger must be one of: overtime, on_rest` |
| `force_lock.warning_mode` | ∈ {countdown_cancel, countdown_only, immediate} | `force_lock.warning_mode must be one of: ...` |
| `force_lock.overtime_threshold_min` | `MINUTE_MIN..MINUTE_MAX`（沿用 `_in_range`） | `force_lock.overtime_threshold_min must satisfy ...` |
| `force_lock.countdown_sec` | 整數且 ≥ 1 | `force_lock.countdown_sec must be an integer >= 1` |
| `reminder.return_sound.enabled` | bool（型別寬鬆，沿用 `bool()` 轉換，不強制報錯） | — |

> `return_sound.sound_path` 不在載入期驗證存在性（檔案可能稍後才放入）；播放期才容錯（見 M1）。

### 2.4 解析與序列化
- `_app_config_from_dict()`：於 `reminder` 區段解析 `return_sound`（子字典）；於根層解析 `force_lock`。沿用「缺鍵則用 dataclass 預設值」模式。
- `_serialize_app_config()`：`asdict()` 會自動遞迴巢狀 dataclass，故 `return_sound`、`force_lock` **自動序列化**，無需特例（僅 `presence.roi` 維持既有特例處理）。

### 2.5 錯誤處理
- 解析時對數值欄位以 `float()/int()` 寬鬆轉換；非法值由 `validate()` 在 `load_config()` 階段集中擋下並丟 `ConfigError`（沿用既有流程）。

### 2.6 單元測試設計（`tests/test_config.py` 擴充）

| 測試 | 重點 | 注入點 |
| --- | --- | --- |
| `test_force_lock_defaults` | `AppConfig().force_lock` 各欄位等於預設值 | 無 |
| `test_return_sound_defaults` | `ReminderConfig().return_sound.enabled is False`、預設路徑正確 | 無 |
| `test_validate_force_lock_trigger_invalid` | trigger 非法 → 錯誤列表含對應訊息 | 傳入 raw dict |
| `test_validate_force_lock_warning_mode_invalid` | warning_mode 非法 → 報錯 | raw dict |
| `test_validate_countdown_sec_min` | `countdown_sec=0` → 報錯 | raw dict |
| `test_roundtrip_serialize_force_lock` | `save_config`→`load_config` 後 `force_lock`、`return_sound` 完全一致 | `tmp_path` 暫存檔 |

### 2.7 獨立性
純資料 + 純函式，無 Qt、無 IO（除 `tmp_path` round-trip）。可完全獨立測試。

---

## 3. 需求一：休息結束音效

### 3.1 M1a — 循環音效播放器（`src/reminder/sound.py`，新）

#### 職責
封裝「循環播放 / 停止」音效，並把 Qt 多媒體細節隔離在一個可替換的介面後面。

#### 介面
```python
class LoopingSoundPlayer(Protocol):
    def play(self, sound_path: str) -> None: ...   # 啟動循環播放；路徑無效則安靜略過
    def stop(self) -> None: ...                     # 停止播放（可重複呼叫）

class QtLoopingSoundPlayer:                          # 預設實作（Qt 後端）
    def __init__(self, parent: QObject | None = None) -> None: ...
    def play(self, sound_path: str) -> None: ...
    def stop(self) -> None: ...
```

#### 行為要點
- `QtLoopingSoundPlayer` 內含 `QSoundEffect`，`setLoopCount(QSoundEffect.Infinite)`。
- `play()` 先以既有 `src/reminder/media.py::safe_sound_url()` 驗證路徑；回傳 `None` 則不播放（容錯，FR-1.6）。
- `stop()` 任何狀態皆可安全呼叫（未播放時為 no-op）。

#### 錯誤處理
路徑空 / 不存在 / 非法 → 不丟例外、不播放。

#### 測試設計（`tests/test_return_sound.py`）
| 測試 | 重點 |
| --- | --- |
| `test_qt_player_play_missing_path_no_crash`（qt） | 不存在路徑呼叫 `play()` 不崩潰 |
| `test_qt_player_stop_before_play_no_crash`（qt） | 未播放即 `stop()` 安全 |

> 注：對「是否真的發聲」不做斷言（offscreen / CI 無音訊裝置）；發聲正確性靠 `safe_sound_url` 既有測試 + 手動驗收。對話框邏輯改用 fake player 驗證（見 M1b）。

### 3.2 M1b — 「歡迎回來」對話框音效（`src/reminder/return_prompt.py`，修改）

#### 職責
在對話框顯示時觸發循環音效，確認 / 關閉時停止；是否播放與音檔路徑由設定決定。

#### 介面（建構子擴充，保持向後相容）
```python
class ReturnPromptDialog(QDialog):
    confirmed = Signal()
    def __init__(
        self,
        *,
        return_sound: ReturnSoundConfig | None = None,   # None → 視為停用
        player: LoopingSoundPlayer | None = None,         # None → 內部建立 QtLoopingSoundPlayer
        parent: object = None,
    ) -> None: ...
    def show_prompt(self, *_unused: object) -> None: ...
    def closeEvent(self, event) -> None: ...              # 既有：忽略關閉
```

#### 流程
```
show_prompt():
    設定 body 文案（既有行為）
    show()
    若 return_sound and return_sound.enabled:
        player.play(return_sound.sound_path)

_on_confirmed():      # 既有「開始新一輪」按鈕
    player.stop()
    confirmed.emit(); accept()

closeEvent():         # 既有：忽略 → 對話框不關，音效不停（FR-1.3）
    event.ignore()
```

#### 依賴與注入點
- 注入 `return_sound`（來自 `cfg.reminder.return_sound`）與 `player`。
- 測試注入 fake player（記錄 `play/stop` 呼叫序列），不依賴真實音訊。

#### 測試設計（`tests/test_return_sound.py`）
| 測試 | 重點 | 注入 |
| --- | --- | --- |
| `test_dialog_plays_when_enabled`（qt） | `enabled=True`：`show_prompt()` 後 fake `play` 被呼叫且帶正確路徑 | FakePlayer + `ReturnSoundConfig(enabled=True)` |
| `test_dialog_silent_when_disabled`（qt） | `enabled=False`（或 None）：`play` 不被呼叫 | FakePlayer |
| `test_dialog_stops_on_confirm`（qt） | 點「開始新一輪」→ `stop` 被呼叫且 `confirmed` 發出 | FakePlayer + `qtbot.waitSignal` |
| `test_dialog_close_does_not_stop`（qt） | `close()` 後仍可見、`stop` 未被呼叫（音效持續） | FakePlayer |
| `test_dialog_backward_compatible_no_args`（qt） | `ReturnPromptDialog()` 無參數可建構（既有測試不破） | 無 |

#### 獨立性
對話框只依賴 `LoopingSoundPlayer` 介面與 `ReturnSoundConfig`，與 worker / timer 解耦。

---

## 4. 需求二：清除資料

### 4.1 M2a — 紀錄清除方法（`src/logging_store.py`，修改）

#### 介面
```python
class SessionStore:
    def clear_today(self, now: datetime | None = None) -> int: ...  # 刪 date(start_ts)=今日，回傳刪除筆數
    def clear_all(self) -> int: ...                                  # 刪整表，回傳刪除筆數
```
- 沿用 per-thread 連線（`_get_connection()`），由 UI 主執行緒呼叫。
- 刪除筆數取自 `cursor.rowcount`；`commit()` 後回傳。

#### 錯誤處理
資料表不存在時先 `init_schema()`（與既有 `run()` 一致），確保刪除不因無表而例外。

#### 測試設計（`tests/test_logging_store.py` 擴充）
| 測試 | 重點 |
| --- | --- |
| `test_clear_today_removes_only_today` | 寫入今日 + 昨日列 → `clear_today()` 後僅今日被刪、回傳數正確 |
| `test_clear_all_empties_table` | 寫入多列 → `clear_all()` 後 `today_summary()` 全 0 |
| `test_clear_today_on_empty_table` | 空表呼叫回傳 0、不崩潰 |

注入：以 `tmp_path` 建臨時 sqlite 檔；`clear_today(now=固定 datetime)` 注入時鐘以穩定測試。

### 4.2 M2b — 清除服務（`src/app/clear_data.py`，新）

#### 職責
把「清除範圍」對映到實際動作（刪今日 / 刪全部 / 刪全部＋重設設定），與 UI 完全解耦、可純測試。

#### 介面
```python
class ClearScope(Enum):
    TODAY = "today"
    ALL = "all"
    ALL_AND_RESET = "all_and_reset"

@dataclass(frozen=True)
class ClearResult:
    deleted: int
    reset_config: bool

class ClearDataService:
    def __init__(self, store: SessionStore, config_path: str) -> None: ...
    def clear(self, scope: ClearScope) -> ClearResult: ...
```

#### 行為對照
| scope | 動作 | 回傳 |
| --- | --- | --- |
| `TODAY` | `store.clear_today()` | `ClearResult(deleted=n, reset_config=False)` |
| `ALL` | `store.clear_all()` | `ClearResult(deleted=n, reset_config=False)` |
| `ALL_AND_RESET` | `store.clear_all()` → `save_config(AppConfig(), config_path)` | `ClearResult(deleted=n, reset_config=True)` |

#### 依賴與注入點
- 注入 `store`（可用真實 `SessionStore` 指向臨時 db）與 `config_path`（臨時檔），完全無 Qt。

#### 測試設計（`tests/test_clear_data.py`）
| 測試 | 重點 |
| --- | --- |
| `test_clear_today_scope` | 呼叫後只刪今日、`reset_config=False` |
| `test_clear_all_scope` | 整表清空 |
| `test_clear_all_and_reset_writes_default_config` | 清空後 `load_config(config_path)` == `AppConfig()`、`reset_config=True` |

### 4.3 M2c — 清除對話框與啟動流程（`src/ui/clear_data_dialog.py`，新）

#### 職責
讓使用者選範圍（預設今日）、對破壞性範圍給警語、做二次確認，然後委派 `ClearDataService` 執行。

#### 介面
```python
class ClearDataDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None: ...
    def selected_scope(self) -> ClearScope: ...   # 預設 ClearScope.TODAY

def run_clear_data_flow(
    parent: QWidget,
    service: ClearDataService,
    on_done: Callable[[ClearResult], None],
) -> None: ...
```

#### UI 規格（`ClearDataDialog`）
- 三個互斥單選（`QRadioButton`）：今日 / 全部 / 全部＋重設；**預設選取今日**。
- 一個 `danger` 樣式警語標籤；當選到「全部＋重設」時顯示（`CLEAR_RESET_WARNING`）。
- 按鈕：確定 / 取消（`QDialogButtonBox`）。`exec()` 回 `Accepted/Rejected`。

#### 流程（`run_clear_data_flow`）
```
dialog = ClearDataDialog(parent)
if dialog.exec() != Accepted: return
scope = dialog.selected_scope()
# 二次確認（FR-2.3）
if QMessageBox.question(parent, CLEAR_DATA_TITLE, CLEAR_CONFIRM_BODY, Yes|No, No) != Yes:
    return
result = service.clear(scope)
QMessageBox.information(parent, CLEAR_DATA_TITLE, CLEAR_DONE.format(count=result.deleted))
if result.reset_config:
    QMessageBox.information(parent, SETTINGS_TITLE, SETTINGS_SAVED_RESTART)  # FR-2.6
on_done(result)   # 觸發主視窗刷新
```

#### 兩處入口與刷新接線（與 INT 章節對應）
- `MainWindow` 新增按鈕 + 訊號 `clear_data_requested = Signal()`（按鈕點擊時 emit）。
- `SettingsWindow` 於「紀錄」分類頁底部新增按鈕 + 訊號 `clear_data_requested = Signal()`。
- `main.py` 將兩個訊號都接到單一處理器：建立 `ClearDataService(store, "config.yaml")` → `run_clear_data_flow(window, service, on_done=lambda _r: window._refresh_base())`（FR-2.5 即時刷新）。
- 入口元件本身**不持有** service，只發出「意圖」訊號 → 解耦。

#### 新增字串（`strings.py`，見 M5 章一併維護）
```
CLEAR_DATA_BUTTON, CLEAR_DATA_TITLE, CLEAR_SCOPE_TODAY, CLEAR_SCOPE_ALL,
CLEAR_SCOPE_RESET, CLEAR_RESET_WARNING, CLEAR_CONFIRM_BODY, CLEAR_DONE
```

#### 測試設計（`tests/test_clear_data_dialog.py`，qt）
| 測試 | 重點 |
| --- | --- |
| `test_dialog_default_scope_is_today` | 開啟後 `selected_scope() == TODAY` |
| `test_dialog_select_all_and_reset` | 勾選第三項 → `selected_scope() == ALL_AND_RESET` 且警語可見 |
| `test_flow_executes_service_on_confirm` | monkeypatch `QMessageBox.question`→Yes、`QDialog.exec`→Accepted；驗證 `service.clear` 以選定 scope 被呼叫、`on_done` 被呼叫 |
| `test_flow_aborts_on_cancel` | exec→Rejected：`service.clear` 不被呼叫 |

> 對話框測試用 fake/spied `ClearDataService`（記錄 `clear` 引數）；不接真實 db。

---

## 5. 需求三：強制休息鎖定

採三層拆分：**M3a 平台呼叫（副作用）→ M3b 決策（純）→ M3c 控制器（Qt 協調）→ M3d 倒數視窗（Qt）**。

### 5.1 M3a — 平台鎖定函式（`src/app/screen_lock.py`，新）

#### 介面
```python
def is_supported() -> bool: ...        # sys.platform == "win32"
def lock_screen() -> bool: ...         # 成功鎖定回 True；非 Windows 回 False（no-op）
```

#### 行為
- `is_supported()`：`sys.platform == "win32"`。
- `lock_screen()`：非 Windows → 記 log 後回 `False`（FR-3.6，不崩潰）；Windows → `ctypes.windll.user32.LockWorkStation()`，回傳布林。

#### 測試設計（`tests/test_screen_lock.py`）
| 測試 | 重點 |
| --- | --- |
| `test_is_supported_matches_platform` | `is_supported() == (sys.platform == 'win32')` |
| `test_lock_screen_noop_off_windows` | 以 `monkeypatch.setattr(screen_lock, "is_supported", lambda: False)` → `lock_screen()` 回 `False`、不丟例外 |

> 真正的 `LockWorkStation` 不在自動測試中呼叫（會鎖住 CI / 開發機）；Windows 路徑靠手動驗收。控制器測試一律注入 fake lock。

### 5.2 M3b — 鎖定決策（`src/app/force_lock.py`，新，純邏輯）

#### 職責
依設定與一連串 `TimerSnapshot`，決定「此刻是否應觸發鎖定」，且每個週期僅觸發一次。**無 Qt、無副作用**。

#### 介面
```python
class ForceLockPolicy:
    def __init__(self, config: ForceLockConfig) -> None: ...
    def observe(self, snap: TimerSnapshot) -> bool: ...   # 該觸發回 True（同一週期只回一次 True）
```

#### 決策規則（狀態：`_fired: bool`；`threshold_sec = overtime_threshold_min * 60`）

通則：`snap.state == SUSPENDED` → 直接回 `False` 且**不更動** `_fired`（暫停期間凍結，避免暫停／恢復造成重複鎖定）。`config.enabled == False` → 永遠 `False`。

| trigger | 觸發條件（回 True 並設 `_fired=True`） | `_fired` 重置（回 False） |
| --- | --- | --- |
| `overtime` | `state==REMINDING` 且 `overtime_sec >= threshold_sec` 且 `not _fired` | 任何非 `REMINDING`、非 `SUSPENDED` 的狀態 |
| `on_rest` | `state==RESTING` 且 `not _fired` | 任何非 `RESTING`、非 `SUSPENDED` 的狀態 |

> 此規則保證：超時持續成長期間（仍 REMINDING）只鎖一次；休息開始只鎖一次；下一個工作 / 休息週期會重置旗標而可再次觸發；暫停不會造成誤觸或重觸。

#### 測試設計（`tests/test_force_lock.py`，純）
以手刻 `TimerSnapshot` 序列餵入：

| 測試 | 序列 → 期望 |
| --- | --- |
| `test_disabled_never_fires` | `enabled=False`，任何序列 → 全 False |
| `test_overtime_fires_once` | REMINDING 超過門檻連續多筆 → 只第一筆 True |
| `test_overtime_resets_next_cycle` | REMINDING(觸發)→RESTING→WORKING→REMINDING(再超門檻) → 第二次 REMINDING 再 True |
| `test_overtime_below_threshold_no_fire` | REMINDING 但 `overtime_sec < threshold` → False |
| `test_on_rest_fires_on_entering_resting` | WORKING→RESTING → 進入 RESTING 當筆 True，後續 RESTING False |
| `test_suspended_does_not_retrigger` | REMINDING(觸發)→SUSPENDED→REMINDING → 第二筆 REMINDING 不再 True |

注入點：直接建構 `ForceLockConfig`，無外部相依。

### 5.3 M3c — 鎖定控制器（`src/app/force_lock_controller.py`，新，Qt）

#### 職責
串接 `worker.timer_updated`（快照）→ `ForceLockPolicy` 決策 → 依 `warning_mode` 執行「立即鎖定」或「倒數警示後鎖定」。

#### 介面
```python
class ForceLockController(QObject):
    def __init__(
        self,
        config: ForceLockConfig,
        *,
        lock_fn: Callable[[], bool] = screen_lock.lock_screen,   # 注入點
        window_factory: Callable[[int, bool], "ForceLockCountdownWindow"] | None = None,
        parent: QObject | None = None,
    ) -> None: ...
    def on_timer_updated(self, snap: TimerSnapshot) -> None: ...   # 接 worker.timer_updated
```

#### 流程
```
on_timer_updated(snap):
    if self._policy.observe(snap):
        self._begin_lock_flow()

_begin_lock_flow():
    mode = config.warning_mode
    if mode == "immediate":
        self._lock_fn()
        return
    cancellable = (mode == "countdown_cancel")
    win = window_factory(config.countdown_sec, cancellable)   # 預設建立 ForceLockCountdownWindow
    win.expired.connect(self._lock_fn)
    win.cancelled.connect(...)    # 僅關閉，不鎖定
    win.start()
    self._countdown_window = win   # 持有參考避免被 GC
```

#### 執行緒注意
`worker.timer_updated` 由偵測執行緒 `emit`，但 `ForceLockController` 屬主執行緒物件 → Qt 以 queued connection 在主執行緒執行 slot，鎖定 / 視窗皆在主執行緒，安全。

#### 依賴與注入點
- `lock_fn`：測試注入記錄呼叫次數的 fake，斷言是否鎖定。
- `window_factory`：測試可注入假視窗（立即 emit `expired`）以驗證倒數路徑而不真的等待。

#### 測試設計（`tests/test_force_lock_controller.py`，qt）
| 測試 | 重點 | 注入 |
| --- | --- | --- |
| `test_immediate_locks_on_trigger` | `warning_mode=immediate` + 觸發快照 → `lock_fn` 被呼叫一次 | fake `lock_fn` + `on_rest` 觸發序列 |
| `test_no_lock_when_policy_not_fired` | 非觸發快照序列 → `lock_fn` 不被呼叫 | fake `lock_fn` |
| `test_countdown_cancel_does_not_lock` | 注入假視窗發出 `cancelled` → `lock_fn` 不被呼叫 | fake `lock_fn` + fake window_factory |
| `test_countdown_expire_locks` | 假視窗發出 `expired` → `lock_fn` 被呼叫 | fake `lock_fn` + fake window_factory |

### 5.4 M3d — 倒數警示視窗（`src/ui/force_lock_window.py`，新，Qt）

#### 介面
```python
class ForceLockCountdownWindow(QWidget):
    expired = Signal()
    cancelled = Signal()
    def __init__(self, seconds: int, cancellable: bool, parent: QWidget | None = None) -> None: ...
    def start(self) -> None: ...
```

#### UI 與行為
- `FramelessWindowHint | WindowStaysOnTop`；置於主螢幕中央。
- 標籤顯示 `FORCE_LOCK_COUNTDOWN.format(seconds=剩餘)`；每秒以 `QTimer` 遞減。
- `cancellable=True` 時顯示「取消本次鎖定」按鈕（`FORCE_LOCK_CANCEL`）→ 點擊 emit `cancelled` 並 `hide()`。
- 倒數到 0 → emit `expired` 並 `hide()`。

#### 測試設計（`tests/test_force_lock_window.py`，qt）
| 測試 | 重點 |
| --- | --- |
| `test_cancel_button_visible_only_when_cancellable` | `cancellable` 決定取消鈕是否存在 |
| `test_emits_cancelled_on_click`（waitSignal） | 點取消 → `cancelled` |
| `test_emits_expired_after_countdown` | `seconds=1` + `start()` → 約 1 秒後 `expired`（`qtbot.waitSignal(timeout=3000)`） |

---

## 6. 需求四：強化提示說明（`src/ui/settings_schema.py`、`src/ui/settings.py`）

### 6.1 M4 — 介面與資料

#### `FieldSpec` 擴充（向後相容）
```python
@dataclass(frozen=True)
class FieldSpec:
    ...                       # 既有欄位不動
    tooltip: str | None = None   # 新增；None → tooltip 回退使用 hint

def tooltip_for(spec: FieldSpec) -> str:   # 新增輔助
    return spec.tooltip or spec.hint
```

#### 內容（FR-4.2 / FR-4.4）
- 擴充既有 hint，並為下列欄位補較長的 `tooltip`（含白話與舉例）：
  - `reminder.method`：popup＝畫面中央彈出視窗；toast＝右下角系統通知；**floating＝畫面角落的小型置頂倒數視窗**。
  - `timer.rest_count_mode`：presence＝必須離開鏡頭才算休息；fixed＝固定倒數、不管在不在座。
  - `reminder.reminding_display_mode`：overtime＝顯示超過工作門檻多久；work_and_reminder＝同時顯示工作時間與提醒持續時間。
  - 其他：ROI、去抖動次數、偵測把握度、最小人體高度比例、運算裝置。
- 需求一、三新增欄位（`reminder.return_sound.*`、`force_lock.*`）同步補上完整 hint 與 tooltip。

#### `SettingsWindow` 套用（`_build_category_page` / `_make_widget`）
- 對每個欄位的輸入元件與標籤呼叫 `setToolTip(tooltip_for(spec))`。
- 「紀錄」分類頁底部加入「清除資料」按鈕（M2c 入口之一），點擊 emit `clear_data_requested`。
- 強制鎖定欄位歸入新分類「強制休息」（`CATEGORIES` 追加），`force_lock.trigger` 依 `overtime/on_rest` 提供下拉、`warning_mode` 提供三選下拉。

### 6.2 測試設計
| 測試（檔） | 重點 |
| --- | --- |
| `test_every_field_has_hint`（`test_settings_schema.py`） | 所有 `SCHEMA` 欄位 `hint` 非空 |
| `test_tooltip_for_falls_back_to_hint`（`test_settings_schema.py`） | `tooltip=None` → `tooltip_for()` 回 hint |
| `test_method_tooltip_mentions_floating`（`test_settings_schema.py`） | `reminder.method` 的 tooltip 含「floating」「角落」等關鍵說明 |
| `test_settings_widgets_have_tooltip`（`test_ui.py`，qt） | 建立 `SettingsWindow` 後抽樣欄位 `widget.toolTip()` 非空 |
| `test_settings_has_clear_button`（`test_ui.py`，qt） | 「紀錄」頁存在清除按鈕並能 emit `clear_data_requested` |

> M4 為純文案 / UI 屬性，不改設定讀寫邏輯（FR-4 行為要點）。

---

## 7. 需求五：修正介面文字錯誤（`src/ui/strings.py`、`src/ui/settings_schema.py`）

### 7.1 M5 — 修正內容
- **FR-5.1**：`settings_schema.py` 的「提醒中顯示」hint
  - 由 `提醒中要顯示》超時時間「還是》工作時間＋提醒持續時間「。`
  - 改為 `提醒中要顯示「超時時間」還是「工作時間＋提醒持續時間」。`
- **FR-5.2 全面掃描**：檢查 `strings.py`、`settings_schema.py` 全部使用者可見字串：
  - 錯字 / 缺字 / 贅字；不成對或誤用的引號（`》`、`「」` 混用）；全形 / 半形不一致。
- **FR-5.3**：只修錯誤呈現，不改語意。

### 7.2 測試設計（`tests/test_strings.py` 擴充）
| 測試 | 重點 |
| --- | --- |
| `test_reminding_display_hint_uses_paired_quotes` | 該 hint 等於修正後字串，且不含 `》` |
| `test_no_stray_angle_quote_in_schema` | 遍歷 `SCHEMA` 的 `label/hint/tooltip`，皆不含 `》` |
| `test_no_stray_angle_quote_in_strings` | 掃描 `strings` 模組所有 `str` 常數不含 `》` |

> 掃描測試可用 `vars(strings)` 取出模組層級 `str` 常數逐一檢查，作為防回歸守門。

---

## 8. INT — 整合與接線（`src/main.py`、`src/ui/main_window.py`）

### 8.1 `MainWindow` 變更
- 新增「清除資料」按鈕（置於今日統計區 `TodaySummaryView` 附近的動作列）。
- 新增訊號 `clear_data_requested = Signal()`，按鈕點擊時 emit。
- 既有 `_refresh_base()` 作為清除後刷新入口（不需新方法）。

### 8.2 `main.py` 接線（啟動時，依設定建立）
```
# 需求一：回來對話框音效（讀設定注入）
return_prompt_dialog = ReturnPromptDialog(return_sound=cfg.reminder.return_sound)

# 需求二：清除資料（單一處理器，兩入口共用）
clear_service = ClearDataService(store, "config.yaml")
def _run_clear_data():
    run_clear_data_flow(window, clear_service, on_done=lambda _r: window._refresh_base())
window.clear_data_requested.connect(_run_clear_data)
settings.clear_data_requested.connect(_run_clear_data)

# 需求三：強制鎖定（僅在 enabled 時建立並接線）
if cfg.force_lock.enabled:
    force_lock_controller = ForceLockController(cfg.force_lock)
    worker.timer_updated.connect(force_lock_controller.on_timer_updated)
```

- `force_lock` 停用時**完全不建立**控制器，零額外負擔（FR-3.1 / 3.7）。
- 各控制器 / 服務在 `main()` 區域變數中持有參考，生命週期同 App。

### 8.3 測試設計
| 測試（`tests/test_main.py` / `tests/test_ui.py`） | 重點 |
| --- | --- |
| `test_main_window_emits_clear_requested`（qt） | 點主視窗清除鈕 → `clear_data_requested` 發出 |
| `test_build_skips_controller_when_force_lock_disabled` | 視 `main` 可測性，驗證停用時不建立控制器（必要時抽出 `_build_force_lock()` 工廠以利測試） |

> 若 `main()` 不易單元測試，將「依設定決定是否建立控制器」抽成可測小工廠 `_maybe_build_force_lock(cfg) -> ForceLockController | None`。

---

## 9. 對既有檔案的異動清單

| 檔案 | 異動 | 模塊 |
| --- | --- | --- |
| `src/config.py` | 新增 `ReturnSoundConfig`、`ForceLockConfig`；掛入 `ReminderConfig`、`AppConfig`；`validate()` / 解析追加 | M0 |
| `src/reminder/sound.py` | 新增 | M1a |
| `src/reminder/return_prompt.py` | 建構子加 `return_sound`/`player`；show/confirm/close 控制播放 | M1b |
| `src/logging_store.py` | 新增 `clear_today` / `clear_all` | M2a |
| `src/app/clear_data.py` | 新增 | M2b |
| `src/ui/clear_data_dialog.py` | 新增 | M2c |
| `src/app/screen_lock.py` | 新增 | M3a |
| `src/app/force_lock.py` | 新增 | M3b |
| `src/app/force_lock_controller.py` | 新增 | M3c |
| `src/ui/force_lock_window.py` | 新增 | M3d |
| `src/ui/settings_schema.py` | `FieldSpec.tooltip`、`tooltip_for`、hint/tooltip 內容、新分類、文字修正 | M4、M5 |
| `src/ui/settings.py` | 套用 tooltip、紀錄頁清除鈕與訊號 | M4、M2c |
| `src/ui/strings.py` | 新增 CLEAR_* / FORCE_LOCK_* 常數；文字修正 | M2c、M3、M5 |
| `src/ui/main_window.py` | 清除鈕與 `clear_data_requested` 訊號 | M2c |
| `src/main.py` | 三項功能接線 | INT |

---

## 10. 風險與邊界情況

1. **暫停（SUSPENDED）與強制鎖定**：M3b 規則明確凍結 `_fired`，避免暫停／恢復誤觸或重觸。
2. **倒數視窗與鎖定競態**：`countdown_only`/`countdown_cancel` 期間若使用者已自行離開→計時器可能轉態，但本次倒數仍走完；倒數結束才鎖定。可接受（不回寫計時，FR-3.5）。視窗需持有參考避免被 GC。
3. **非 Windows**：`lock_screen()` no-op 回 False；控制器照常運作但無實際鎖定，不崩潰。
4. **音效裝置缺失 / 路徑錯誤**：`safe_sound_url` 容錯，靜默不播。
5. **清除＋重設後**：執行中物件仍用舊設定，需提示重啟（FR-2.6）；`config.yaml` 立即為預設值。
6. **`set_value` 三層 key**：`reminder.return_sound.enabled` 為三層，既有 `set_value` 已支援三層深度，沿用即可。

---

## 11. 設計自我審查（需求覆蓋表）

| 需求 | 對應模塊 | 驗收標準覆蓋 |
| --- | --- | --- |
| 一 休息結束音效 | M0、M1a、M1b、INT | 啟用循環播放 / 確認停止 / 關閉不停 / 停用無聲 / 容錯 ✓ |
| 二 清除資料 | M0(reset 用)、M2a、M2b、M2c、M4(設定頁鈕)、INT | 三範圍 / 預設今日 / 二次確認 / 兩入口 / 即時刷新 / 重設提示 ✓ |
| 三 強制鎖定 | M0、M3a、M3b、M3c、M3d、INT | 預設關 / 兩觸發 / 三警示 / 單週期一次 / 非 Win no-op / 不動計時 ✓ |
| 四 提示說明 | M4 | 內嵌 hint＋tooltip / 名詞講清楚 ✓ |
| 五 文字修正 | M5 | 修正已知錯字 / 全面掃描 / 防回歸測試 ✓ |

- **Placeholder 掃描**：本文無 TBD / TODO；介面簽章、資料結構、測試案例均具體。
- **型別一致**：`ReturnSoundConfig`、`ForceLockConfig`、`ClearScope`、`ClearResult`、`ClearDataService`、`LoopingSoundPlayer`、`QtLoopingSoundPlayer`、`ForceLockPolicy`、`ForceLockController`、`ForceLockCountdownWindow`、`screen_lock.lock_screen/is_supported` 全文一致。
- **獨立性**：每模塊有明確注入點（fake player / fake lock_fn / fake window_factory / 臨時 db / 臨時 config_path），可單獨測試。
```
