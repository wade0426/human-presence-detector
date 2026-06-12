# 全系統重新設計 — 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 依 `docs/superpowers/specs/2026-06-12-app-redesign-design.md` 原地重寫整個應用程式：純邏輯核心（等待離席＋升級階梯＋記帳）＋ Qt 薄外殼，功能對等。

**Architecture:** 六角架構 — `src/core/`（零 Qt 純邏輯）、`src/infra/`（config v2 / SQLite v2 / 鎖屏）、`src/shell/`（Qt 外殼）；`src/capture/`、`src/detection/`、`src/presence.py`、`src/duration_format.py` 原樣重用。舊碼（`timer_engine.py`、`app/`、`ui/`、`reminder/`、`config.py`、`logging_store.py`）保持不動直到 W5 切換刪除，期間舊測試持續全綠。

**Tech Stack:** Python 3.11（conda env `project`）、PySide6、pytest、ruff、mypy（strict）。

---

## 規範（所有任務一體適用）

- **TDD**：先寫失敗測試 → 跑確認失敗 → 最小實作 → 跑確認通過。
- **測試指令**（cp950 教訓，沿用上輪）：`$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"; D:\miniconda3\envs\project\python.exe -m pytest <scoped> -q`。任務內只跑自己範圍；全套件由 W5 整合跑。lint/型別：同一 python.exe 跑 `-m ruff check <touched>`、`-m mypy <touched src>`。
- **不操作 git**（使用者自理）。原計畫範本的 commit 步驟以「回報檢查點」取代。
- **只動自己任務擁有的檔案**；舊碼（src/timer_engine.py、src/app/、src/ui/、src/reminder/、src/config.py、src/logging_store.py、src/main.py、src/types.py）在 W5 之前**任何任務不得修改**。
- 必讀：spec（`docs/superpowers/specs/2026-06-12-app-redesign-design.md`）對應章節＋本計畫「鎖定介面」一節＋要移植的舊原始碼。
- 新 UI 文字進 `src/shell/strings.py`（全大寫常數、繁中）。
- pytest 注意：此環境裝有 seleniumbase plugin，禁用 `--timeout` 旗標；Qt 測試沿用現有 offscreen＋conftest 模式。

## 檔案所有權與波次

| 任務 | 波次 | 建立/擁有 | 測試 |
| --- | --- | --- | --- |
| T0 外殼基礎移植 | 1 | `src/shell/__init__.py`、`strings.py`、`theme.py`、`icons.py` | `tests/shell/test_strings.py`、`test_theme.py`、`test_icons.py` |
| T1 核心狀態機 | 1 | `src/core/__init__.py`、`events.py`、`state_machine.py` | `tests/core/test_state_machine.py`、`test_pause.py` |
| T2 升級階梯 | 1 | `src/core/escalation.py` | `tests/core/test_escalation.py` |
| T3 config v2 | 1 | `src/infra/__init__.py`、`config.py` | `tests/infra/test_config.py` |
| T4 store v2＋鎖屏 | 1 | `src/infra/store.py`、`screen_lock.py` | `tests/infra/test_store.py`、`test_screen_lock.py` |
| T5 記帳轉換器 | 2 | `src/core/accounting.py` | `tests/core/test_accounting.py` |
| T6 休息教練覆蓋層 | 2 | `src/shell/overlay.py` | `tests/shell/test_overlay.py` |
| T7 提醒系列移植 | 2 | `src/shell/reminders/`（context/popup/toast/floating/return_prompt/sound/media/factory） | `tests/shell/test_reminders.py`、`test_return_sound.py` |
| T8 偵測 worker | 3 | `src/shell/worker.py` | `tests/shell/test_worker.py` |
| T9 設定頁 v2 | 3 | `src/shell/settings/`（window/schema/cuda/preview）、`src/shell/clear_data.py` | `tests/shell/test_settings.py`、`test_settings_schema.py`、`test_sound_preview.py` |
| T10 主視窗與組裝 | 4 | `src/shell/main_window.py`、`tray.py`、`app.py`、改寫 `src/main.py` | `tests/shell/test_main_window.py`、`test_app.py` |
| T11 切換清理＋整合 | 5 | 刪除全部舊碼與舊測試、瘦身 `src/types.py`、全套件驗證 | 全部 |

衝突規則：同波次任務檔案互斥。T7 依賴 T0 的 strings/theme（同屬不同波 ✓）；T8 依賴 core 全部與 T7 的 ReminderContext；T9 依賴 T3、T0、T7 的 sound player。

## 鎖定介面（跨任務契約，不得擅改名）

### `src/core/events.py`（T1 擁有，逐字實作）

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class TimerState(Enum):
    IDLE = "idle"
    WORKING = "working"
    AWAY = "away"
    REMINDING = "reminding"
    REST_PENDING = "rest_pending"
    RESTING = "resting"
    AWAITING_RETURN = "awaiting_return"
    SUSPENDED = "suspended"  # 僅 snapshot 對外呈現；內部為正交旗標

class TimerEventType(Enum):
    WORK_STARTED = "work_started"
    WORK_ENDED = "work_ended"            # ended_by: reset|rest|rest_pending|interrupted
    REMINDER_TRIGGERED = "reminder_triggered"
    REMINDER_REPEATED = "reminder_repeated"
    REST_PENDING_ENTERED = "rest_pending_entered"
    REST_PENDING_CANCELLED = "rest_pending_cancelled"
    ESCALATED = "escalated"              # stage 1..3，每階升級發一次
    LOCK_REQUESTED = "lock_requested"    # 隨 stage==3 發出，單一工作週期至多一次
    REST_STARTED = "rest_started"
    REST_ENDED = "rest_ended"            # ended_by: ""|interrupted
    REST_INTERRUPTED = "rest_interrupted"
    RETURN_PROMPT = "return_prompt"

class Command(Enum):
    START_REST = "start_rest"
    CANCEL_PENDING = "cancel_pending"
    CONFIRM_RETURN = "confirm_return"

@dataclass(frozen=True)
class TimerEvent:
    type: TimerEventType
    at: float
    duration_sec: float = 0.0
    ended_by: str = ""
    stage: int = -1

@dataclass(frozen=True)
class TimerSnapshot:
    state: TimerState
    work_elapsed_sec: float
    away_elapsed_sec: float
    remaining_to_reminder_sec: float
    reminder_active: bool
    rest_remaining_sec: float
    rest_elapsed_sec: float
    overtime_sec: float
    pending_dwell_sec: float    # REST_PENDING 滯留秒數（非該態為 0）
    escalation_stage: int       # 目前階段 0..3；無階梯情境為 -1
    escalation_dwell_sec: float = 0.0  # 階梯 dwell（兩來源共用、暫停凍結；審查修正 #8 新增）

@dataclass(frozen=True)
class SessionRecord:            # 持久化型別（T4 store / T5 translator 共用）
    kind: str                   # work | rest
    start_ts: float             # = event.at - duration_sec
    end_ts: float
    duration_sec: float
    ended_by: str

@dataclass(frozen=True)
class LedgerEvent:
    ts: float
    type: str                   # TimerEventType.value
    payload: dict[str, object]
```

### `src/core/state_machine.py`（T1）

```python
@dataclass(frozen=True)
class MachineConfig:
    work_threshold_sec: float
    reset_threshold_sec: float
    required_rest_sec: float
    repeat_interval_sec: float
    rest_count_mode: str = "presence"      # presence | fixed
    pending_accounting: str = "work"       # work | none
    interrupt_behavior: str = "remind"     # remind | new_work
    rest_interrupt_after_sec: float = 120.0
    apply_to_reminding: bool = True

class EscalationLike(Protocol):
    @property
    def max_stage(self) -> int: ...
    def stage_for(self, dwell_sec: float) -> int: ...

class RestFlowMachine:
    def __init__(self, cfg: MachineConfig, escalation: EscalationLike) -> None: ...
    def tick(self, present: bool, now: float) -> list[TimerEvent]: ...
    def command(self, cmd: Command, now: float) -> list[TimerEvent]: ...
    def pause(self, now: float) -> None: ...
    def resume(self, now: float) -> None: ...
    def notify_unlocked(self, now: float) -> None: ...  # 解鎖回來：階梯歸零（審查修正 #2/#7 新增）
    def snapshot(self, now: float) -> TimerSnapshot: ...
```

### `src/core/escalation.py`（T2）

```python
class EscalationPolicy:
    def __init__(self, stage_after_sec: tuple[float, float, float], max_stage: int) -> None: ...
    @property
    def max_stage(self) -> int: ...
    def stage_for(self, dwell_sec: float) -> int:
        """dwell<s1→0；≥s1→1；≥s2→2；≥s3→3；回傳值以 max_stage 封頂。"""
```

### `src/core/accounting.py`（T5；`SessionRecord`/`LedgerEvent` 定義於 `core/events.py`，由此 import）

```python
class SessionTranslator:
    def translate(self, event: TimerEvent) -> tuple[SessionRecord | None, LedgerEvent | None]:
        """WORK_ENDED→work session；REST_ENDED→rest session；
        REST_PENDING_ENTERED/CANCELLED、ESCALATED(payload={'stage':n})、
        LOCK_REQUESTED、REST_INTERRUPTED→LedgerEvent；其餘→(None, None)。"""
```

### `src/infra/config.py`（T3）— dataclass 名稱與函式

`AppConfig`（欄位：`source/detection/presence/timer/rest_flow/reminder/logging/ui`，子型別 `SourceConfig`、`DetectionConfig`、`PresenceConfig`、`TimerConfig`、`RestFlowConfig`（含 `EscalationConfig`）、`ReminderConfig`（含 `PopupConfig/FloatingConfig/ReturnSoundConfig`）、`LoggingConfig`、`UiConfig`），值與預設依 spec §8。函式：`load_config(path) -> AppConfig`（缺檔→預設；錯誤→`ConfigError(errors)`）、`save_config(cfg, path)`、`validate(raw) -> list[str]`、`machine_config(cfg) -> MachineConfig`、`escalation_policy(cfg) -> EscalationPolicy`。ROI 用既有 `src/types.py` 的 `BBox`。

### `src/infra/store.py`（T4）

```python
class RecordStore:
    def __init__(self, db_path: str) -> None: ...
    def init_schema(self) -> None: ...   # PRAGMA user_version != 2 → drop 兩表重建
    def log_session(self, rec: SessionRecord) -> None: ...
    def log_event(self, ev: LedgerEvent) -> None: ...     # payload json.dumps
    def today_work_seconds(self, now: datetime | None = None) -> float: ...
    def today_rest_count(self, now: datetime | None = None) -> int: ...
    def clear_today(self, now: datetime | None = None) -> int: ...
    def clear_all(self) -> int: ...
    def close(self) -> None: ...         # per-thread 連線（移植舊 SessionStore 模式）
```

### `src/shell/worker.py` 訊號（T8）

`timer_updated(object)`＝TimerSnapshot、`reminder_show(object)`、`reminder_repeat()`、`return_prompt()`、`lock_requested()`、`rest_pending_entered()`（審查修正 #1/#6 新增：spec §5 stage 0 提示音觸發源）、`connection_status(str)`、`device_fallback(str)`、`failed(str)`。指令槽：`request_start_rest()`、`request_cancel_pending()`、`request_confirm_return()`、`request_pause()`、`request_resume()`、`request_notify_unlocked()`（審查修正 #2/#7 新增：解鎖回來 → 階梯歸零）。建構參數含 `logging_enabled: bool = True`。覆蓋層與主視窗一律由 `timer_updated` 的 snapshot 驅動（state＋escalation_stage＋escalation_dwell_sec／pending_dwell_sec），不另設 overlay 專用訊號；階梯重複音效（EscalationSoundController）同樣以 snapshot 驅動啟停。

### `src/shell/reminders/context.py`（T7）

`ReminderContext` dataclass：自舊 `src/types.py:ReminderContext` 移植（`work_minutes: float` 保持 float——上輪 §4.14 修正不回退）。

---

## Wave 1

### T0：外殼基礎移植

**Files:** Create `src/shell/__init__.py`、`src/shell/strings.py`、`src/shell/theme.py`、`src/shell/icons.py`；Test `tests/shell/`（同名 test 檔）

- [ ] 複製 `src/ui/strings.py` → `src/shell/strings.py`：刪除 force_lock 區塊字串（FORCE_LOCK_*，被階梯吸收）；新增 REST_PENDING／覆蓋層／中斷字串：`REST_PENDING_TITLE = "請離開座位"`、`REST_PENDING_BODY = "休息尚未開始——離開座位後才開始計時。"`、`REST_PENDING_DWELL = "已等待 {duration}"`、`REST_PENDING_CANCEL = "取消休息"`、`LOCK_COUNTDOWN = "{seconds} 秒後鎖定畫面"`、`REST_INTERRUPTED_NOTICE = "休息中斷——你還欠一段休息。"`、`STATUS_REST_PENDING = "等待離席"`。
- [ ] 複製 `src/ui/theme.py` → `src/shell/theme.py`（含上輪 muted/neutral 修正）、`src/ui/icons.py` → `src/shell/icons.py`（含上輪路徑修正）；只改 import 路徑。
- [ ] 移植對應舊測試到 `tests/shell/`（import 改 shell；strings 關鍵字串斷言更新為新常數）。先跑確認紅燈（模組不存在）→ 實作 → 綠燈。
- [ ] 範圍測試＋ruff＋mypy 通過；回報檢查點。

### T1：核心狀態機（本計畫最大宗）

**Files:** Create `src/core/__init__.py`、`src/core/events.py`（逐字依鎖定介面）、`src/core/state_machine.py`；Test `tests/core/test_state_machine.py`、`tests/core/test_pause.py`

實作依據：spec §4 轉移表逐列 ＋ §4.2 中斷 ＋ §4.3 暫停。關鍵語意：

- REST_PENDING 進入（presence 模式 START_REST）：`pending_accounting="work"` 時**不發 WORK_ENDED**、work_elapsed 續計；`"none"` 時當場發 `WORK_ENDED(ended_by="rest_pending")` 並凍結工作累計。離席轉 RESTING 時：work 模式此刻發 `WORK_ENDED(ended_by="rest")`；none 模式不再發（已結算）。
- ESCALATED：滯留（REST_PENDING）或超時（REMINDING，僅 `apply_to_reminding`）的 dwell 經 `stage_for` 升階時發 `ESCALATED(stage=n)`（n≥1，每階一次）；到 3 且本工作週期未鎖過 → 加發 `LOCK_REQUESTED`。進入 REST_PENDING 時階梯歸零重計（按鈕＝善意）；離開觸發態（離席/取消/confirm）歸零。
- 中斷（§4.2，presence 限定）：RESTING 連續在席 ≥ `rest_interrupt_after_sec` 且未滿額 → `REST_ENDED(ended_by="interrupted", duration=已累計)`＋`REST_INTERRUPTED`＋`WORK_STARTED`，`work_elapsed` 初始＝已連續在席秒數；`remind`→ 次態 REMINDING（補發 `REMINDER_TRIGGERED`）、`new_work`→ WORKING。
- 暫停：移植上輪契約（暫停中 tick 回 []；指令直接生效且 resume 不還原狀態；絕對時間戳 resume 平移並 clamp `min(ts+dur, now)`；暫停中 confirm 的 rest_duration 以 `min(now, pause_started_at)` 計）。REST_PENDING 滯留與 REMINDING 超時的階梯 dwell 同樣凍結。

- [ ] 寫 `events.py`（純型別，照鎖定介面逐字）。
- [ ] 失敗測試（轉移表逐列，範例形式）：

```python
def make(mode="presence", acc="work", intr="remind", apply_rem=True, max_stage=3):
    cfg = MachineConfig(work_threshold_sec=10, reset_threshold_sec=6,
                        required_rest_sec=8, repeat_interval_sec=12,
                        rest_count_mode=mode, pending_accounting=acc,
                        interrupt_behavior=intr, apply_to_reminding=apply_rem)
    return RestFlowMachine(cfg, EscalationPolicy((60, 120, 180), max_stage))

def test_start_rest_enters_pending_without_closing_work_session():
    m = make()
    drive_to_reminding(m)                      # helper：tick 有人到超過門檻
    evs = m.command(Command.START_REST, now=20)
    assert types_of(evs) == [TimerEventType.REST_PENDING_ENTERED]
    assert m.snapshot(20).state is TimerState.REST_PENDING

def test_pending_work_keeps_accruing_in_work_mode():
    m = make(); drive_to_reminding(m); m.command(Command.START_REST, 20)
    m.tick(True, 25)
    assert m.snapshot(25).work_elapsed_sec >= 15   # 按鈕後仍續計

def test_pending_leaves_to_resting_closes_session():
    m = make(); drive_to_reminding(m); m.command(Command.START_REST, 20)
    evs = m.tick(False, 30)
    assert [e.type for e in evs] == [TimerEventType.WORK_ENDED, TimerEventType.REST_STARTED]
    assert evs[0].ended_by == "rest"

def test_pending_dwell_escalates_and_requests_lock_once():
    m = make(); drive_to_reminding(m); m.command(Command.START_REST, 20)
    stages = [e.stage for e in m.tick(True, 81) if e.type is TimerEventType.ESCALATED]
    assert stages == [1]
    evs = m.tick(True, 201)
    assert TimerEventType.LOCK_REQUESTED in types_of(evs)
    assert TimerEventType.LOCK_REQUESTED not in types_of(m.tick(True, 240))  # 單週期一次
```

   涵蓋面（每列至少一測）：IDLE/WORKING/AWAY 基本流、reset 隱式休息、REMINDING 重複與 `apply_to_reminding` true/false 兩態、fixed 模式 START_REST 直進 RESTING、REST_PENDING 全路徑（離席/取消/滯留升級/max_stage 封頂/none 記帳）、RESTING 累計與滿額、中斷 remind/new_work 兩態、AWAITING_RETURN/confirm、暫停四情境（移植 tests/test_timer_engine.py 的 29 個既有暫停/基本測試語意到新 API）。
- [ ] 跑紅燈 → 實作 `state_machine.py`（顯式 per-state handler，禁止單一大 if/elif 巨塊：`_tick_idle/_tick_working/...` 方法分派）→ 綠燈。
- [ ] ruff＋mypy（strict）通過；回報檢查點（含轉移表覆蓋清單）。

### T2：升級階梯

**Files:** Create `src/core/escalation.py`；Test `tests/core/test_escalation.py`

- [ ] 失敗測試：邊界（dwell=59.9→0、60→1、120→2、180→3）、max_stage 封頂（max_stage=1 時 dwell=999→1）、max_stage=0 恆 0、建構驗證（非遞增/負值 → ValueError）。
- [ ] 實作（純函式，無狀態）→ 綠燈 → ruff＋mypy。

### T3：config v2

**Files:** Create `src/infra/__init__.py`、`src/infra/config.py`；Test `tests/infra/test_config.py`

- [ ] 失敗測試：預設值完整載入（缺檔→AppConfig() 等於 spec §8 全預設）、round-trip save/load、`version != 2`→預設＋不炸、驗證矩陣（移植上輪 §4.5 嚴格度：roi 畸形/越界、數值欄位型別、enum 欄位、`stage_after_sec` 長度 3/嚴格遞增/正數、`max_stage` 0..3、`pending_accounting`/`interrupt_behavior` enum），全部以 `ConfigError` 列錯不外洩原始例外；`machine_config()`/`escalation_policy()` 對映正確（分→秒換算）。
- [ ] 實作（結構仿舊 src/config.py 的 dataclass＋_from_dict＋validate 模式，但全新 schema）→ 綠燈 → ruff＋mypy。

### T4：store v2＋鎖屏移植

**Files:** Create `src/infra/store.py`、`src/infra/screen_lock.py`；Test `tests/infra/test_store.py`、`tests/infra/test_screen_lock.py`

- [ ] 失敗測試（tmp_path sqlite）：init_schema 建表＋user_version=2；user_version 不符（先手動建 v0 表）→ 重建不炸；log_session/log_event 寫入讀回；today_work_seconds/today_rest_count 只算今日（跨日案例）；clear_today/clear_all 筆數；payload JSON round-trip；per-thread 連線（兩執行緒並用不炸——移植舊 tests/test_logging_store.py 的對應測試）。
- [ ] `screen_lock.py`：複製 `src/app/screen_lock.py`（LockWorkStation ctypes、非 Windows no-op）含其測試。
- [ ] 實作 → 綠燈 → ruff＋mypy。

## Wave 2

### T5：記帳轉換器

**Files:** Create `src/core/accounting.py`；Test `tests/core/test_accounting.py`

- [ ] 失敗測試：WORK_ENDED(duration=300, at=1000)→SessionRecord(kind="work", start_ts=700, end_ts=1000, ended_by 透傳)；REST_ENDED 同理 kind="rest"；ESCALATED→LedgerEvent(type="escalated", payload={"stage": n})；REST_PENDING_ENTERED/CANCELLED/LOCK_REQUESTED/REST_INTERRUPTED→LedgerEvent；WORK_STARTED/REMINDER_*→(None, None)。
- [ ] 實作（無狀態 translate；start_ts = at − duration_sec）→ 綠燈 → ruff＋mypy。

### T6：休息教練覆蓋層

**Files:** Create `src/shell/overlay.py`；Test `tests/shell/test_overlay.py`

API（鎖定）：`RestCoachOverlay(QWidget)`，方法 `update_from_snapshot(snapshot: TimerSnapshot, lock_enabled: bool, stage_after_sec: tuple)`、signal `cancel_requested = Signal()`、`start_rest_requested = Signal()`（審查修正 #3 新增：REMINDING 來源顯示「開始休息（請離席）」鈕——全螢幕遮罩會擋住 popup 的善意出口）。滯留時長兩來源皆讀 `snapshot.escalation_dwell_sec`（審查修正 #8：取代本地時鐘估計）。行為：

- snapshot.state==REST_PENDING 或（REMINDING 且 escalation_stage≥1）→ 顯示；其他狀態 → 隱藏。
- stage 0→小型角落視窗（frameless、置頂、WindowDoesNotAcceptFocus）；stage 1→放大置中；stage 2/3→全螢幕半透明（`WA_TranslucentBackground`，主螢幕 geometry）。
- 內容：`strings.REST_PENDING_TITLE/BODY`、`REST_PENDING_DWELL`（用 `src/duration_format.py`）、lock_enabled 且 stage≥2 時顯示 `LOCK_COUNTDOWN`（剩餘 = stage_after_sec[2] − dwell）；「取消休息」按鈕發 `cancel_requested`（REMINDING 來源時隱藏取消鈕——只有 REST_PENDING 可取消）。
- 鎖屏前（stage 3 snapshot）自行隱藏（spec §10：避免解鎖後殘留遮罩）。

- [ ] 失敗測試：四 stage 幾何型態切換（以 size/windowFlags/可見性斷言）、REST_PENDING→RESTING snapshot 序列導致隱藏、取消鈕 signal、REMINDING 來源無取消鈕、stage3 隱藏。
- [ ] 實作 → 綠燈 → ruff＋mypy。

### T7：提醒系列移植

**Files:** Create `src/shell/reminders/`：`__init__.py`、`context.py`（ReminderContext）、`media.py`、`sound.py`、`popup.py`、`toast.py`、`floating.py`、`return_prompt.py`、`factory.py`；Test `tests/shell/test_reminders.py`、`tests/shell/test_return_sound.py`

- [ ] 自 `src/reminder/*` 與 `src/types.py:ReminderContext` 逐檔移植：import 改 `src.shell.strings`/`src.shell.reminders.*`；popup 的「開始休息」按鈕文案改為 presence 模式時 `"開始休息（請離席）"`（文案常數 `REMIND_START_REST_PRESENCE` 入 strings.py——此為 T0 之外唯一允許 T7 追加 strings 的點，新增於檔尾避免衝突）；其餘行為不變（QtSoundPlayer/QtLoopingSoundPlayer、hide 停音、errorOccurred log 全保留）。
- [ ] 移植對應舊測試（tests/test_reminder.py、test_return_sound.py 全量）到 tests/shell/，import 更新；先紅（模組不存在）後綠。
- [ ] ruff＋mypy 通過；回報檢查點（列出與舊版的任何行為差異，應為僅文案一項）。

## Wave 3

### T8：偵測 worker

**Files:** Create `src/shell/worker.py`；Test `tests/shell/test_worker.py`

- [ ] 以 `src/app/worker.py` 為移植基底（保留：影格新鮮度判定、StreamHealthMonitor 接線、CUDA device_fallback 通知、logging_enabled、暫停 sleep 迴圈、執行緒安全規則），替換核心：`TimerEngine`→`RestFlowMachine`＋`SessionTranslator`＋`RecordStore`（translate 結果非 None 才寫入；`logging_enabled=False` 跳過 store 寫入但 LedgerEvent 仍照 spec 記？——**否**：停用即兩者都不寫，與上輪 §4.8 行為一致）。事件→訊號對映集中單一 `_emit_for(event)` 方法：REMINDER_TRIGGERED/REPEATED→reminder_show/reminder_repeat、RETURN_PROMPT→return_prompt、LOCK_REQUESTED→lock_requested。
- [ ] 失敗測試（移植 tests/test_worker.py 的 LiveFrames/FakeFrames/遞增 timestamp 模式）：凍結影格→停止偵測＋狀態轉換、logging_enabled 兩態、REST_PENDING 指令流（request_start_rest→snapshot 為 REST_PENDING；request_cancel_pending→回 REMINDING）、lock_requested 訊號發出、暫停/恢復。
- [ ] 實作 → 綠燈 → ruff＋mypy。

### T9：設定頁 v2

**Files:** Create `src/shell/settings/`：`__init__.py`、`schema.py`、`window.py`、`cuda.py`、`preview.py`；`src/shell/clear_data.py`；Test `tests/shell/test_settings.py`、`test_settings_schema.py`、`test_sound_preview.py`

- [ ] `schema.py`：以舊 `src/ui/settings_schema.py` 為基底改 v2 鍵空間：分類 `("基本", "偵測", "提醒", "休息流程", "紀錄", "進階")`；移除 force_lock 欄位；新增 `rest_flow.pending_accounting`（CHOICE work/none）、`rest_flow.interrupt_behavior`（CHOICE remind/new_work）、`rest_flow.rest_interrupt_after_sec`（INT）、`rest_flow.escalation.max_stage`（CHOICE "0"/"1"/"2"/"3"）、`rest_flow.escalation.apply_to_reminding`（BOOL）、stage_after_sec 三欄（INT：`stage1_sec/stage2_sec/stage3_sec` 對映 list——`get_value/set_value` 需支援 list 索引對映，schema 內以三個虛擬 key 處理並於存檔時組回 list）；全欄位 hint＋tooltip（繁中、含新名詞白話說明）。
- [ ] `window.py`：移植舊 `src/ui/settings.py`（PathField/SoundPathField/DeviceField/試聽/瀏覽過濾/磁碟基底儲存/驗證錯誤顯示全保留），import 改 infra.config/shell.strings；`cuda.py`、`preview.py` 自舊檔抽出對應元件（CUDA 檢查橋接、試聽控制）以符合單一職責。
- [ ] `clear_data.py`：移植 `src/app/clear_data.py`＋`src/ui/clear_data_dialog.py` 對 `RecordStore` 的對接（clear_today/clear_all/重設設定寫入 v2 預設）。
- [ ] 失敗測試：schema 鍵存在/分類/choices/roundtrip/tooltip 模式（移植舊 test_settings_schema.py 風格）、stage 三欄組回 list、試聽/CUDA 元件回歸（移植上輪測試）、儲存以磁碟為基底。
- [ ] 實作 → 綠燈 → ruff＋mypy。

## Wave 4

### T10：主視窗、托盤與組裝

**Files:** Create `src/shell/main_window.py`、`src/shell/tray.py`、`src/shell/app.py`；Modify `src/main.py`（整檔改寫為 `from src.shell.app import main`）；Test `tests/shell/test_main_window.py`、`tests/shell/test_app.py`

- [ ] `main_window.py`：以舊 `src/ui/main_window.py` 為基底（PreviewView/badge/action bar/今日統計/暫停同步/ROI 磁碟基底全移植，widgets 自 `src/ui/widgets/` 一併移植到 `src/shell/widgets/`——本任務擁有該目錄）；狀態列新增 REST_PENDING 顯示（`STATUS_REST_PENDING ＋ REST_PENDING_DWELL`）與 REST_INTERRUPTED 通知列。
- [ ] `tray.py`：移植舊 tray（含 on_timer_updated/on_connection_status 槽方法慣例）。
- [ ] `app.py`：組裝（移植舊 src/main.py 的接線並改 v2）：ConfigError try/except（stderr＋非零退出）、worker↔window↔overlay↔reminders↔tray 接線（全 QObject slot，禁 lambda）、`lock_requested`→overlay.hide→`screen_lock.lock_workstation()`、`device_fallback`→tray 通知、清除資料雙入口。`src/main.py` 改為三行薄轉發（保住 `python -m src.main` 入口）。
- [ ] 失敗測試：app 組裝 smoke（offscreen 全物件建構＋接線斷言）、REST_PENDING snapshot→狀態列文字＋overlay 顯示、lock_requested 流程（mock screen_lock）、暫停雙入口同步回歸。
- [ ] 實作 → 綠燈 → ruff＋mypy；回報檢查點。

## Wave 5

### T11：切換清理＋整合驗證

**Files:** Delete `src/timer_engine.py`、`src/app/`、`src/ui/`、`src/reminder/`、`src/config.py`、`src/logging_store.py`；Modify `src/types.py`（僅保留 Frame/BBox/DetectionResult 等 capture/detection/presence 仍引用的型別，移除 TimerState/TimerEvent/TimerSnapshot/ReminderContext 等已遷移型別）；Delete 對應舊測試（tests/test_timer_engine.py、test_worker.py、test_ui.py、test_settings_schema.py、test_sound_preview.py、test_reminder.py、test_return_sound.py、test_main.py、test_config.py、test_logging_store.py、test_icons.py、test_theme.py、test_strings.py、test_force_lock*.py、test_screen_lock.py、test_clear_data*.py、test_types.py 中已遷移部分）；config.yaml 改寫為 v2 範例值。

- [ ] 全 repo grep 確認無殘留 import 舊模組（`src.ui`、`src.app`、`src.reminder`、`src.timer_engine`、`src.config`、`src.logging_store`）。
- [ ] 刪除清單執行；`src/types.py` 瘦身後跑 capture/detection/presence 測試確認未破壞。
- [ ] 全套件 `python.exe -m pytest -q` 全綠；`ruff check .` 0；`mypy src` 0。
- [ ] 實機煙霧測試：`python -m src.main` 啟動 10 秒無例外後關閉（驗 config v2 載入與組裝）。
- [ ] 更新 spec 文件狀態為「已實作（待手動驗收）」；回報手動驗收清單（等待離席全流程、覆蓋層四型態、鎖屏、中斷、設定頁新分類）。

---

## 自我審查紀錄

- **Spec 覆蓋**：§4 轉移表→T1；§4.2 中斷→T1；§4.3 暫停→T1；§5 階梯→T2＋T1（發事件）＋T6（呈現）＋T8（lock 訊號）＋T10（鎖屏執行）；§6 記帳→T1（session 邊界）＋T5（轉換）；§7 store→T4；§8 config→T3＋T9（設定頁）；§9 外殼→T6/T7/T8/T9/T10；§10 錯誤處理→T1（非法輸入）/T7（聲音容錯）/T10（ConfigError）/T6（鎖屏前隱藏）；§11 測試→各任務；§12 對等例外→T0（刪 force_lock 字串）/T9（刪欄位）/T11（刪模組）。無缺口。
- **型別一致性**：TimerSnapshot 新欄位（pending_dwell_sec/escalation_stage）在 T1 定義、T6/T10 消費；SessionRecord/LedgerEvent 在 T5 定義、T4 簽名引用（T4 與 T5 同為 W1/W2——T4 在 W1 先行，store 簽名引用 T5 型別會 import 失敗 → **修正**：`SessionRecord`/`LedgerEvent` 移至 T1 的 `core/events.py` 一併定義（純型別檔），T5 只實作 translator，T4 自 events import。已據此更新鎖定介面歸屬：兩個 dataclass 由 T1 在 events.py 檔尾定義，欄位如 T5 節所示。
- **佔位符**：無 TBD/TODO；港接步驟皆指明來源檔與具體變更。
- **git**：依使用者規範以回報檢查點取代 commit 步驟。
