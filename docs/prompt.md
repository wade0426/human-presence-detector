# 人體辨識休息提醒系統 — 自動建構 Prompt

> **用途**：這是 Vibe Coding 的起始 Prompt。將此文件的全部內容貼給 AI 助理，AI 將以「主 Agent」身份全自動完成整個系統的建構，過程中**不需要任何人工介入**。

---

## 你的角色：主 Agent（Main Orchestrator）

你是這個專案的**主協調者**。你的唯一目標是：依序為每個模塊生成「子 Agent 指令」，驅動子 Agent 完成實作、測試與品質檢查，最終讓整個系統可以執行。

**主 Agent 只做三件事**：
1. 讀取 `docs/tasks/progress.md`，確認哪些模塊尚未完成。
2. 按照本文件指定的「模塊執行順序」，為下一個未完成的模塊**生成子 Agent 指令**並啟動子 Agent。
3. 子 Agent 回報後，更新 `docs/tasks/progress.md`，再繼續下一個模塊。

---

## 專案背景

**系統名稱**：人體辨識休息提醒系統  
**平台**：Windows 11 桌面（個人自用）  
**語言**：Python 3.11+，conda 環境名稱 `project`

核心功能：透過攝影機（RTSP 或 webcam）即時判斷使用者是否坐在座位前工作；連續工作達 N 分鐘後提醒休息；離開超過 M 分鐘視為已休息並重置計時。

**完整需求**：`docs/proposal.md`  
**詳細設計**（含介面簽章、演算法虛擬碼、測試要點）：`docs/detailed-design.md`

---

## 現有資源

```
docs/
  proposal.md          需求文檔
  detailed-design.md   詳細設計文檔
  tasks/
    progress.md        模塊完成狀態（主 Agent 維護）
    environment.md     任務：開發環境設置
    types.md           任務：共用資料契約
    config.md          任務：設定管理
    presence.md        任務：在場判定
    timer-engine.md    任務：計時狀態機
    video-source.md    任務：影像來源
    detector.md        任務：人體偵測
    logging-store.md   任務：SQLite 記錄
    worker.md          任務：背景執行緒
    reminder.md        任務：提醒元件
    ui.md              任務：主視窗/設定/系統匣
    main.md            任務：進入點組裝
data/
  model/yolov8n.pt     已備妥的 YOLO 模型
```

---

## 品質關卡（Quality Gates）

每個模塊完成後，**子 Agent 必須全部通過以下三項**才能回報成功：

### 1. pytest
```bash
rtk pytest tests/ -v --tb=short
```
- 所有測試必須通過（0 failures, 0 errors）
- Qt 層測試（worker、reminder、ui）使用 `pytest-qt`

### 2. mypy
```bash
mypy src/ --strict --ignore-missing-imports
```
- 0 errors
- `--ignore-missing-imports`：允許 PySide6、numpy、ultralytics 等無完整 stubs 的套件
- `--strict`：要求所有函數都有型別標注（含回傳型別）

### 3. ruff
```bash
ruff check src/ tests/
```
- 0 errors（warnings 可忽略）
- 若有 auto-fix 的問題：先執行 `ruff check --fix src/ tests/` 再重新確認

### 設定檔要求

在 **environment 模塊**中，子 Agent 必須建立以下設定檔（置於專案根目錄）：

**`pyproject.toml`**（統一管理 mypy / ruff / pytest 設定）：
```toml
[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
ignore = ["B008"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

---

## 模塊執行順序

**嚴格按照以下順序**執行，後面的模塊相依前面的模塊：

```
第 1 批（串行）：
  1. environment   ← 建立專案骨架與設定檔

第 2 批（串行）：
  2. types         ← 共用資料契約，所有模塊的基礎

第 3 批（可並行，但按序執行亦可）：
  3. config        ← 設定 dataclass + YAML I/O
  4. presence      ← 在場判定純邏輯
  5. timer-engine  ← 計時狀態機純邏輯（最複雜，測試最多）

第 4 批（可並行）：
  6. video-source  ← 影像來源封裝
  7. detector      ← YOLOv8 封裝
  8. logging-store ← SQLite 寫入

第 5 批（串行）：
  9. worker        ← 組合核心，背景執行緒

第 6 批（可並行）：
  10. reminder     ← Qt 提醒元件
  11. ui           ← Qt 主視窗/設定/系統匣

第 7 批（串行）：
  12. main         ← 最終組裝 + 手動驗收清單
```

---

## 子 Agent 標準操作流程（SOP）

主 Agent 啟動每個子 Agent 時，必須給子 Agent **完整的獨立指令**，包含以下所有內容：

### 子 Agent 指令模板

```
你是實作「{模塊名稱}」模塊的子 Agent。

## 你的任務
完整實作 {模塊名稱} 模塊，所有任務定義在 docs/tasks/{模塊檔案}.md。

## 必讀文件
- docs/tasks/{模塊檔案}.md（你的任務清單）
- docs/detailed-design.md §{對應章節}（介面簽章與演算法）
- docs/proposal.md §{對應章節}（功能需求）

## 實作要求
1. 完全照 docs/detailed-design.md 的介面簽章實作（函數名、參數名、型別一致）
2. 所有 public 函數/方法都必須有型別標注（mypy --strict 相容）
3. 不寫多餘的 docstring；只在 WHY 非顯而易見時加行內注釋

## 品質關卡（全部通過才算完成）
執行以下命令，每項必須 0 errors：
  rtk pytest tests/test_{模塊}.py -v --tb=short
  mypy src/{路徑} --strict --ignore-missing-imports
  ruff check src/{路徑} tests/test_{模塊}.py

## 錯誤自動修復策略
若任一品質關卡失敗：
  1. 分析錯誤訊息，定位問題
  2. 修復程式碼（不修改測試邏輯，除非測試本身有 bug）
  3. 重新執行品質關卡
  4. 最多重試 3 次；第 3 次仍失敗時，記錄具體錯誤原因並回報「失敗」

## 完成回報格式
完成後，回報：
  狀態：成功 / 失敗
  建立的檔案：[清單]
  測試結果：X passed
  mypy 結果：0 errors
  ruff 結果：0 errors
  失敗原因（若失敗）：[詳細錯誤]
```

---

## 進度追蹤協議

主 Agent 在以下時機更新 `docs/tasks/progress.md`：

- **子 Agent 開始前**：在模塊項目旁加 `(進行中)`
- **子 Agent 成功後**：將 `- [ ]` 改為 `- [x]`
- **子 Agent 失敗後**：在模塊項目旁加 `(失敗: <原因摘要>)`，繼續執行下一個模塊

---

## 各模塊子 Agent 指令

以下為主 Agent 需生成的各模塊完整指令。**主 Agent 按順序逐一啟動子 Agent**，等候回報後再啟動下一個。

---

### 模塊 1：environment

```
你是實作「environment」模塊的子 Agent。

## 你的任務
完整執行 docs/tasks/environment.md 中的所有任務。

## 必讀文件
- docs/tasks/environment.md
- docs/proposal.md §4.3（建議檔案結構）、§8.3（環境）、§9.1（config.yaml）

## 實作要求
建立以下所有內容：
1. environment.yml（conda 環境定義，包含 pyside6、opencv-python、ultralytics、pyyaml、pytest、pytest-qt）
2. config.yaml（照 docs/proposal.md §9.1 的完整預設值）
3. pyproject.toml（包含 mypy、ruff、pytest 設定，照 docs/prompt.md 品質關卡章節的規格）
4. 所有 src/ 子目錄的 __init__.py（src/、src/capture/、src/detection/、src/app/、src/reminder/、src/ui/）
5. tests/__init__.py 和 tests/conftest.py（空 conftest，備用）
6. data/assets/rest_placeholder.png（任意一張小 PNG，可用 Python 的 Pillow 或直接用 bytes 寫入最小 PNG）

## 品質關卡
rtk pytest tests/ --collect-only    ← 應顯示 no tests ran，不報錯
ruff check src/ tests/               ← 空目錄，0 errors

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：[清單]
```

---

### 模塊 2：types

```
你是實作「types」模塊的子 Agent。

## 你的任務
完整執行 docs/tasks/types.md 中的所有任務。

## 必讀文件
- docs/tasks/types.md
- docs/detailed-design.md §4（共用資料契約）

## 實作要求
建立 src/types.py，包含：
- BBox(frozen dataclass)：x, y, w, h: float，center property 回傳 tuple[float, float]
- Detection(frozen dataclass)：bbox: BBox, confidence: float
- Frame(frozen dataclass)：image: np.ndarray, width: int, height: int, timestamp: float
- TimerState(Enum)：IDLE / WORKING / PAUSED / REMINDING
- ResetMode(Enum)：DETECTION / DISMISS / SNOOZE
- TimerEventType(Enum)：WORK_STARTED / WORK_ENDED / REST_ENDED / REMINDER_TRIGGERED / REMINDER_REPEATED
- TimerEvent(frozen dataclass)：type: TimerEventType, at: float, duration_sec: float = 0.0, ended_by: str = ""
- TimerSnapshot(frozen dataclass)：state: TimerState, work_elapsed_sec: float, away_elapsed_sec: float, remaining_to_reminder_sec: float, reminder_active: bool
- ReminderContext(frozen dataclass)：work_minutes: int, media_path: str, media_type: str, sound_path: str

建立 tests/test_types.py，測試：
- BBox(0.0, 0.0, 1.0, 1.0).center == (0.5, 0.5)
- BBox(0.1, 0.2, 0.4, 0.6).center == (0.3, 0.5)（誤差 < 1e-9）
- BBox 為 frozen（修改 x 引發 dataclasses.FrozenInstanceError）

## 品質關卡
rtk pytest tests/test_types.py -v --tb=short
mypy src/types.py --strict --ignore-missing-imports
ruff check src/types.py tests/test_types.py

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：src/types.py、tests/test_types.py
測試結果：X passed
mypy 結果：0 errors
ruff 結果：0 errors
失敗原因（若失敗）：[詳細錯誤]
```

---

### 模塊 3：config

```
你是實作「config」模塊的子 Agent。

## 你的任務
完整執行 docs/tasks/config.md 中的所有任務。

## 必讀文件
- docs/tasks/config.md
- docs/detailed-design.md §5.1（config.py 設計）
- docs/proposal.md §9.1（config.yaml 結構）

## 實作要求
建立 src/config.py，包含：
- 所有 Config dataclass（SourceConfig、DetectionConfig、PresenceConfig、TimerConfig、
  PopupConfig、FloatingConfig、ReminderConfig、LoggingConfig、UIConfig、AppConfig）
- class ConfigError(Exception): pass
- validate(raw: dict) -> list[str]
- load_config(path: str) -> AppConfig
- save_config(config: AppConfig, path: str) -> None

關鍵型別轉換：
- YAML 中 roi 為 list [x, y, w, h] ↔ BBox
- YAML 中 reset_mode 為字串 ↔ ResetMode

建立 tests/test_config.py，必須涵蓋：
- 路徑不存在 → 回傳全預設 AppConfig
- YAML 缺 detection 區塊 → 以預設補齊
- confidence=2.0 → validate 回傳含 confidence 的錯誤
- source.type='x' → validate 回傳錯誤
- source.type='rtsp' 且 rtsp_url='' → validate 回傳錯誤
- round-trip：save_config 後 load_config 結果一致

## 品質關卡
rtk pytest tests/test_config.py -v --tb=short
mypy src/config.py --strict --ignore-missing-imports
ruff check src/config.py tests/test_config.py

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：src/config.py、tests/test_config.py
測試結果：X passed
mypy 結果：0 errors
ruff 結果：0 errors
失敗原因（若失敗）：[詳細錯誤]
```

---

### 模塊 4：presence

```
你是實作「presence」模塊的子 Agent。

## 你的任務
完整執行 docs/tasks/presence.md 中的所有任務。

## 必讀文件
- docs/tasks/presence.md
- docs/detailed-design.md §5.4（PresenceEvaluator 設計）
- docs/proposal.md §3 FR-3（在場判定需求）

## 實作要求
建立 src/presence.py，實作 PresenceEvaluator：

class PresenceEvaluator:
    def __init__(self, roi: BBox, min_box_height_ratio: float, debounce_count: int) -> None
    def update(self, detections: list[Detection]) -> bool
    def set_roi(self, roi: BBox) -> None
    @property
    def stable_present(self) -> bool

去抖動邏輯（照詳細設計虛擬碼）：
- raw = any(_qualifies(d) for d in detections)
- raw == stable → 清除 pending
- raw != stable → 累計 pending；達 debounce_count 次才翻轉 stable

建立 tests/test_presence.py，必須涵蓋：
- 連續 debounce_count-1 次反訊號不翻轉；第 debounce_count 次翻轉
- ROI 邊界：center 剛好在左邊界 → 在場；超出右邊界 → 不在場
- 大小門檻：bbox.h == min_box_height_ratio → 在場；< 則不在場
- 空 detections（離開信號）需達去抖動次數才切換
- 多偵測：其中一個合格即在場
- set_roi 後以新 ROI 判定

## 品質關卡
rtk pytest tests/test_presence.py -v --tb=short
mypy src/presence.py --strict --ignore-missing-imports
ruff check src/presence.py tests/test_presence.py

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：src/presence.py、tests/test_presence.py
測試結果：X passed
mypy 結果：0 errors
ruff 結果：0 errors
失敗原因（若失敗）：[詳細錯誤]
```

---

### 模塊 5：timer-engine

```
你是實作「timer-engine」模塊的子 Agent。
這是系統最核心的模塊，請仔細閱讀詳細設計文檔後再實作。

## 你的任務
完整執行 docs/tasks/timer-engine.md 中的所有任務。

## 必讀文件
- docs/tasks/timer-engine.md
- docs/detailed-design.md §5.5（TimerEngine 完整設計與虛擬碼）
- docs/proposal.md §6（計時狀態機詳述，含狀態轉移表）

## 實作要求
建立 src/timer_engine.py，實作 TimerEngine：

class TimerEngine:
    def __init__(self, work_threshold_sec: float, reset_threshold_sec: float,
                 required_rest_sec: float, reset_mode: ResetMode,
                 repeat_interval_sec: float, snooze_sec: float) -> None
    def update(self, present: bool, now: float) -> list[TimerEvent]
    def on_reminder_dismissed(self, now: float) -> list[TimerEvent]
    def snapshot(self, now: float) -> TimerSnapshot
    @property
    def state(self) -> TimerState

內部狀態（全部需要）：
  _state, _work_elapsed, _last_t, _away_since, _rest_start_t,
  _work_start_t, _reminder_last_t, _snooze_until

所有狀態轉移嚴格對應 docs/proposal.md §6.2 的轉移表。
update 的虛擬碼完整實作在 docs/detailed-design.md §5.5。

建立 tests/test_timer_engine.py，使用注入 now 參數（不依賴真實時鐘），必須涵蓋：
1. 在場累計達 N → REMINDER_TRIGGERED
2. 短暫離開（< M）→ 回來後 work_elapsed 不含離開時間
3. 離開達 M → WORK_ENDED(ended_by='reset') + REST_ENDED + WORK_STARTED
4. 模式1(DETECTION)：提醒後在場每 repeat_interval 收到 REMINDER_REPEATED；離開達 R → WORK_ENDED(ended_by='rest_done')
5. 模式2(DISMISS)：on_reminder_dismissed → WORK_ENDED(ended_by='dismiss') + WORK_STARTED
6. 模式3(SNOOZE)：貪睡期不再提醒；到期後再 REMINDER_REPEATED；離開達 R 真正重置
7. snapshot 各欄位在各狀態下正確

## 品質關卡
rtk pytest tests/test_timer_engine.py -v --tb=short
mypy src/timer_engine.py --strict --ignore-missing-imports
ruff check src/timer_engine.py tests/test_timer_engine.py

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：src/timer_engine.py、tests/test_timer_engine.py
測試結果：X passed
mypy 結果：0 errors
ruff 結果：0 errors
失敗原因（若失敗）：[詳細錯誤]
```

---

### 模塊 6：video-source

```
你是實作「video-source」模塊的子 Agent。

## 你的任務
完整執行 docs/tasks/video-source.md 中的所有任務。

## 必讀文件
- docs/tasks/video-source.md
- docs/detailed-design.md §5.2（VideoSource 設計）
- docs/proposal.md FR-1（影像來源需求）

## 實作要求
建立 src/capture/video_source.py，包含：
- VideoSource(Protocol)：open/read/release/is_opened
- WebcamSource：cv2.VideoCapture(index)
- RTSPSource：cv2.VideoCapture(url, cv2.CAP_FFMPEG)
- ReconnectingSource：包裝任一 VideoSource，read 失敗自動重連（clock 可注入）
- create_source(cfg: SourceConfig, clock=time.monotonic) -> VideoSource

建立 tests/test_video_source.py，使用假 inner source（不碰真實攝影機）：
- 定義 FakeSource 類別實作 VideoSource Protocol，可控制 open/read/release 行為
- inner 未開啟 → 第一次 read 觸發 open
- open 失敗（raise Exception）→ 回 None，重試受 reconnect_interval 限制
- inner.read() 回 None → 呼叫 release
- create_source type='webcam' → ReconnectingSource wrapping WebcamSource
- create_source type='rtsp' → ReconnectingSource wrapping RTSPSource

## 品質關卡
rtk pytest tests/test_video_source.py -v --tb=short
mypy src/capture/video_source.py --strict --ignore-missing-imports
ruff check src/capture/video_source.py tests/test_video_source.py

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：src/capture/video_source.py、tests/test_video_source.py
測試結果：X passed
mypy 結果：0 errors
ruff 結果：0 errors
失敗原因（若失敗）：[詳細錯誤]
```

---

### 模塊 7：detector

```
你是實作「detector」模塊的子 Agent。

## 你的任務
完整執行 docs/tasks/detector.md 中的所有任務。

## 必讀文件
- docs/tasks/detector.md
- docs/detailed-design.md §5.3（PersonDetector 設計）
- docs/proposal.md FR-2（人體偵測需求）

## 實作要求
建立 src/detection/detector.py，包含：

class PersonDetector:
    def __init__(self, model_path: str, confidence: float, device: str = "auto") -> None
    def detect(self, frame: Frame) -> list[Detection]
    def _infer(self, image: Any) -> list[tuple[float, float, float, float, float]]

重要：
- model 延遲載入（__init__ 不載模型，detect 第一次呼叫時才載）
- _infer 是測試縫（seam），單元測試 mock 此方法
- _resolve_device：auto → cuda if torch.cuda.is_available() else cpu

建立 tests/test_detector.py，用 unittest.mock.patch.object mock _infer：
- mock 回 [(100, 50, 300, 400, 0.85)]，frame 500×600 → BBox(0.2, 0.0833, 0.4, 0.5833) 誤差 < 1e-4
- mock 回 [] → detect 回 []
- _resolve_device('cpu') → 'cpu'
- _resolve_device('auto') 在無 CUDA 環境 → 'cpu'

## 品質關卡
rtk pytest tests/test_detector.py -v --tb=short
mypy src/detection/detector.py --strict --ignore-missing-imports
ruff check src/detection/detector.py tests/test_detector.py

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：src/detection/detector.py、tests/test_detector.py
測試結果：X passed
mypy 結果：0 errors
ruff 結果：0 errors
失敗原因（若失敗）：[詳細錯誤]
```

---

### 模塊 8：logging-store

```
你是實作「logging-store」模塊的子 Agent。

## 你的任務
完整執行 docs/tasks/logging-store.md 中的所有任務。

## 必讀文件
- docs/tasks/logging-store.md
- docs/detailed-design.md §5.6（SessionStore 設計）
- docs/proposal.md §9.2（SQLite Schema）

## 實作要求
建立 src/logging_store.py，實作 SessionStore：

class SessionStore:
    def __init__(self, db_path: str) -> None
    def init_schema(self) -> None          # CREATE TABLE IF NOT EXISTS，可重複呼叫
    def log_session(self, type: str, start_ts: datetime, end_ts: datetime,
                    duration_sec: int, ended_by: str) -> int   # 回傳 row id
    def close(self) -> None

注意：SQLite 連線具執行緒親和性，SessionStore 僅在建立它的執行緒中使用。

建立 tests/test_logging_store.py，使用 db_path=':memory:'：
- init_schema 可重複呼叫兩次不報錯
- log_session('work', start, end, 1800, 'reset') 後 SELECT 回相同欄位
- log_session('rest', ...) type 欄位為 'rest'
- 回傳 row id 為正整數

## 品質關卡
rtk pytest tests/test_logging_store.py -v --tb=short
mypy src/logging_store.py --strict --ignore-missing-imports
ruff check src/logging_store.py tests/test_logging_store.py

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：src/logging_store.py、tests/test_logging_store.py
測試結果：X passed
mypy 結果：0 errors
ruff 結果：0 errors
失敗原因（若失敗）：[詳細錯誤]
```

---

### 模塊 9：worker

```
你是實作「worker」模塊的子 Agent。

## 你的任務
完整執行 docs/tasks/worker.md 中的所有任務。

## 必讀文件
- docs/tasks/worker.md
- docs/detailed-design.md §5.7（DetectionWorker 設計）、§6.1（偵測主迴圈時序）

## 實作要求
建立 src/app/worker.py，實作 DetectionWorker(QObject)：

Signals：
  frame_ready = Signal(object)        # Frame
  presence_changed = Signal(bool)
  timer_updated = Signal(object)      # TimerSnapshot
  reminder_show = Signal(object)      # ReminderContext
  reminder_repeat = Signal(object)    # ReminderContext
  connection_status = Signal(str)     # 'connected' | 'reconnecting'

Methods：
  __init__(source, detector, presence_evaluator, timer_engine, store,
           detection_interval_sec, reminder_context, clock=time.monotonic)
  run() -> None          # 主迴圈，放入 QThread 執行
  stop() -> None
  pause() -> None
  resume() -> None
  dismiss_reminder() -> None    # 呼叫 timer_engine.on_reminder_dismissed
  set_roi(roi: BBox) -> None    # 呼叫 presence_evaluator.set_roi

_dispatch(ev) 對應關係：
  REMINDER_TRIGGERED → emit reminder_show
  REMINDER_REPEATED  → emit reminder_repeat
  WORK_STARTED       → 記錄 _work_start_dt
  WORK_ENDED         → store.log_session('work', ...)
  REST_ENDED         → store.log_session('rest', ...)

建立 tests/test_worker.py（pytest-qt），使用假 source/detector：
- 假 source 回固定 Frame，假 detector 回 [] → 3 圈後收到 frame_ready signal
- source.read() 回 None → 發出 connection_status='reconnecting'，不崩潰
- 假 detector 回符合 ROI 的 Detection + 計時超過 N → 發出 reminder_show

## 品質關卡
rtk pytest tests/test_worker.py -v --tb=short
mypy src/app/worker.py --strict --ignore-missing-imports
ruff check src/app/worker.py tests/test_worker.py

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：src/app/worker.py、tests/test_worker.py
測試結果：X passed
mypy 結果：0 errors
ruff 結果：0 errors
失敗原因（若失敗）：[詳細錯誤]
```

---

### 模塊 10：reminder

```
你是實作「reminder」模塊的子 Agent。

## 你的任務
完整執行 docs/tasks/reminder.md 中的所有任務。

## 必讀文件
- docs/tasks/reminder.md
- docs/detailed-design.md §5.8（reminder 設計）
- docs/proposal.md FR-5（提醒需求）、FR-6（重置邏輯）

## 實作要求
建立以下檔案：

src/reminder/base.py：
  class Reminder(Protocol)：dismissed: Signal, show(ctx: ReminderContext), hide()

src/reminder/popup.py：
  class PopupReminder(QDialog)：
  - media_type='image' → QLabel + QPixmap
  - media_type='video' → QMediaPlayer + QVideoWidget
  - sound_path 非空 → QSoundEffect
  - 「我要休息」按鈕 → emit dismissed

src/reminder/toast.py：
  class ToastReminder：QSystemTrayIcon.showMessage，emit dismissed 立即

src/reminder/floating.py：
  class FloatingReminder(QWidget)：
  - FramelessWindowHint | WindowStaysOnTopHint
  - QTimer 每秒更新倒數，到零閃爍/變色

src/reminder/factory.py：
  def create_reminder(cfg: ReminderConfig, tray: Optional[QSystemTrayIcon] = None) -> Reminder

建立 tests/test_reminder.py（pytest-qt）：
- create_reminder 依 method 回正確型別
- PopupReminder.show(ctx) media_type='image' 不崩潰
- 點擊「我要休息」按鈕發出 dismissed signal

## 品質關卡
rtk pytest tests/test_reminder.py -v --tb=short
mypy src/reminder/ --strict --ignore-missing-imports
ruff check src/reminder/ tests/test_reminder.py

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：src/reminder/{base,popup,toast,floating,factory}.py、tests/test_reminder.py
測試結果：X passed
mypy 結果：0 errors
ruff 結果：0 errors
失敗原因（若失敗）：[詳細錯誤]
```

---

### 模塊 11：ui

```
你是實作「ui」模塊的子 Agent。

## 你的任務
完整執行 docs/tasks/ui.md 中的所有任務。

## 必讀文件
- docs/tasks/ui.md
- docs/detailed-design.md §5.9（UI 設計）
- docs/proposal.md FR-7（主視窗）、FR-8（系統匣）、FR-9（設定）

## 實作要求
建立以下檔案：

src/ui/main_window.py：
  class MainWindow(QMainWindow)：
  - roi_changed = Signal(object)  # BBox
  - on_frame_ready(frame: Frame)：BGR→RGB→QImage→QPixmap，疊加偵測框/ROI/計時
  - on_timer_updated(snapshot: TimerSnapshot)：更新狀態與計時 label
  - on_presence_changed(present: bool)
  - on_connection_status(status: str)
  - ROI 拖拉：mousePressEvent/mouseMoveEvent/mouseReleaseEvent，emit roi_changed(BBox)
  - closeEvent：hide()（最小化至系統匣）

src/ui/settings.py：
  class SettingsDialog(QDialog)：
  - config_changed = Signal(object)  # AppConfig
  - 表單含所有設定欄位，儲存呼叫 save_config + emit config_changed
  - 驗證失敗顯示 QMessageBox

src/ui/tray.py：
  class TrayIcon(QSystemTrayIcon)：
  - 選單：開啟主視窗 / 暫停·繼續 / 設定 / 結束
  - update_status(state: TimerState)：更新 tooltip

建立 tests/test_ui.py（pytest-qt）：
- MainWindow(config) 可建立不崩潰
- ROI 拖拉換算：press(10,20)→release(110,120) 在 500×400 label → BBox 誤差 < 0.01
- SettingsDialog(config) 可建立不崩潰
- TrayIcon 可建立不崩潰

## 品質關卡
rtk pytest tests/test_ui.py -v --tb=short
mypy src/ui/ --strict --ignore-missing-imports
ruff check src/ui/ tests/test_ui.py

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：src/ui/{main_window,settings,tray}.py、tests/test_ui.py
測試結果：X passed
mypy 結果：0 errors
ruff 結果：0 errors
失敗原因（若失敗）：[詳細錯誤]
```

---

### 模塊 12：main

```
你是實作「main」模塊的子 Agent。

## 你的任務
完整執行 docs/tasks/main.md 中的所有任務。

## 必讀文件
- docs/tasks/main.md
- docs/detailed-design.md §5.10（main.py 虛擬碼）、§6（主要時序）
- docs/proposal.md §11（MVP 驗收標準）

## 實作要求
建立 src/main.py，組裝所有模塊（照 docs/detailed-design.md §5.10 的虛擬碼）：

1. QApplication
2. load_config("config.yaml")
3. 建立 source / detector / presence / timer / store / ctx
4. 建立 DetectionWorker，moveToThread(QThread)
5. 建立 MainWindow / TrayIcon / reminder
6. 完成所有 signal → slot 接線（照詳細設計 §5.10）
7. thread.start()，依 start_minimized 決定顯示方式
8. if __name__ == '__main__': main()

接線清單（不可遺漏）：
  worker.frame_ready → window.on_frame_ready
  worker.presence_changed → window.on_presence_changed
  worker.timer_updated → window.on_timer_updated
  worker.connection_status → window.on_connection_status
  worker.reminder_show → reminder.show
  worker.reminder_repeat → reminder.show
  reminder.dismissed → worker.dismiss_reminder
  window.roi_changed → worker.set_roi
  tray 選單的暫停/繼續 → worker.pause/resume
  tray 選單的設定 → 開啟 SettingsDialog
  settings.config_changed → worker 重新套用設定
  app.aboutToQuit → worker.stop

## 品質關卡
mypy src/main.py --strict --ignore-missing-imports
ruff check src/main.py

（main.py 不需自動化 pytest；以手動啟動 python src/main.py 驗收）

完成後輸出 MVP 驗收清單（docs/proposal.md §11 的 8 項），讓使用者手動確認。

## 完成回報格式
狀態：成功 / 失敗
建立的檔案：src/main.py
mypy 結果：0 errors
ruff 結果：0 errors
待手動驗收項目：[列出 proposal.md §11 的 8 項]
失敗原因（若失敗）：[詳細錯誤]
```

---

## 開始執行

**主 Agent，請現在開始執行：**

1. 讀取 `docs/tasks/progress.md` 確認初始狀態
2. 讀取 `docs/detailed-design.md` 和 `docs/proposal.md` 建立全局理解
3. 從模塊 1（environment）開始，依序啟動子 Agent
4. 每完成一個模塊，更新 `docs/tasks/progress.md`
5. 所有 12 個模塊完成後，輸出最終總結報告，包含：
   - 每個模塊的狀態（成功/失敗）
   - 總測試數與通過數
   - 任何需要人工確認的事項

**執行過程中不需要任何人工回覆，全程自動完成。**
