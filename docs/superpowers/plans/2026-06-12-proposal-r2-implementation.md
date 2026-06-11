# 設定頁功能強化與系統性錯誤修正 — 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 `docs/proposal.md` 全部範圍：需求一（CUDA 檢查＋fallback）、需求二（QMediaPlayer 修聲音）、需求三（試聽按鈕）、需求四（17 項錯誤修正）。

**Architecture:** 依「檔案所有權」把工作切成 9 個任務、4 個波次執行，同一波內任務互不碰同一檔案，可平行；跨任務介面（如 `DetectionWorker.logging_enabled` 參數）在本計畫中先行定義。最後做整合驗證與對抗式審查。

**Tech Stack:** Python 3.11（conda env `project`）、PySide6（Qt6）、OpenCV、ultralytics/torch、pytest、ruff、mypy。

**規範（所有任務一體適用）：**

- TDD：先寫失敗測試 → 跑確認失敗 → 最小實作 → 跑確認通過。
- 測試指令：`conda run -n project python -m pytest <scoped test files> -q`（任務內只跑自己範圍的測試檔；全套件由整合任務跑）。
- Lint/型別：`conda run -n project ruff check <touched files>`、`conda run -n project mypy src`。
- **不操作 git**（使用者自理；不 commit、不 add）。
- 必讀資料：`docs/proposal.md` 對應章節、`.recon-fixhints.txt` 對應條目（驗證者的修法提示與陷阱警告）。
- UI 文字一律加進 `src/ui/strings.py`（全大寫常數、繁中）。
- 既有測試不得破壞；行為變更需同步修正對應測試的斷言（不是刪測試）。

---

## 檔案所有權總表

| 任務 | 波次 | 擁有檔案（src） | 測試檔 |
| --- | --- | --- | --- |
| T1 | 1 | `src/timer_engine.py` | `tests/test_timer_engine.py` |
| T2 | 1 | `src/config.py` | `tests/test_config.py` |
| T3 | 1 | `src/ui/widgets/preview_view.py` | `tests/test_ui.py`（preview 相關） |
| T4 | 1 | `src/reminder/sound.py`、`src/reminder/popup.py`、`src/reminder/media.py` | `tests/test_return_sound.py`、`tests/test_reminder.py` |
| T5 | 1 | `src/ui/theme.py`、`src/ui/icons.py`、`src/app/connection_state.py`、`data/assets/rest_placeholder.png` | `tests/test_theme.py`、`tests/test_icons.py`、`tests/test_connection_state.py` |
| T6 | 2 | `src/capture/frame_grabber.py`、`src/capture/video_source.py`、`src/capture/stream_health.py`、`src/app/worker.py` | `tests/test_frame_grabber.py`、`tests/test_video_source.py`、`tests/test_stream_health.py`、`tests/test_worker.py` |
| T7 | 2 | `src/ui/settings.py`、`src/ui/strings.py` | `tests/test_settings_schema.py`、新增 `tests/test_sound_preview.py` |
| T8 | 3 | `src/main.py`、`src/ui/main_window.py`、`src/ui/tray.py`、`src/ui/widgets/action_bar.py`、`src/types.py`、`src/reminder/floating.py` | `tests/test_main.py`、`tests/test_ui.py`（main window 相關）、`tests/test_reminder.py`（floating 部分） |
| T9 | 4 | `src/detection/cuda_check.py`（新）、`src/detection/detector.py`、`src/ui/settings.py`、`src/ui/strings.py`、`src/main.py`、`src/app/worker.py` | 新增 `tests/test_cuda_check.py`、`tests/test_detector.py` |
| T10 | 5 | 整合驗證＋審查修正（全部） | 全套件 |

---

## Wave 1（五任務平行，檔案互斥）

### T1：timer_engine 暫停修正（proposal §4.1、§4.4）

**Files:** Modify `src/timer_engine.py`；Test `tests/test_timer_engine.py`

設計約束（來自驗證報告）：

- §4.1：`resume()` 的 `self._state = self._state_before_pause`（timer_engine.py:242）在正常流程是 no-op，唯一生效時機就是造成損壞的時機。修法：**移除 resume 的狀態還原與 `_state_before_pause` 機制**（首選），或指令執行時同步更新該值。**禁止**改成「暫停期間拒絕 start_rest/confirm_return 指令」——ReturnPromptDialog 按確認後無條件關閉，拒絕指令同樣造成 AWAITING_RETURN 死鎖。
- §4.4：`pause(now)` 記錄 `_pause_started_at`；`resume(now)` 把 `_away_since`、`_reminder_last_t`、`_rest_started_at`、`_rest_start_t` 中非 None 者各加上暫停時長（向前平移＝等效凍結）。

- [ ] 失敗測試 A：AWAITING_RETURN → pause → confirm_return → resume，斷言狀態為 WORKING（非 AWAITING_RETURN）、事件不重複。
- [ ] 失敗測試 B：REMINDING → pause → start_rest → resume，斷言狀態為 RESTING、無第二筆 work session。
- [ ] 失敗測試 C：AWAY 暫停超過 reset_threshold 再 resume，斷言**不**觸發重置；REMINDING 暫停超過 repeat_interval 再 resume，斷言**不**立即重發提醒。
- [ ] 失敗測試 D：RESTING（fixed 模式）跨暫停，必要休息時長不被暫停折抵；confirm_return 的 rest_duration 不含暫停時長。
- [ ] 實作 §4.1 修法 → 測試 A、B 通過。
- [ ] 實作 §4.4 時間戳平移 → 測試 C、D 通過。
- [ ] 全檔測試 + ruff + mypy 通過。

### T2：config 驗證補強（proposal §4.5）

**Files:** Modify `src/config.py`；Test `tests/test_config.py`

- [ ] 失敗測試：`presence.roi` 畸形（非 list、長度錯、含 None/字串/bool、負值、>1、w/h=0、x+w>1）各案例 `validate()` 回報含 `presence.roi` 的錯誤訊息，且 `load_config` 拋 `ConfigError` 而非 TypeError/ValueError。
- [ ] 失敗測試：`detection.interval_sec`、`source.reconnect_interval_sec`（>0 數值）、`source.webcam_index`（int 且 ≥0，排除 bool）型別/值域錯誤被 `validate()` 攔截。
- [ ] 實作 `validate()` 檢查（沿用既有 `_in_range`/`_greater_than_zero` 輔助函式風格；roi 檢查需在 `_roi_from_raw` 之前生效，即 validate 階段直接檢查 raw dict）。
- [ ] 確認合法 config 不受影響（既有測試全綠）+ ruff + mypy。

### T3：PreviewView 修正（proposal §4.3、§4.9）

**Files:** Modify `src/ui/widgets/preview_view.py`；Test `tests/test_ui.py`

設計約束：

- §4.3：framebuffer→widget 採 KeepAspectRatio 置中，框選換算需以「實際顯示影像矩形」為基準：記錄最近影格尺寸，計算 scaled size 與置中偏移，正規化 `(pos - offset) / scaled_dim`，clamp [0,1]；完全落在留邊內的框拒絕提交。
- §4.9：文字與影像分離——獨立覆蓋層 QLabel（疊於影像之上、平時隱藏）或 paintEvent 繪字；`set_edit_mode` 提示與 `set_overlay_text` 在影格持續更新下仍可見。

- [ ] 失敗測試：已知幾何換算案例（如 640×360 影格放入 400×400 widget：上下留邊 (400−225)/2≈87px；在影像區內框選一矩形，斷言正規化結果）。留邊內框選回傳 None/不發 signal。
- [ ] 失敗測試：`set_edit_mode(True)` 後連續 `set_frame` 多次，提示文字仍可見（覆蓋層 isVisible 且文字未被清除）。
- [ ] 實作座標換算 + 覆蓋層分離。
- [ ] 範圍測試 + ruff + mypy 通過。

### T4：聲音播放修復（proposal 需求二 FR-2.1～2.6）

**Files:** Modify `src/reminder/sound.py`、`src/reminder/popup.py`、（必要時）`src/reminder/media.py`；Test `tests/test_return_sound.py`、`tests/test_reminder.py`

設計約束：

- `QtLoopingSoundPlayer` 內部以 `QMediaPlayer` + `QAudioOutput` 取代 `QSoundEffect`，`setLoops(QMediaPlayer.Loops.Infinite)` 維持循環；**對外 Protocol `play(path)/stop()` 不變**，`ReturnPromptDialog` 與 FakePlayer 注入測試不得受影響。
- popup：`_sound_effect` 換成**第二組** QMediaPlayer＋QAudioOutput（與影片那組分離，popup.py:39-42 已 import 所需類別）；單次播放（不設循環）。
- `hide()` 一併停止提醒音（修 popup.py:74-76 只停影片的缺陷）。
- 播放錯誤：連接 `QMediaPlayer.errorOccurred`，以 `logging` 記錄（含 source 路徑），靜默不播、不崩潰。`safe_sound_url` 的「空路徑/不存在 → None」行為不變。

- [ ] 失敗測試：存在但無法解碼的檔案（tmp_path 寫入垃圾 bytes 的 .mp3）→ `play()` 不拋例外；log 有紀錄（caplog）。
- [ ] 失敗測試：popup `hide()` 後音效播放器處於停止狀態。
- [ ] 實作 sound.py 替換 → 既有 `tests/test_return_sound.py` 全綠。
- [ ] 實作 popup.py 替換＋hide 停音 → `tests/test_reminder.py` 全綠。
- [ ] ruff + mypy 通過。

### T5：資產與樣式（proposal §4.12、§4.15、§4.16）

**Files:** Modify `src/ui/icons.py`、`src/ui/theme.py`、`src/app/connection_state.py`（如採統一 role 方案）、Regenerate `data/assets/rest_placeholder.png`；Test `tests/test_icons.py`、`tests/test_theme.py`、`tests/test_connection_state.py`

設計約束：

- §4.12：以 Pillow 重產 placeholder（內容不限 1×1，可產生簡單灰底圖），驗收為 `cv2.imread` 與 `QPixmap` 皆可載入、無 libpng 錯誤。
- §4.15：`load_app_icon` 預設路徑改為「以模組位置定錨」且指向實際資產 `icon.png`（`Path(__file__).resolve().parents[2] / "data" / "assets" / "icon.png"`），同時修掉檔名錯誤與 CWD 依賴；恆真測試 `tests/test_icons.py` 改為有效斷言（載入結果與資產內容比對，非比較兩個必然不同的 cacheKey）。
- §4.16：theme.py QSS 增加 `QLabel[role="muted"]`（灰色，**不可**沿用 secondary——其 11px 字級會造成切換時版面跳動）；`neutral` 統一：建議把 `connection_state.py:25` IDLE 的 severity 改為 `"muted"`，QSS 只需一條新規則；PresenceBadge/ConnectionBadge 樣式一致。

- [ ] 失敗測試：muted role 存在於 QSS；IDLE severity 對應的 role 在 QSS 中有規則（防回歸：斷言兩個 badge 用到的所有 role 都出現在 build_qss 輸出）。
- [ ] 失敗測試：`load_app_icon()` 預設在任意 CWD 下載入實際資產（與 `QIcon(資產絕對路徑)` 的 toImage 相等）。
- [ ] 重產 `rest_placeholder.png` + 驗證可解碼（測試：QPixmap/cv2 載入非空）。
- [ ] 實作 → 範圍測試 + ruff + mypy 通過。

---

## Wave 2（兩任務平行，檔案互斥）

### T6：擷取層與 worker（proposal §4.2、§4.10、§4.13、§4.17、§4.8-worker 端）

**Files:** Modify `src/capture/frame_grabber.py`、`src/capture/video_source.py`、`src/app/worker.py`、（必要時）`src/capture/stream_health.py`；Test `tests/test_frame_grabber.py`、`tests/test_video_source.py`、`tests/test_stream_health.py`、`tests/test_worker.py`

設計約束：

- §4.2：以「影格新鮮度」取代「影格存在性」——worker 記錄上次處理的 `frame.timestamp`（`src/types.py:32` 已有此欄位），`has_frame = (frame is not None and frame.timestamp != last_ts)`；過期影格走健康檢查分支（帶 `is_opened` 區分 DISCONNECTED/TIMEOUT）並**跳過偵測**，不得以凍結畫面更新在席狀態。
- §4.10：RTSP 逾時必須在**建構子**傳入：`cv2.VideoCapture(url, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000])`（open 後 set 已太遲）；`FrameGrabber.stop()` 的 join 加 timeout（2.0s），逾時放棄等待（daemon 執行緒）且跳過 `release()` 避免與仍在 read 的執行緒競爭。
- §4.13：`is_opened` 先快照 `cap = self._cap` 再判斷，消除 TOCTOU（WebcamSource 與 RTSPSource 皆要修）。
- §4.17：移除 `CAP_PROP_BUFFERSIZE`（FFMPEG 後端不支援）或保留但檢查 `set()` 回傳值並 log warning；加註解說明延遲由高頻抽幀承擔。
- §4.8（worker 端介面，**T8 會在 main.py 傳入**）：`DetectionWorker.__init__` 新增參數 `logging_enabled: bool = True`；`_dispatch` 在 False 時跳過 `store.log_session`。**參數名稱固定為 `logging_enabled`，不得擅改**（T8 依此接線）。

- [ ] 失敗測試：worker 先收到一幀、之後 latest() 持續回傳同一幀（timestamp 不變）→ 健康狀態進入 TIMEOUT/DISCONNECTED、不再呼叫 detector。
- [ ] 失敗測試：`logging_enabled=False` 時 WORK_ENDED/REST_ENDED 不寫 store。
- [ ] 失敗測試：is_opened 在 `_cap` 被併發設為 None 時不拋例外（注入模擬）。
- [ ] 失敗測試：stop() 在 read 永久阻塞（fake source）下 ≤ ~2.5s 返回。
- [ ] 實作以上 → 範圍測試 + ruff + mypy 通過。

### T7：設定視窗——試聽、瀏覽過濾、舊 config 基底（proposal 需求三 FR-3.1～3.7、FR-2.7、§4.7-settings 端）

**Files:** Modify `src/ui/settings.py`、`src/ui/strings.py`；Test `tests/test_settings_schema.py`、Create `tests/test_sound_preview.py`

設計約束：

- 試聽：擴充 `PathField`（或包裝出 `SoundPathField`）為「輸入框＋瀏覽＋試聽」同列；播放元件**重用 T4 的播放器**（單次播放模式）。狀態機：idle ↔ playing；播放中按鈕變停止；同時僅一個試聽（建議 SettingsWindow 持有單一共享 preview player）；視窗 `done()`/關閉時停止；無效檔於該欄位 hint 顯示 `strings.SOUND_PREVIEW_ERROR`（role=danger），成功播放時清除。
- 試聽以欄位**目前輸入值**為準（未儲存）。
- FR-2.7：音檔欄位（`reminder.popup.sound_path`、`reminder.return_sound.sound_path`）的瀏覽對話框 filter：`"音訊檔 (*.mp3 *.wav);;所有檔案 (*)"`。如何判別音檔欄位：建議 `FieldSpec` 加選用欄位（如 `file_filter: str | None = None`）或依 key 清單特判——擇一並在測試鎖定。
- §4.7：`_read_widgets_to_config` 改以 `load_config(self._config_path)` 重讀磁碟作為基底（而非啟動時注入的 `self._config`），SCHEMA 外欄位（presence.roi）不被舊值覆寫。（main_window 端 ROI 寫檔同理由 T8 處理。）
- 新字串：`SOUND_PREVIEW_PLAY = "試聽"`、`SOUND_PREVIEW_STOP = "停止"`、`SOUND_PREVIEW_ERROR = "無法播放此音檔"`。

- [ ] 失敗測試：兩個音檔欄位 widget 各含試聽按鈕；按下後 player.play 收到**欄位目前文字**（注入 FakePlayer）。
- [ ] 失敗測試：A 播放中按 B → A 停止、B 播放；關閉視窗 → 停止。
- [ ] 失敗測試：無效路徑 → hint 顯示錯誤、role=danger、不拋例外。
- [ ] 失敗測試：磁碟 config 的 roi 與啟動注入 config 不同時，儲存後磁碟 roi 保留（§4.7）。
- [ ] 失敗測試：音檔欄位瀏覽 filter 含 `*.mp3 *.wav`。
- [ ] 實作 → 範圍測試 + ruff + mypy 通過。

---

## Wave 3（單任務）

### T8：main.py 接線與 UI 同步（proposal §4.6、§4.11、§4.14、§4.5-main 端、§4.7-ROI 端、§4.8-接線）

**Files:** Modify `src/main.py`、`src/ui/main_window.py`、`src/ui/tray.py`、`src/ui/widgets/action_bar.py`、`src/types.py`、`src/reminder/floating.py`；Test `tests/test_main.py`、`tests/test_ui.py`、`tests/test_reminder.py`

設計約束：

- §4.6：TrayIcon（QObject）新增薄槽方法 `on_timer_updated(snapshot)` / `on_connection_status(status)`，main.py:138/140 改連 bound method（自動 queued connection）。**不可**用 functools.partial 或 lambda＋QueuedConnection。
- §4.11：ActionBar 新增 `set_paused(paused)`（blockSignals 防重入、同步按鈕文字），MainWindow 轉發；`_toggle_pause` 統一同步 window 與 tray。
- §4.14：`ReminderContext.work_minutes` 改 float（`src/types.py:82`）、移除 main.py:59 的 `int()`、floating.py:31 改 `max(round(ctx.work_minutes * 60), 1)`。
- §4.5-main 端：`main()` 對 `load_config` 包 `try/except ConfigError`，以 stderr 清楚列出錯誤後退出（exit code ≠ 0），不得拋原始 traceback。
- §4.7-ROI 端：`MainWindow._on_roi_committed` 寫檔前以磁碟 config 為基底（`load_config` 重讀後僅替換 presence.roi）。
- §4.8-接線：`_build_worker` 傳入 `logging_enabled=cfg.logging.enabled`（T6 已定義參數）。

- [ ] 失敗測試：tray 槽方法存在且 worker 訊號連接到 QObject bound method（檢查 main.py 接線或以行為測試驗證）。
- [ ] 失敗測試：`_toggle_pause` 後 ActionBar checked 與 tray 文字一致；交錯切換不重入。
- [ ] 失敗測試：work_threshold_min=0.1 → floating 倒數 6 秒；25.5 → 1530 秒。
- [ ] 失敗測試：畸形 config 啟動 → ConfigError 訊息、非零退出、無 traceback。
- [ ] 失敗測試：先存設定（磁碟有新 roi）→ ROI 重框寫檔後設定值保留。
- [ ] 實作 → 範圍測試 + ruff + mypy 通過。

---

## Wave 4（單任務）

### T9：CUDA 檢查與 fallback（proposal 需求一 FR-1.1～1.6）

**Files:** Create `src/detection/cuda_check.py`、`tests/test_cuda_check.py`；Modify `src/detection/detector.py`、`src/ui/settings.py`、`src/ui/strings.py`、`src/main.py`、`src/app/worker.py`；Test `tests/test_detector.py`、`tests/test_settings_schema.py`

新模組介面（純邏輯、與 Qt 分離）：

```python
# src/detection/cuda_check.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class CudaCheckResult:
    state: str                    # "no_torch" | "cpu_only" | "cuda_unavailable" | "ok"
    torch_version: str | None     # 如 "2.9.1+cu128"；no_torch 時 None
    cuda_build_version: str | None  # torch.version.cuda；CPU-only 為 None
    cuda_available: bool
    device_count: int
    devices: tuple[str, ...]      # "NVIDIA GeForce RTX 5060 Laptop GPU (8.0 GB)" 形式
    cudnn_version: int | None
    suggested_device: str         # "auto" | "cpu"
    error: str | None             # 例外訊息（含 ImportError）

def check_cuda() -> CudaCheckResult: ...   # 不得拋例外；所有例外收進 error 欄位
```

設計約束：

- 設定頁：「運算裝置」欄位旁加「檢查」按鈕（仿 PathField 複合 widget）；按下 → 按鈕停用、文字 `CUDA_CHECK_RUNNING` → 於背景執行緒（QThread 或 QThreadPool）呼叫 `check_cuda()` → signal 回主執行緒 → `QMessageBox`/簡單 QDialog 呈現診斷（標題 `CUDA_CHECK_TITLE`，內容含四種狀態對應訊息與 `CUDA_SUGGEST`）→ 按鈕復原。防重入：執行中再點無效。視窗關閉時忽略遲到的結果（不可對已銷毀 widget 操作）。
- fallback（FR-1.6）：`detector._ensure_model` 的 `model.to(device)` 包 try/except（捕 `Exception`，涵蓋 AssertionError/RuntimeError）：失敗且 device 非 cpu 時 log warning、改 `to("cpu")` 繼續，並記錄 fallback 狀態；`PersonDetector` 暴露 `device_fallback: bool`（或類似）屬性。worker 在偵測啟動後若 fallback 發生，emit 一次新 signal `device_fallback = Signal(str)`；main.py 接線顯示 `strings.CUDA_FALLBACK_NOTICE`（tray showMessage 即可）。
- 新字串：`CUDA_CHECK_BUTTON = "檢查"`、`CUDA_CHECK_RUNNING = "檢查中…"`、`CUDA_CHECK_TITLE = "GPU CUDA 檢查"`、`CUDA_CHECK_OK`、`CUDA_CHECK_FAIL`、`CUDA_SUGGEST = "建議的運算裝置：{device}"`、`CUDA_FALLBACK_NOTICE = "CUDA 初始化失敗，已改用 CPU 繼續偵測。"`。

- [ ] 失敗測試：`check_cuda()` 四種狀態（monkeypatch torch import / 屬性）各回傳正確 state 與 suggested_device；任何內部例外不外洩。
- [ ] 失敗測試：detector `.to()` 失敗 → fallback 至 cpu、不拋例外、`device_fallback` 為 True；`.to()` 成功 → False。
- [ ] 失敗測試：設定頁運算裝置 widget 含檢查按鈕；點擊後按鈕停用；（以注入/mock 的 checker）結果回來後復原。
- [ ] 實作 → 範圍測試 + ruff + mypy 通過。
- [ ] 本機實機驗證：`conda run -n project python -c "from src.detection.cuda_check import check_cuda; print(check_cuda())"` → state="ok"、RTX 5060。

---

## Wave 5（整合）

### T10：整合驗證與審查

- [ ] 全套件：`conda run -n project python -m pytest -q` 全綠。
- [ ] `conda run -n project ruff check .` 0 錯誤。
- [ ] `conda run -n project mypy src` 0 錯誤。
- [ ] 對抗式程式碼審查（spec 符合度、Qt 執行緒安全、回歸風險），確認的問題修正後重跑驗證。
- [ ] 更新 `docs/proposal.md` 文件狀態為「已實作」。
- [ ] 向使用者回報：變更檔案清單、測試結果、待手動驗收項（實際聲音播放、CUDA 對話框、托盤行為等 GUI 實聽實看項目）。

## 自我審查紀錄

- Spec 覆蓋：需求一→T9；需求二→T4＋T7(FR-2.7)；需求三→T7；§4.1/4.4→T1；§4.5→T2＋T8；§4.2/4.10/4.13/4.17→T6；§4.6/4.11/4.14→T8；§4.7→T7＋T8；§4.8→T6＋T8；§4.3/4.9→T3；§4.12/4.15/4.16→T5。無缺口。
- 跨任務介面已鎖定：`logging_enabled` 參數名（T6↔T8）、播放器 Protocol 不變（T4↔T7）、strings 常數名（T7/T9）。
- 不操作 git 為本專案使用者指示，取代計畫範本中的 commit 步驟。
