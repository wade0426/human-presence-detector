# 全系統重新設計：休息流程驅動的純核心架構

> 文件狀態：已實作（待手動驗收）
> 日期：2026-06-12
> 適用專案：human-presence-detector（人體辨識休息提醒系統）
> 範圍：整個應用程式原地重寫（同 repo、Python + PySide6、功能對等＋新休息流程）

---

## 1. 動機

presence 模式下按「開始休息」等於「承諾離席」，但系統沒有處理「承諾了卻沒走」：

- 休息卡在 00:00（唯一出口是真的離席滿額）。
- 按鈕當下工作 session 已結算，之後坐著繼續工作的時間**不計入任何地方**——按一下按鈕即可永遠不再被提醒。
- 使用者要求藉此契機重新設計整個應用程式（專案一個月後刪除，允許大膽設計）。

## 2. 決策記錄（與使用者逐項確認）

| # | 決策 | 結論 |
| --- | --- | --- |
| 1 | 重設計範圍 | 整個應用程式 |
| 2 | 未離席處理 | 新增「等待離席」（REST_PENDING）狀態：實際離席才開始計休息 |
| 3 | 等待離席記帳 | 可設定；預設 `work`（工作續計，session 到真正離席才結算） |
| 4 | 升級強度 | 可設定上限；預設分階段升級到鎖屏（max_stage=3） |
| 5 | 功能集 | 對等＋新休息流程 |
| 6 | 技術棧 | Python + PySide6；重用 capture/detection/聲音播放/theme |
| 7 | 資料相容 | 不需要：config v2、DB schema v2，不遷移舊資料 |
| 8 | 品質基準 | 嚴格 TDD＋全面測試（沿用現有水準） |
| 9 | UI 視覺 | 沿用現有深色風格，為新狀態增改元件 |
| 10 | 休息引導 | 升級式覆蓋層（小視窗 → 變大 → 半透明全螢幕「休息教練」） |
| 11 | 重寫位置 | 同 repo 原地重寫（使用者自行先 commit 既有變更；git 全程由使用者控管） |
| 12 | D1 休息中斷 | 可設定；預設 `remind`（退回提醒中，繼續施壓）；替代 `new_work` |
| 13 | D2 統一階梯 | 可設定；預設 `true`（提醒中超時也進同一條升級階梯）；舊「強制休息」功能被階梯吸收 |
| 14 | 架構方案 | A：純邏輯核心＋Qt 外殼（六角架構） |

## 3. 架構總覽

```
src/
├─ core/                # 純 Python，零 Qt import，100% 單元測試
│  ├─ events.py         # 事件與指令型別
│  ├─ state_machine.py  # 狀態機（輸入：PresenceTick / Command）
│  ├─ escalation.py     # 資料驅動升級階梯
│  └─ accounting.py     # 時間記帳簿（work/rest/灰色時段歸帳）
├─ infra/               # 與外界的邊界
│  ├─ config.py         # config v2 載入/驗證/儲存
│  ├─ store.py          # SQLite schema v2（sessions + events）
│  └─ screen_lock.py    # LockWorkStation 包裝（移植現有）
├─ capture/             # ▼ 原樣重用（本輪剛修復完成）
├─ detection/           # ▼ 原樣重用（含 CUDA 檢查與 fallback）
└─ shell/               # Qt 外殼（薄）
   ├─ worker.py         # 偵測執行緒：capture→detect→presence→core.tick
   ├─ main_window.py、tray.py、theme.py、icons.py、strings.py
   ├─ overlay.py        # RestCoachOverlay（新：小/大/全螢幕三型態）
   ├─ reminders/        # popup/toast/floating/return_prompt/sound（移植）
   └─ settings/         # 設定視窗＋schema v2（含 CUDA 檢查、試聽按鈕移植）
```

舊的 `src/timer_engine.py`、`src/app/`、`src/ui/`、`src/reminder/`、`src/config.py`、`src/logging_store.py` 等於重寫完成後刪除。測試鏡像分層：`tests/core/`、`tests/infra/`、`tests/shell/`。

核心運行位置：core 實例存活於 worker 執行緒（同現行模式），事件以 Qt signal 發往主執行緒的 QObject slot（禁止 lambda 接 UI——沿用本輪 §4.6 教訓）。

## 4. 核心狀態機

輸入只有兩種：

- `PresenceTick(present: bool, now: float)` — worker 每偵測週期餵入（present 已經過上游去抖動）。
- `Command` — `START_REST`、`CANCEL_PENDING`、`CONFIRM_RETURN`、`PAUSE`、`RESUME`。

狀態：`IDLE`、`WORKING`、`AWAY`、`REMINDING`、`REST_PENDING`（新）、`RESTING`、`AWAITING_RETURN`；`SUSPENDED` 為正交旗標。

### 4.1 轉移表

| 現態 | 輸入 | 條件 | 次態 | 事件 |
| --- | --- | --- | --- | --- |
| IDLE | tick(有人) | — | WORKING | WORK_STARTED（若有隱式休息追蹤中，先 REST_ENDED） |
| WORKING | tick(有人) | 工作累計 ≥ 門檻 | REMINDING | REMINDER_TRIGGERED |
| WORKING | tick(無人) | — | AWAY | — |
| AWAY | tick(有人) | — | WORKING | — |
| AWAY | tick(無人) | 離席 ≥ reset 門檻 | IDLE | WORK_ENDED(reset)；開始隱式休息追蹤 |
| REMINDING | tick(有人) | 重複間隔到 | REMINDING | REMINDER_REPEATED |
| REMINDING | tick(有人) | `apply_to_reminding` 且超時達階梯門檻 | REMINDING | ESCALATED(n)；n=3 時 LOCK_REQUESTED |
| REMINDING | tick(無人) | — | RESTING | WORK_ENDED(rest)＋REST_STARTED |
| REMINDING | START_REST | presence 模式 | REST_PENDING | REST_PENDING_ENTERED（記帳依 §6） |
| REMINDING | START_REST | fixed 模式 | RESTING | WORK_ENDED(rest)＋REST_STARTED |
| REST_PENDING | tick(無人) | — | RESTING | WORK_ENDED(rest)＋REST_STARTED |
| REST_PENDING | CANCEL_PENDING | — | REMINDING | REST_PENDING_CANCELLED |
| REST_PENDING | tick(有人) | 滯留達階梯門檻 | REST_PENDING | ESCALATED(n)；n=3 時 LOCK_REQUESTED |
| RESTING | tick(無人) | presence 模式 | RESTING | 休息累計 += dt |
| RESTING | tick(有人) | 休息滿額 | AWAITING_RETURN | RETURN_PROMPT |
| RESTING | tick(有人) | 未滿額且連續在席 ≥ `rest_interrupt_after_sec` | 依 `interrupt_behavior`（§4.2） | REST_ENDED(interrupted)＋WORK_STARTED（＋REMINDER_TRIGGERED） |
| RESTING | tick(任意) | fixed 模式：now−開始 ≥ 額度，且有人 | AWAITING_RETURN | RETURN_PROMPT |
| AWAITING_RETURN | CONFIRM_RETURN | — | WORKING | REST_ENDED＋WORK_STARTED |
| 任意 | PAUSE / RESUME | — | SUSPENDED 旗標 | 凍結語意見 §4.3 |

### 4.2 休息中斷（D1，設定 `rest_flow.interrupt_behavior`；僅 presence 模式，fixed 模式倒數不受在席影響、無此機制）

- `remind`（預設）：記 `REST_ENDED(ended_by=interrupted, duration=已累計休息)`，開新工作 session（`work_elapsed` 從「已連續在席時長」起算），直接進 REMINDING（你還欠休息，提醒與 D2 階梯繼續施壓；REST_PENDING 階梯重新從 0 計）。
- `new_work`：同樣結算中斷休息與開新 session，但回 WORKING，等自然到門檻再提醒。

### 4.3 暫停語意（移植，不重新發明）

完整移植本輪剛修好的凍結契約與測試：暫停期間 `update` 不累計、指令直接生效且 resume 不還原狀態（§4.1 教訓）、絕對時間戳於 resume 平移並 clamp（§4.4 教訓）。升級階梯的滯留計時同樣凍結。

## 5. 升級階梯（`core/escalation.py`）

純資料驅動：`EscalationPolicy(stage_after_sec: [s1,s2,s3], max_stage: 0..3)`，輸入「連續滯留時長」輸出當前 stage；stage 變化由狀態機轉成 `ESCALATED(n)` 事件。

| 階段 | 預設觸發 | 外殼動作 |
| --- | --- | --- |
| 0（進入） | 立即 | 小型置頂倒數視窗「請離開座位，休息尚未開始」＋提示音一次 |
| 1 | 滯留 60s | 視窗放大置中＋依 `repeat_interval` 重複音效 |
| 2 | 滯留 120s | 半透明全螢幕「休息教練」覆蓋層（滯留時長、鎖屏倒數） |
| 3 | 滯留 180s | LOCK_REQUESTED → 外殼呼叫 `LockWorkStation()` |

規則：

- 兩個來源共用同一政策實例但**各自獨立計時**：REST_PENDING 滯留、REMINDING 超時（後者僅 `apply_to_reminding=true` 時生效）。按下「開始休息」進入 REST_PENDING 時階梯歸零重計（按鈕視為善意行為）。
- 離開觸發狀態（離席/取消/鎖屏後回來）階梯歸零、覆蓋層立即消失。
- `max_stage` 封頂（0=只有階段 0 提示；3=可鎖屏）。每工作週期鎖屏最多觸發一次（移植舊 force_lock 的單週期防重複規則）。

## 6. 時間記帳（`core/accounting.py`）

- 記帳簿輸出 `SessionRecord(kind, start, end, duration, ended_by)` 與 `LedgerEvent`，由狀態機驅動、infra/store 落盤。
- `pending_accounting`（D 3）：
  - `work`（預設）：REST_PENDING 期間工作 session **保持開啟**、工作與超時續計；真正離席才 `WORK_ENDED(rest)`。取消（CANCEL_PENDING）則 session 無縫延續。
  - `none`：按下按鈕即 `WORK_ENDED(rest_pending)` 結算；滯留為灰色時段，只記 events 不計 sessions。
- `ended_by` 取值：`reset`、`rest`、`rest_pending`、`interrupted`。

## 7. 持久化 v2（`infra/store.py`）

```sql
PRAGMA user_version = 2;
CREATE TABLE sessions(
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('work','rest')),
  start_ts REAL NOT NULL, end_ts REAL NOT NULL,
  duration_sec REAL NOT NULL, ended_by TEXT NOT NULL);
CREATE TABLE events(
  id INTEGER PRIMARY KEY, ts REAL NOT NULL,
  type TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}');
```

- `events` 記錄 REST_PENDING_ENTERED / ESCALATED / REST_INTERRUPTED / LOCK_REQUESTED 等（payload JSON）。
- 今日統計由 sessions 推導（同現行邏輯）。`user_version` 不符 → 直接重建（不遷移；一個月專案）。
- per-thread 連線、`logging.enabled=false` 不寫（保留本輪修正的行為）。

## 8. 設定 v2（`infra/config.py`）

```yaml
version: 2
source:    { type: rtsp, rtsp_url: "", webcam_index: 0, reconnect_interval_sec: 5.0 }
detection: { model_path: data/model/yolov8n.pt, device: auto, confidence: 0.5,
             interval_sec: 1.0, min_box_height_ratio: 0.3 }
presence:  { roi: [0.0, 0.0, 1.0, 1.0], debounce_count: 3 }
timer:     { work_threshold_min: 50.0, reset_threshold_min: 5.0,
             required_rest_min: 10.0, rest_count_mode: presence }
rest_flow:                       # ★ 新區段
  pending_accounting: work       # work | none（D3）
  interrupt_behavior: remind     # remind | new_work（D1）
  rest_interrupt_after_sec: 120
  escalation:
    max_stage: 3                 # 0..3（D4）
    stage_after_sec: [60, 120, 180]   # 嚴格遞增正數
    apply_to_reminding: true     # D2
reminder:  { method: popup, repeat_interval_min: 2.0, reminding_display_mode: overtime,
             popup: { media_path: "", media_type: image, sound_path: "" },
             floating: { position: top-right },
             return_sound: { enabled: false, sound_path: data/assets/Radar.mp3 } }
logging:   { enabled: true, db_path: data/records.sqlite }
ui:        { start_minimized: false }
```

- `force_lock` 區段移除（被階梯吸收；舊 `on_rest` 觸發語意由 REST_PENDING 階梯取代——功能對等的唯一刻意例外，見 §12）。
- 驗證：全欄位型別/值域檢查（沿用本輪 §4.5 的嚴格度），`stage_after_sec` 必須長度 3、嚴格遞增、皆 >0；`version != 2` 或檔案缺失 → 以預設值啟動；格式錯誤 → ConfigError 清楚列出（main 端攔截、stderr、非零退出）。
- 設定頁分類改為：基本／偵測／提醒／**休息流程**（新）／紀錄／進階（移除「強制休息」分類）。CUDA 檢查按鈕與音檔試聽按鈕原樣移植。

## 9. Qt 外殼

- **worker（shell/worker.py）**：移植現行 DetectionWorker 骨架（影格新鮮度、健康監測、CUDA fallback 通知、logging_enabled 全保留），把 TimerEngine 替換為 core 狀態機＋記帳簿；事件→signal 對映集中於一處。
- **RestCoachOverlay（shell/overlay.py，新）**：無框、置頂、三型態（小角落視窗 → 放大置中 → 全螢幕半透明，`WA_TranslucentBackground`）；顯示主畫面（primary screen）；內容：提示文字、滯留時長（讀 snapshot 的階梯 dwell 欄位）、（鎖屏啟用時）鎖屏倒數、「取消休息」按鈕（REST_PENDING 來源，發 CANCEL_PENDING）、「開始休息（請離席）」按鈕（REMINDING 來源，發 START_REST——全螢幕遮罩會擋住 popup 的開始休息鈕，覆蓋層需自備善意出口）。由 snapshot 驅動型態切換，離開觸發狀態即隱藏。
- **階梯音效（shell/app.py EscalationSoundController，新）**：§5 表的聽覺動作——進入 REST_PENDING（stage 0）播提示音一次；stage 1+ 依 `repeat_interval` 重複；離開觸發狀態、暫停或 stage 3 即停。僅 REST_PENDING 來源啟用（REMINDING 的重複音由 popup 負責，不疊加）。
- **解鎖偵測（shell/session_events.py，新）**：Windows WTS session 通知（WM_WTSSESSION_CHANGE / WTS_SESSION_UNLOCK）→ core 階梯歸零重爬（§5「鎖屏後回來」；鎖屏仍單一工作週期至多一次）；非 Windows no-op。
- **提醒視窗（popup/toast/floating）**：照現行移植；popup 的「開始休息」按鈕文案在 presence 模式改為「開始休息（請離席）」。
- **主視窗**：佈局沿用；狀態列新增「等待離席──請離開座位（已等待 mm:ss）」與「休息中斷」顯示；暫停按鈕與托盤同步機制照本輪修正移植。
- **鎖屏**：LOCK_REQUESTED 事件 → 主執行緒 slot → `screen_lock.lock_workstation()`（非 Windows no-op，移植現行）。

## 10. 錯誤處理

- core 為純函式風格：非法輸入（未知指令、負 dt）丟明確例外——由測試保證外殼不會送出。
- 外殼沿用本輪建立的容錯慣例：聲音解碼失敗記 log 靜默、資產缺失走備援、串流斷線顯示狀態並重連、ConfigError 友善退出。
- 覆蓋層在鎖屏前必須先隱藏（避免解鎖後殘留全螢幕遮罩）；解鎖回來視同仍在原狀態繼續判定。

## 11. 測試策略

- `tests/core/`：狀態機轉移表逐列測試（含 REST_PENDING 全路徑、D1 兩種模式、D2 開關、fixed 模式直進）、階梯時序（含凍結）、記帳兩模式的 session 邊界；全部純 Python、無 Qt。
- `tests/infra/`：config v2 驗證矩陣、store v2 讀寫與 user_version 重建。
- `tests/shell/`：沿用現有 Qt 測試模式（offscreen＋注入 FakePlayer/FakeFrames）；overlay 型態切換、事件→UI 對映、CUDA/試聽移植回歸。
- 既有 461 測試中：capture/detection/聲音/設定元件等可重用部分隨模組搬移調整 import；timer_engine 舊測試由 tests/core/ 新測試取代（暫停語意測試逐條移植）。

## 12. 功能對等清單與例外

對等保留：RTSP/webcam＋重連、YOLO 偵測（CUDA 檢查/fallback）、ROI 編輯（含留邊修正）、去抖動、工作/休息計時兩模式、三種提醒、回來音效、歡迎回來對話框、SQLite 紀錄＋今日統計、清除資料、設定頁（含試聽）、托盤、暫停/恢復、開機最小化、鎖屏能力。

刻意例外（已與使用者確認方向）：

1. 舊 `force_lock` 獨立功能（trigger=overtime/on_rest）併入升級階梯：overtime 由 `apply_to_reminding` 覆蓋、on_rest 由 REST_PENDING 階梯取代。
2. config v1 / DB v1 不相容、不遷移。

## 13. 實作分期（後續 writing-plans 依此展開）

1. **W1 core**：events / state_machine / escalation / accounting（純 TDD，最大宗）
2. **W2 infra**：config v2、store v2、screen_lock 移植
3. **W3 shell 骨架**：worker 接 core、main_window 最小可跑、overlay
4. **W4 對等移植**：提醒系列、設定頁（schema v2＋CUDA＋試聽）、托盤、清除資料
5. **W5 整合**：舊碼刪除、全套件驗證、對抗審查、修正

## 14. 非目標

- 不做資料遷移、不做新視覺主題、不做 Web UI、不加音量控制。
- 覆蓋層只處理主螢幕（多螢幕僅主畫面顯示教練層）。
- 不處理 `[h264] co located POCs unavailable`（無害警告）。
