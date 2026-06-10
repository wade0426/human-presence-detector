# 需求文檔：休息提醒系統功能擴充

> 文件狀態：草案（待實作）
> 適用專案：human-presence-detector（人體辨識休息提醒系統）

---

## 0. 背景與目標

本次擴充新增五項功能，目的在於：

1. 休息結束時主動以音效提醒使用者回到工作。
2. 提供清除歷史紀錄（與重設設定）的入口。
3. 對工作過久者提供「強制休息」鎖定畫面（`win+L`，僅限 Windows）。
4. 強化設定畫面的提示說明，降低使用者理解門檻。
5. 修正介面文字的錯字與標點錯誤。

本文件僅定義需求與驗收標準，**不包含實作程式碼**，且**不需 commit 至 git**。

### 0.1 名詞對照

| 名詞 | 說明 |
| --- | --- |
| 在場 / 離場 | 由鏡頭＋YOLO 偵測 ROI 內是否有人，經去抖動後判定。 |
| ROI | Region of Interest，偵測區域（畫面中要判定有無人的方框）。 |
| popup / toast / floating | 三種提醒呈現方式：彈出視窗 / 系統通知 / 置頂懸浮倒數。 |
| presence / fixed | 休息計算方式：必須離座才算休息 / 固定倒數。 |
| overtime | 超時，`work_elapsed - work_threshold`，僅在「提醒中」有意義。 |
| 歡迎回來對話框 | 休息完成後彈出、需手動確認的 `ReturnPromptDialog`。 |

### 0.2 現況摘要（與本需求相關）

- 休息完成（`TimerState.AWAITING_RETURN`）時，`main.py` 已串接 `worker.return_prompt → ReturnPromptDialog.show_prompt`，會彈出「歡迎回來」對話框，但**目前沒有音效**。
- 紀錄寫入 SQLite `sessions` 表（`src/logging_store.py::SessionStore`），**目前沒有清除介面**。
- **目前沒有任何鎖定畫面 / 強制休息機制**。
- 設定畫面已有內嵌 hint（`src/ui/settings_schema.py`），但部分名詞（如 `floating`）說明不足，且**無 tooltip**。
- 已知文字錯誤：`src/ui/settings_schema.py:153`，「提醒中顯示」hint 使用了錯誤引號 `》…「`。

---

## 需求一：休息結束音效（回到工作提醒）

### 1.1 目標

休息完成、彈出「歡迎回來」對話框時，以音效主動提醒使用者回到工作。功能可選，預設關閉。

### 1.2 功能需求

- **FR-1.1** 當「歡迎回來」對話框出現時，若功能啟用，開始播放提醒音效。
- **FR-1.2** 音效採**循環播放**，直到使用者按下「開始新一輪」（確認）按鈕後立即停止。
- **FR-1.3** 對話框被忽略 / 失焦時音效**不停止**（沿用對話框「只能由確認鈕關閉」的既有行為）。
- **FR-1.4** 功能可由設定開關，並可自訂音檔路徑；預設音檔為 `data/assets/Radar.mp3`。
- **FR-1.5** 預設**關閉**（opt-in）。
- **FR-1.6** 音檔路徑無效或不存在時，安靜地不播放（不可崩潰，沿用 `safe_sound_url` 的容錯精神）。

### 1.3 設定欄位（新增）

於 `ReminderConfig` 下新增子設定 `return_sound`：

```yaml
reminder:
  return_sound:
    enabled: false                      # 預設關閉
    sound_path: data/assets/Radar.mp3   # 預設音檔
```

- 對應新增 `@dataclass ReturnSoundConfig`（`enabled: bool = False`、`sound_path: str = "data/assets/Radar.mp3"`）。
- `settings_schema.py` 於「提醒」分類新增兩個欄位：`reminder.return_sound.enabled`（BOOL）、`reminder.return_sound.sound_path`（PATH）。
- 由於 `set_value` 目前支援至三層 key（`reminder.return_sound.enabled` 為三層），需確認巢狀讀寫可正確運作。

### 1.4 行為與實作要點

- `ReturnPromptDialog` 內建一個 `QSoundEffect`，`setLoopCount(QSoundEffect.Infinite)`；`show_prompt()` 啟用時 `play()`，確認（`_on_confirmed`）與關閉時 `stop()`。
- 啟用旗標與音檔路徑由 `main.py` 在建立對話框時注入（讀自 `cfg.reminder.return_sound`）。

### 1.5 驗收標準

- 啟用後，休息完成 → 對話框出現同時開始循環播放，按「開始新一輪」立即靜音。
- 關閉時無任何音效。
- 音檔不存在時不播放、不崩潰。

---

## 需求二：清除資料

### 2.1 目標

提供清除歷史工作／休息紀錄的入口，並可選擇一併重設設定。

### 2.2 功能需求

- **FR-2.1** 提供「清除資料」入口，點擊後**彈出對話框**讓使用者選擇清除範圍。
- **FR-2.2** 範圍三選一：
  1. **今日紀錄**（預設選取）
  2. **全部紀錄**
  3. **全部紀錄＋重設設定為預設值**
- **FR-2.3** 對話框需**二次確認**才執行；範圍 3（含重設設定）屬不可復原之破壞性操作，需以明顯警語提示。
- **FR-2.4** 入口同時出現在**兩處**：
  - 主視窗（今日統計區旁）
  - 設定視窗「紀錄」分類頁
  - 兩處皆開啟**同一個**清除對話框。
- **FR-2.5** 清除完成後，主視窗「今日工作 / 休息次數」需**即時刷新**（範圍 1、2 後今日統計應歸零或反映刪除結果）。
- **FR-2.6** 範圍 3 重設設定後，需提示「部分變更需重新啟動程式後才會生效」（沿用既有 `SETTINGS_SAVED_RESTART` 文案精神）。

### 2.3 行為與實作要點

- `SessionStore` 新增方法：
  - `clear_today(now: datetime | None = None) -> int`：刪除 `date(start_ts) = 今日` 的列，回傳刪除筆數。
  - `clear_all() -> int`：刪除 `sessions` 全表，回傳刪除筆數。
  - 沿用 per-thread 連線架構；由 UI 主執行緒呼叫，使用主執行緒自己的連線。
- 重設設定：`save_config(AppConfig(), config_path)`（寫入全預設值）。
- 清除對話框（新元件，例如 `ClearDataDialog`）：含三選一（預設今日）＋確認 / 取消；回傳使用者選擇的範圍。
- 主視窗刷新：清除後呼叫既有 `MainWindow._refresh_base()` 重抓 DB 基準。
- 主視窗入口建議放在今日統計區（`TodaySummaryView`）附近的動作列；設定頁入口放在「紀錄」分類頁底部（為按鈕，非 `SCHEMA` 欄位，於 `_build_category_page` 對「紀錄」分類額外加入）。

### 2.4 新增字串（範例）

```
CLEAR_DATA_BUTTON   = "清除資料"
CLEAR_DATA_TITLE    = "清除資料"
CLEAR_SCOPE_TODAY   = "清除今日紀錄"
CLEAR_SCOPE_ALL     = "清除全部紀錄"
CLEAR_SCOPE_RESET   = "清除全部紀錄並重設設定"
CLEAR_CONFIRM_BODY  = "此操作無法復原，確定要繼續嗎？"
CLEAR_DONE          = "已清除 {count} 筆紀錄。"
```

### 2.5 驗收標準

- 主視窗與設定頁皆能開啟清除對話框，預設選取「今日」。
- 選「今日」只刪今日列；選「全部」清空全表；選「全部＋重設」另外把 `config.yaml` 回到預設值。
- 任一範圍皆需二次確認；取消則不動任何資料。
- 清除後今日統計即時更新。

---

## 需求三：強制休息鎖定（win+L，僅 Windows）

### 3.1 目標

對工作過久的使用者提供「強制休息」：在符合條件時鎖定 Windows 畫面（等同 `win+L`），逼使其離開。功能可選，預設關閉。

### 3.2 功能需求

- **FR-3.1** 功能可由設定開關，預設**關閉**（opt-in）。
- **FR-3.2** 觸發方式二選一，由使用者於設定中選擇：
  - `overtime`：**超時太久**——當「超時時間」累積達 `overtime_threshold_min` 分鐘時觸發。
  - `on_rest`：**一到休息**——當進入休息狀態（`RESTING`）的當下觸發。
- **FR-3.3** 鎖定前的警示模式三選一，由使用者選擇，**預設 `immediate`**：
  - `countdown_cancel`：先倒數（`countdown_sec` 秒），期間可按「取消」跳過本次鎖定，逾時未取消則鎖定。
  - `countdown_only`：先倒數（`countdown_sec` 秒）純通知，不可取消，時間到必定鎖定。
  - `immediate`：立即鎖定，不顯示任何提示。
- **FR-3.4** 同一個工作 / 休息週期內**僅觸發一次**，避免使用者解鎖後立刻被再次鎖定。
- **FR-3.5** **鎖定僅為附加動作**，不改變 `TimerEngine` 任何計時邏輯；休息仍依既有規則（presence / fixed）判定。
- **FR-3.6** 僅限 Windows 生效；於非 Windows 平台自動 no-op（不可崩潰），並於記錄中留下訊息。

### 3.3 設定欄位（新增）

新增頂層設定區 `force_lock`：

```yaml
force_lock:
  enabled: false                 # 預設關閉
  trigger: overtime              # overtime | on_rest
  overtime_threshold_min: 10.0   # 僅 trigger=overtime 時使用
  warning_mode: immediate        # countdown_cancel | countdown_only | immediate
  countdown_sec: 10              # countdown_* 模式使用
```

- 對應新增 `@dataclass ForceLockConfig` 並掛入 `AppConfig`。
- `validate()` 需新增：`trigger ∈ {overtime, on_rest}`、`warning_mode ∈ {countdown_cancel, countdown_only, immediate}`、`overtime_threshold_min` 介於 `MINUTE_MIN..MINUTE_MAX`、`countdown_sec ≥ 1`。
- `settings_schema.py` 新增分類「強制休息」，欄位：`force_lock.enabled`（BOOL）、`force_lock.trigger`（CHOICE）、`force_lock.overtime_threshold_min`（FLOAT）、`force_lock.warning_mode`（CHOICE）、`force_lock.countdown_sec`（INT）。

### 3.4 觸發判定規格

- `overtime` 模式：監看 `TimerSnapshot.overtime_sec`，當 `overtime_sec >= overtime_threshold_min * 60` 且本工作週期尚未觸發過 → 進入警示 / 鎖定流程。
- `on_rest` 模式：監看狀態由其他狀態轉為 `RESTING` 的當下（每次休息開始）→ 進入警示 / 鎖定流程。
- 「已觸發」旗標於離開對應狀態（重新開始工作 / 結束休息）時重置，確保下一週期可再次觸發。

### 3.5 行為與實作要點

- 鎖定 API：以 `ctypes` 呼叫 `user32.LockWorkStation()`；平台判定使用 `sys.platform == "win32"`（或 `os.name == "nt"`）。
- 新增 `ForceLockController`（`QObject`，主執行緒）：訂閱 `worker.timer_updated`（取得 `TimerSnapshot` 與狀態轉換）以判定觸發；不需更動 worker 的偵測執行緒邏輯。
- 警示視窗（`countdown_*` 模式）：置頂、顯示倒數秒數；`countdown_cancel` 額外提供「取消」按鈕。倒數結束呼叫鎖定 API。
- 此控制器只負責「決定何時鎖定 / 顯示倒數 / 呼叫鎖定」，與 `TimerEngine` 解耦。

### 3.6 新增字串（範例）

```
FORCE_LOCK_COUNTDOWN = "{seconds} 秒後將鎖定畫面，請準備休息。"
FORCE_LOCK_CANCEL    = "取消本次鎖定"
```

### 3.7 驗收標準

- 預設關閉時，任何情況都不會鎖定。
- 啟用 `overtime` + `immediate`：超時達門檻立即鎖定，且同一工作週期不重複鎖定。
- 啟用 `on_rest` + `countdown_cancel`：進入休息時倒數，期間按取消可跳過本次。
- 非 Windows 平台啟用時不崩潰、不鎖定。
- 鎖定前後 `TimerEngine` 狀態與計時不受影響。

---

## 需求四：強化提示說明

### 4.1 目標

降低使用者理解門檻，讓不熟悉名詞（如 `floating`）的使用者也能看懂每個設定。

### 4.2 功能需求

- **FR-4.1** **內嵌說明（hint）＋ tooltip 兩者都做**。
- **FR-4.2** 擴充 `settings_schema.py` 既有 hint，將下列名詞講清楚（含白話舉例）：
  - `reminder.method` 的 `popup` / `toast` / `floating`（例：floating＝畫面角落的小型置頂倒數視窗）。
  - `timer.rest_count_mode` 的 `presence` / `fixed`。
  - `reminder.reminding_display_mode` 的 `overtime` / `work_and_reminder`。
  - 其他易混淆項：ROI、去抖動次數、偵測把握度、最小人體高度比例、運算裝置。
- **FR-4.3** 為各欄位（標籤或輸入元件）加上 tooltip，內容比 hint 更詳細，可補充範例與建議值。
- **FR-4.4** 新增功能（需求一、二、三）的設定欄位同樣需具備完整 hint 與 tooltip。

### 4.3 行為與實作要點

- `FieldSpec` 可考慮新增選用欄位（例如 `tooltip: str | None = None`）；未提供時 tooltip 回退為 hint。
- 於 `SettingsWindow._build_category_page` / `_make_widget` 為元件呼叫 `setToolTip(...)`。
- 此需求為純文案與 UI 屬性調整，不影響設定的讀寫邏輯。

### 4.4 驗收標準

- 每個設定欄位都有清楚的內嵌說明與 tooltip。
- `floating`、`presence/fixed`、`overtime/work_and_reminder` 等名詞，非技術使用者讀後能理解其差異。

---

## 需求五：修正介面文字錯誤

### 5.1 目標

修正介面文字的錯字與標點錯誤，並全面掃描避免遺漏。

### 5.2 功能需求

- **FR-5.1** 修正已知錯誤：`src/ui/settings_schema.py:153`
  - 現況：`提醒中要顯示》超時時間「還是》工作時間＋提醒持續時間「。`
  - 修正為：`提醒中要顯示「超時時間」還是「工作時間＋提醒持續時間」。`
- **FR-5.2** **全面掃描並修正**所有 UI 文字（至少涵蓋 `src/ui/strings.py`、`src/ui/settings_schema.py`）的：
  - 錯字、缺字、贅字。
  - 不成對 / 用錯的引號與標點（如 `》`、`「`、`」` 混用）。
  - 全形 / 半形不一致。
- **FR-5.3** 不改變文案語意，只修正錯誤呈現。

### 5.3 驗收標準

- 「提醒中顯示」hint 顯示正確的成對引號。
- UI 文字無明顯錯字 / 標點錯誤。

---

## 6. 設定結構彙整（新增 / 異動總覽）

```yaml
reminder:
  return_sound:                 # 需求一（新增）
    enabled: false
    sound_path: data/assets/Radar.mp3

force_lock:                     # 需求三（新增頂層區段）
  enabled: false
  trigger: overtime             # overtime | on_rest
  overtime_threshold_min: 10.0
  warning_mode: immediate       # countdown_cancel | countdown_only | immediate
  countdown_sec: 10
```

| 區段 | 變更 | 對應需求 |
| --- | --- | --- |
| `reminder.return_sound.*` | 新增 | 需求一 |
| `force_lock.*` | 新增頂層區段 | 需求三 |
| `SessionStore.clear_today/clear_all` | 新增方法 | 需求二 |
| `settings_schema`（新欄位＋hint＋tooltip） | 新增 / 修改 | 需求一、三、四 |
| `settings_schema` 新分類「強制休息」 | 新增 | 需求三 |
| `strings.py` / `settings_schema.py` 文案 | 修正 | 需求五 |

---

## 7. 非目標（Out of Scope）

- 不調整既有偵測 / 計時演算法與狀態機行為。
- 不支援非 Windows 平台的畫面鎖定（其他平台 no-op）。
- 不新增雲端同步、匯出報表或多使用者功能。
- 不重構與本次需求無關的既有模組。

---

## 8. 測試考量

- **需求一**：對話框啟用 / 關閉、循環播放與停止、音檔不存在容錯。
- **需求二**：`clear_today` / `clear_all` 的刪除筆數與今日統計刷新；範圍 3 重設設定後 `config.yaml` 等於預設值；取消不動資料。
- **需求三**：兩種觸發判定（`overtime` 門檻、`on_rest` 進入休息）、三種警示模式、單週期僅觸發一次、非 Windows no-op、鎖定不影響 `TimerEngine`。
- **需求四**：設定欄位皆具 hint 與 tooltip（可作快照 / 屬性檢查）。
- **需求五**：關鍵字串內容正確（可用既有 `tests/test_strings.py` 風格擴充）。
