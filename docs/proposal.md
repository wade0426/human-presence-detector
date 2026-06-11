# 需求文檔：設定頁功能強化與系統性錯誤修正

> 文件狀態：已實作（待手動驗收）
> 適用專案：human-presence-detector（人體辨識休息提醒系統）

---

## 0. 背景與目標

本次擴充包含三項新功能與一輪系統性錯誤修正：

1. 「進階」設定頁新增 **GPU CUDA 檢查按鈕**，讓使用者確認自己的裝置是否支援 CUDA，並在選了 `cuda` 但機器不支援時自動退回 CPU。
2. **修復聲音播放**：現行 `QSoundEffect` 無法解碼 mp3，預設音檔 `Radar.mp3` 完全無聲且錯誤被吞掉。
3. 設定頁音檔欄位新增 **試聽（喇叭）按鈕**，儲存前即可試播音檔。
4. 修正經逐項驗證確認的 **17 個既有錯誤**（依嚴重度分級：High 3、Medium 7、Low 7）。

本文件僅定義需求與驗收標準，**不包含實作程式碼**，且**不需 commit 至 git**。

### 0.1 名詞對照

| 名詞 | 說明 |
| --- | --- |
| 運算裝置 / device | `detection.device` 設定（`auto` / `cpu` / `cuda`），決定 YOLO 推論跑在 CPU 或 NVIDIA GPU。 |
| CPU-only build | 未編譯 CUDA 支援的 PyTorch 套件（`torch.version.cuda` 為 `None`），與「有 CUDA build 但驅動／GPU 不可用」是不同狀態。 |
| QSoundEffect | Qt 低延遲音效類別，**僅支援未壓縮 WAV/PCM**，不支援 mp3。 |
| QMediaPlayer + QAudioOutput | Qt 通用媒體播放組合（FFmpeg 後端），支援 mp3 / wav 等常見格式。 |
| SoundPlayer Protocol | `src/reminder/sound.py` 定義的播放介面（`play(path)` / `stop()`），呼叫端只依賴此介面。 |
| 留邊（letterbox） | 預覽影像以 KeepAspectRatio 縮放置中後，widget 上下或左右出現的空白邊。 |
| 試聽 | 在設定頁直接播放欄位中音檔路徑的功能，不需儲存設定。 |

### 0.2 現況摘要（與本需求相關）

- 「運算裝置」欄位位於「進階」分類（`src/ui/settings_schema.py:233`，`QComboBox`，選項 `auto/cpu/cuda`）。選 `cuda` 但機器不支援時，例外發生在偵測執行緒第一次推論（`model.to("cuda")`），被 `DetectionWorker.run` 捕獲後**偵測迴圈永久終止，無 fallback、無重試**（`src/app/worker.py:102-108`），UI 僅剩一行錯誤字串。
- 聲音有兩條播放路徑：popup 提醒音（`src/reminder/popup.py:43, 67-70`，單次）與歡迎回來循環音（`src/reminder/sound.py:16-29` + `src/reminder/return_prompt.py`）。兩者皆用 `QSoundEffect`，而程式預設值（`src/config.py:61`）與現行 `config.yaml` 皆指向 mp3，實測載入後 `Status.Error`、無聲、無任何使用者可見的錯誤。
- `safe_sound_url()` 只檢查「路徑非空且檔案存在」，不檢查格式（`src/reminder/media.py:37-40`）。
- 設定頁欄位旁附按鈕已有前例：`PathField`（QLineEdit＋「瀏覽」按鈕，`src/ui/settings.py:40-56`）；分類頁底部動作按鈕＋Signal 外接也有前例（「紀錄」頁清除資料按鈕，`src/ui/settings.py:159-162`）。
- 全專案**沒有任何音量控制**（無 `setVolume` 呼叫），播放一律預設音量；本輪維持此現狀（見非目標）。
- 需求四的 17 個問題由多代理調查產出、每項經獨立對抗驗證確認（High 1、2 並經實際重現），證據以 file:line 記於各小節。

---

## 需求一：GPU CUDA 檢查按鈕（含 CUDA 失敗退回 CPU）

### 1.1 目標

讓使用者在「進階」頁一鍵確認本機是否支援 GPU CUDA、看懂自己該選哪個運算裝置；並讓「選了 `cuda` 但不支援」不再造成偵測靜默死亡。

### 1.2 功能需求

- **FR-1.1** 「進階」分類頁的「運算裝置」欄位旁新增「檢查」按鈕（仿 `PathField` 複合 widget 形式：下拉選單＋按鈕同列）。
- **FR-1.2** 檢查必須在**背景執行緒**執行，期間按鈕停用並顯示「檢查中…」，GUI 不得凍結（`import torch` 冷啟最壞 1.5 秒以上、驅動異常時 `torch.cuda.is_available()` 可能更久）。完成後以 signal 回主執行緒呈現結果。按鈕需防重入（檢查進行中再點無效）。
- **FR-1.3** 檢查完成後**彈出診斷對話框**，內容包含：
  - PyTorch 版本（含 build 標籤，如 `2.9.1+cu128` / `+cpu`）
  - CUDA build 版本（`torch.version.cuda`；CPU-only build 顯示「無（CPU 版 PyTorch）」）
  - CUDA 是否可用（`torch.cuda.is_available()`）
  - GPU 數量，及各 GPU 型號與 VRAM 總量（`get_device_name` / `get_device_properties`）
  - cuDNN 版本（`torch.backends.cudnn.version()`）
  - **建議的運算裝置設定值**（見 FR-1.4）
- **FR-1.4** 需完整區分並正確呈現四種狀態，各附對應建議：
  1. torch 未安裝（ImportError）→ 建議 `cpu`，提示需安裝 PyTorch。
  2. CPU-only build（`torch.version.cuda is None`）→ 建議 `cpu`，提示需改裝 CUDA 版 PyTorch 才能用 GPU。
  3. CUDA build 但不可用（`is_available() == False`）→ 建議 `cpu`，提示檢查 NVIDIA 驅動／GPU。
  4. 正常可用 → 建議 `auto` 或 `cuda`。
- **FR-1.5** 檢查過程中任何例外不可使程式崩潰；例外訊息納入對話框呈現。
- **FR-1.6**（CUDA fallback）偵測端初始化裝置失敗時（如 `model.to("cuda")` 拋出 `AssertionError: Torch not compiled with CUDA enabled` 或 `RuntimeError: Found no NVIDIA driver`），**自動退回 CPU 繼續偵測**，不得讓偵測迴圈終止；需寫入 log，並於 UI 提示「CUDA 初始化失敗，已改用 CPU 繼續偵測」。`auto` 模式行為不變（本來就會自動判斷）。

### 1.3 行為與實作要點

- 檢查邏輯獨立為純函式／資料類別（例如回傳 `CudaCheckResult` dataclass），與 Qt 分離，便於單元測試（沿用「純邏輯與 Qt 分離」設計原則）。
- 背景執行可用 `QThread` 或 `QThreadPool`；結果經 signal 傳回主執行緒後才建立對話框。
- 按鈕掛載方式沿用 `PathField` 複合 widget 前例，於 `SettingsWindow._make_widget` 對 `detection.device` 特例處理或新增 widget 類型。
- fallback 屬偵測端行為（`src/detection/detector.py` 的裝置解析／模型載入），與檢查按鈕互相獨立；UI 提示可沿用既有 worker → main 的 signal 路徑。
- 新增 UI 文字一律進 `src/ui/strings.py`（全大寫常數、繁中、`{placeholder}` 佔位）。

### 1.4 新增字串（範例）

```
CUDA_CHECK_BUTTON   = "檢查"
CUDA_CHECK_RUNNING  = "檢查中…"
CUDA_CHECK_TITLE    = "GPU CUDA 檢查"
CUDA_CHECK_OK       = "✓ 本機可使用 GPU CUDA"
CUDA_CHECK_FAIL     = "✗ 本機目前無法使用 GPU CUDA"
CUDA_SUGGEST        = "建議的運算裝置：{device}"
CUDA_FALLBACK_NOTICE = "CUDA 初始化失敗，已改用 CPU 繼續偵測。"
```

### 1.5 驗收標準

- 在支援機（如開發機：RTX 5060 Laptop GPU、torch 2.9.1+cu128）按下檢查：顯示「可使用」、GPU 型號、CUDA 12.8、建議 `auto` 或 `cuda`。
- 檢查期間 GUI 可正常操作，按鈕呈「檢查中…」且不可重入。
- 四種狀態各自顯示正確訊息與建議值（不支援的狀態可用單元測試以注入／mock 驗證）。
- 設 `device: cuda` 於不支援 CUDA 的環境啟動：偵測自動改用 CPU 繼續運作、log 有記錄、UI 有提示；偵測迴圈不終止。

---

## 需求二：修復聲音播放（支援 mp3）

### 2.1 目標

讓提醒音效與歡迎回來音效在預設配置（mp3）下真正發聲；播放失敗時有跡可循而非靜默吞錯。

### 2.2 功能需求

- **FR-2.1** popup 提醒音與歡迎回來循環音兩條路徑皆能播放 mp3 與 wav 等常見格式。
- **FR-2.2** 底層播放實作由 `QSoundEffect` 替換為 `QMediaPlayer` + `QAudioOutput`；**`SoundPlayer` Protocol（`play`/`stop`）介面不變**，`ReturnPromptDialog` 等呼叫端與注入測試（`FakePlayer`）不受影響。
- **FR-2.3** 歡迎回來音效維持**循環播放**直到按下確認鈕（改用 `QMediaPlayer.setLoops(Infinite)` 實現，行為不變）。
- **FR-2.4** popup 的提醒音播放器須**獨立於影片播放器**（`media_type == "video"` 時兩者可能同時存在，不可共用同一組 QMediaPlayer）。
- **FR-2.5** 修復既有缺陷：popup 關閉（`hide()`）時目前只停影片不停音效（`src/reminder/popup.py:74-76`），修正為**一併停止提醒音**。
- **FR-2.6** 播放錯誤（檔案損壞、格式不支援等）時：寫入 log、靜默不播、不得崩潰（沿用 `safe_sound_url` 容錯精神；路徑空／檔案不存在仍為靜默略過）。
- **FR-2.7** `PathField` 的「瀏覽」對話框在音檔欄位需加副檔名過濾（如「音訊檔 (*.mp3 *.wav);;所有檔案 (*)」）。

### 2.3 行為與實作要點

- 異動集中於 `src/reminder/sound.py`（`QtLoopingSoundPlayer` 內部替換）與 `src/reminder/popup.py`（`_sound_effect` 換為第二組 QMediaPlayer＋QAudioOutput；該檔已 import 這兩個類別）。
- `src/reminder/media.py` 的 `safe_sound_url` 行為不變；config 與音檔資產不需變動。
- 錯誤監聽使用 `QMediaPlayer.errorOccurred` signal。

### 2.4 驗收標準

- 現行 `config.yaml`（`Radar.mp3`）下：popup 提醒出現時有聲；啟用回來提示音後循環播放、按「開始新一輪」立即靜音。
- popup 關閉當下提醒音立即停止。
- 指定損壞／不支援的音檔：不播、不崩潰、log 有記錄。
- 既有 `tests/test_return_sound.py` 注入測試全數通過；補上「檔案存在但格式不支援」情境的測試（此為本 bug 未被攔截的測試缺口）。

---

## 需求三：音檔試聽（喇叭）按鈕

### 3.1 目標

使用者在設定頁即可試播音檔，不必儲存、重啟、等提醒觸發才知道聲音對不對。

### 3.2 功能需求

- **FR-3.1** 兩個音檔欄位——「音效路徑」（`reminder.popup.sound_path`）與「回來提示音效檔」（`reminder.return_sound.sound_path`）——各在欄位旁新增試聽按鈕（喇叭圖示）。
- **FR-3.2** 按下播放**一次**（不循環）；播放中按鈕變為停止狀態，再按立即停止。
- **FR-3.3** 試聽以**欄位目前輸入值**為準（含尚未儲存的修改）。
- **FR-3.4** 同時僅允許一個試聽；播放中啟動另一欄位的試聽時，先停止前一個。
- **FR-3.5** 設定視窗關閉（儲存或取消）時自動停止試聽。
- **FR-3.6** 路徑為空、檔案不存在或無法解碼時：不播放、不崩潰，並於該欄位 hint 區顯示錯誤文字（沿用驗證錯誤的 `role=danger` 呈現慣例）；下次成功播放或重新試聽時清除錯誤。
- **FR-3.7** 試聽與需求二使用**同一播放元件**，確保「試聽聽到的＝實際提醒聽到的」。

### 3.3 行為與實作要點

- UI 形式沿用 `PathField` 複合 widget 前例：音檔欄位呈「輸入框＋瀏覽＋試聽」同列；建議擴充或包裝 `PathField` 而非另造平行元件。
- 試聽屬設定視窗內部行為，不需經 `main.py` 接線（與「清除資料」按鈕的 Signal 外接模式不同）。
- 按鈕文字／無障礙名稱進 `strings.py`。

### 3.4 新增字串（範例）

```
SOUND_PREVIEW_PLAY  = "試聽"
SOUND_PREVIEW_STOP  = "停止"
SOUND_PREVIEW_ERROR = "無法播放此音檔"
```

### 3.5 驗收標準

- 兩個音檔欄位都有試聽按鈕；按下可聽到欄位目前指定的音檔，再按停止。
- 修改路徑後未儲存即可試聽新路徑。
- 兩欄位互相切換試聽時不重疊播放。
- 無效檔案顯示錯誤 hint、不崩潰；關閉設定視窗時聲音停止。

---

## 需求四：錯誤修正（17 項）

> 每項格式：**現況／根因**（含證據位置）→ **修正要求** → **驗收標準**。
> 等級代表建議優先序：🔴 High（核心功能實質損壞）→ 🟡 Medium（行為錯誤／設定失效）→ 🟢 Low（小錯誤／死資產）。實作可依等級分階段。

### 🔴 High

#### 4.1 暫停／恢復會損壞計時狀態機

- **現況／根因**：`pause()` 只記錄 `_state_before_pause` 不改 `_state`；`resume()` 無條件還原 `self._state = self._state_before_pause`（`src/timer_engine.py:242`）。但 worker 迴圈在檢查 `_paused` **之前**先執行佇列指令（`src/app/worker.py:69-72`），且 `start_rest()` / `confirm_return()` 不檢查暫停狀態。暫停期間按歡迎回來確認鈕 → 恢復後狀態被覆寫回 `AWAITING_RETURN`，而對話框已關閉且不會重發 → **狀態機永久卡死（須重啟）**；暫停期間按「開始休息」→ 恢復後 DB 寫入重複的工作紀錄。兩情境皆已實際重現。
- **修正要求**：消除「resume 用過期狀態覆寫」的可能。注意：在指令守衛中單純擋掉暫停期間的指令**不可行**（確認鈕按下後對話框無條件關閉，拒絕指令同樣導致卡死）；可行方向為移除 resume 的狀態還原機制，或指令執行時同步更新 `_state_before_pause`。
- **驗收標準**：暫停期間操作確認鈕／開始休息，恢復後狀態機行為正確、無卡死、DB 無重複紀錄；補齊「暫停期間執行指令」的單元測試。

#### 4.2 串流斷線永遠偵測不到（凍結畫面持續偵測）

- **現況／根因**：`FrameGrabber._latest` 只在 `stop()` 時清空，斷線後最後一幀永久保留（`src/capture/frame_grabber.py:57-63, 80-82`）；worker 以 `latest() is not None` 當作 `has_frame`（`src/app/worker.py:75-88`），與 `StreamHealthMonitor` 期待的「本週期是否有**新**影格」語意不符。結果：只要曾收到一幀，健康監測永遠回報 OK，TIMEOUT／DISCONNECTED 永不觸發，UI 永遠顯示已連線，並持續對凍結畫面做偵測（在席判定固定不變）。
- **修正要求**：讓 worker 能區分「新影格」與「殘留的舊影格」（例如影格附時間戳／序號，或 take-once 語意），健康監測依「新影格」判定；斷線時 UI 連線狀態正確轉為 TIMEOUT／DISCONNECTED，且不得以凍結畫面的偵測結果更新在席狀態。
- **驗收標準**：模擬來源停止供幀後，於逾時門檻內 UI 顯示斷線；恢復供幀後自動回到已連線；補單元測試。

#### 4.3 ROI 框選座標與實際畫面錯位

- **現況／根因**：預覽影像以 KeepAspectRatio 縮放並置中（`src/ui/widgets/preview_view.py:34-40`），widget 與影像長寬比不同時有留邊；但滑鼠框選直接以 **widget 寬高**正規化（`preview_view.py:78-85`），未補償留邊與實際顯示尺寸。存下的 ROI 與使用者在畫面上框的區域不一致 → 在席判定範圍錯誤（`src/presence.py:43-48` 以正規化座標判定）。
- **修正要求**：框選座標換算需扣除留邊偏移、除以實際顯示影像尺寸，並 clamp 至 [0,1]；留邊區域的拖曳起終點需正確處理。
- **驗收標準**：以已知幾何（如 16:9 影格配 4:3 widget）做單元測試，框選座標換算結果與影格實際區域一致；實機框選後 ROI 視覺位置吻合。

### 🟡 Medium

#### 4.4 暫停期間時間照算，違反凍結契約

- **現況／根因**：`resume()` 只重設 `_last_t`；`_away_since`、`_reminder_last_t`、`_rest_started_at`、`_rest_start_t` 為絕對時間戳且判斷皆用 `now` 直接相減（`src/timer_engine.py:102-104, 124-127, 156-157, 202-204, 232-242`），暫停時長全被計入——與檔內明文「pause 期間所有 elapsed 計數凍結」（`timer_engine.py:43-46`）矛盾。後果：暫停後恢復可立即誤觸發離席重置、立即重發提醒、fixed 模式折抵休息、REST_ENDED 的 DB 時長灌水。
- **修正要求**：pause 記錄起點、resume 將非 None 的絕對時間戳整體前移暫停時長（等效凍結）；或改為與 `_rest_accumulated` 相同的 dt 累計式。
- **驗收標準**：AWAY／REMINDING／RESTING(fixed)／AWAITING_RETURN 各狀態跨暫停的時長與事件正確（不誤觸發、不灌水）；補單元測試。

#### 4.5 `presence.roi` 與同族欄位完全未驗證

- **現況／根因**：`validate()` 不檢查 roi；`_roi_from_raw` 對 4 元素 list 直接 `float()`（`src/config.py:345-349`），畸形值（null／字串）以原始 `TypeError`/`ValueError` 從 `load_config` 外洩，`main()` 無捕獲（`src/main.py:87`）→ 原始 traceback 崩潰，違反「設定錯誤一律以 `ConfigError` 列出」契約；越界值（負數、>1、寬高 0）靜默接受，在席偵測靜默失效。同族：`detection.interval_sec`、`source.reconnect_interval_sec`、`webcam_index` 也未驗證型別。
- **修正要求**：`validate()` 補 roi 檢查（長度 4、皆為數值、值域 [0,1]、寬高 > 0）與上述同族欄位的型別／值域檢查；所有設定錯誤以 `ConfigError` 呈現。
- **驗收標準**：畸形與越界 config 啟動時得到清楚的 `ConfigError` 訊息；合法值不受影響；補測試。

#### 4.6 worker 訊號接 lambda，托盤 UI 操作跑在偵測執行緒

- **現況／根因**：`worker.timer_updated` / `connection_status` 連接到 lambda（`src/main.py:138, 140`）。PySide6 中非 QObject callable 在**發射端執行緒**直接執行，lambda 內的 `tray.set_timer_state` / `set_connection` 最終呼叫 `QSystemTrayIcon.setToolTip`——Qt UI 操作於偵測執行緒執行，屬未定義行為。
- **修正要求**：worker 訊號改連至 QObject slot（或等效機制），確保跨執行緒為 queued connection、UI 操作一律在主執行緒。
- **驗收標準**：所有 worker 訊號的接收端皆在主執行緒執行（檢視全部 `connect` 呼叫點，並以測試或斷言佐證）。

#### 4.7 設定視窗持舊 config，儲存會把新框的 ROI 蓋回舊值

- **現況／根因**：`MainWindow` 與 `SettingsWindow` 各持啟動時的同一份初始 config（`src/main.py:100, 105`）。框選 ROI 只更新 MainWindow 持有的 config 並寫檔（`src/ui/main_window.py:119-123`），SettingsWindow 不知情；`presence.roi` 又不在 SCHEMA 中。之後開設定視窗按儲存，以舊 config 為基底寫檔（`src/ui/settings.py:256`）→ **新 ROI 被蓋回舊值**（反向順序亦同理）。
- **修正要求**：儲存時以最新狀態為基底（例如儲存當下重讀磁碟 config、或兩視窗共享單一最新 config 來源），SCHEMA 以外的欄位不得被舊值覆寫。
- **驗收標準**：「先框 ROI → 再存設定」與「先存設定 → 再框 ROI」兩種順序下，ROI 與設定值皆保留；補測試。

#### 4.8 「啟用紀錄」（`logging.enabled`）完全無作用

- **現況／根因**：設定頁提供開關（`src/ui/settings_schema.py:212-218`），但全程式無任何地方讀取它；worker `_dispatch` 一律寫入 SQLite（`src/app/worker.py:199-210`）。
- **修正要求**：`logging.enabled = false` 時不寫入工作／休息紀錄（不建 store 或寫入前判斷，擇一）；hint 如實描述行為。
- **驗收標準**：關閉後觸發工作／休息結束，DB 無新列；開啟後照常寫入；補測試。

#### 4.9 預覽區文字提示被影格立即清除

- **現況／根因**：`PreviewView` 用同一個 QLabel 承載影像（`setPixmap`）與文字（`setText`），兩者互斥（`src/ui/widgets/preview_view.py:34-40, 48-55`）；主程式以 33ms 週期持續 `set_frame`（`src/main.py:124-133`），ROI 編輯提示與覆蓋文字設定後最長 33ms 即被清除，使用者實際上看不到。
- **修正要求**：文字與影像分離呈現（獨立覆蓋層或於繪製時疊加），影像持續更新下提示仍可見。
- **驗收標準**：進入 ROI 編輯模式時提示文字持續顯示直到退出；錯誤覆蓋文字在影像更新下仍可見。

#### 4.10 RTSP 無逾時且關閉時 join 無上限，GUI 可永久卡死

- **現況／根因**：`RTSPSource.open()` 未設 `CAP_PROP_OPEN_TIMEOUT_MSEC` / `CAP_PROP_READ_TIMEOUT_MSEC`（`src/capture/video_source.py:57-58`），FFmpeg 在伺服器無回應／TCP 半開時 `VideoCapture(...)` 與 `read()` 可阻塞數十秒至無限期；此時 `_grab_loop` 卡在 `read()`，而 `FrameGrabber.stop()` 的 `join()` 無 timeout（`src/capture/frame_grabber.py`），由 GUI 執行緒呼叫 → 關閉程式時整個 GUI 無限卡死。
- **修正要求**：RTSP 設定 open/read 逾時；`stop()` 的 join 加 timeout，逾時記 log 並放行關閉流程。
- **驗收標準**：模擬來源 read 永久阻塞時，關閉程式於合理時間內（如 ≤ 3 秒）完成退出；正常串流關閉行為不變。

### 🟢 Low

#### 4.11 托盤／主視窗暫停切換不同步

- **現況／根因**：暫停有兩個入口（主視窗 checkable 按鈕、托盤選單 `src/main.py:182`），`_toggle_pause` 只更新托盤文字（`src/main.py:152-161`），不回寫主視窗按鈕 checked 狀態。從托盤暫停後，主視窗按鈕第一次點擊會重送同向指令、顯示錯誤文字。
- **修正要求**：暫停狀態單一事實來源，任一入口切換後兩處 UI（按鈕 checked／文字、托盤文字）同步。
- **驗收標準**：任意交錯操作兩入口，狀態與顯示始終一致；補測試。

#### 4.12 `rest_placeholder.png` 損壞（截圖中 libpng 錯誤的來源）

- **現況／根因**：逐 chunk 驗證 CRC32 確認 `data/assets/rest_placeholder.png` 的 IDAT chunk CRC 不符（stored=ef9a430d、calc=efa2a75b）；`cv2.imread` 載入即重現「libpng error: IDAT: CRC error」並回傳 None，QPixmap 同樣失敗。此為 `popup.media_path` 的程式預設值指向的資產（`src/config.py:48`）。
- **修正要求**：以完好影像重新產生／替換該資產。
- **驗收標準**：啟動與 popup 載入預設媒體無 libpng 錯誤；該檔可被 QPixmap 正常解碼。

#### 4.13 `is_opened` 跨執行緒競態可使偵測迴圈死亡

- **現況／根因**：`is_opened` 對 `self._cap` 做兩次無鎖讀取（`src/capture/video_source.py:76`）；grabber 執行緒重連時 `release()` 把 `_cap` 設為 None（`video_source.py:111` 觸發），與 worker 執行緒輪詢 `is_opened`（`src/app/worker.py:78`）競態，極端時機拋 `AttributeError` → worker 例外 → 偵測迴圈永久死亡。
- **修正要求**：以區域變數快照後判斷（或加鎖），消除 TOCTOU。
- **驗收標準**：競態情境（可注入模擬）不再拋例外；補測試。

#### 4.14 `work_threshold_min` 被 `int()` 截斷，floating 倒數錯誤

- **現況／根因**：`ReminderContext.work_minutes = int(cfg.timer.work_threshold_min)`（`src/main.py:59`）截斷小數；`FloatingReminder.show` 以 `max(work_minutes * 60, 1)` 當倒數秒數（`src/reminder/floating.py:31`）。現行設定 0.1 分 → 倒數 1 秒（應為 6 秒）；任何小數分鐘最多少算近 60 秒。
- **修正要求**：保留小數精度（context 改存 float 或直接存秒數），倒數秒數 = `round(work_threshold_min * 60)`。
- **驗收標準**：0.1 分 → 6 秒、25.5 分 → 1530 秒；補測試。

#### 4.15 托盤圖示引用不存在的 `icon_1024.png`

- **現況／根因**：`load_app_icon` 預設路徑 `data/assets/icon_1024.png` 不存在（`src/ui/icons.py:26`），實際資產為 `icon.png`（完好、1024×1024）；`Path.exists()` 失敗後永遠使用程式產生的藍底「H」備援圖示，出貨資產是死檔案。對應測試恆真（`tests/test_icons.py:28`），資產缺失也不會失敗。
- **修正要求**：預設路徑改指向實際資產 `icon.png`（或補上正確檔名的資產，擇一）；修正恆真測試使其在資產缺失時失敗。
- **驗收標準**：托盤顯示實際圖示資產；刪除資產時對應測試會失敗。

#### 4.16 badge 的 `muted` / `neutral` role 無對應 QSS 樣式

- **現況／根因**：主題 QSS 僅定義 `secondary/danger/warning/success/info`（`src/ui/theme.py:70-88`）；`PresenceBadge` 無人狀態用 `muted`（`src/ui/widgets/presence_badge.py:39`）、`ConnectionBadge` 待機狀態經 `severity()` 對應 `neutral`（`src/app/connection_state.py:25`），皆無樣式，退回預設文字色，與 docstring 宣稱的「灰色」不符。
- **修正要求**：QSS 補上 `muted` / `neutral` 樣式（灰色系），或統一改用既有 role，擇一並保持兩個 badge 一致。
- **驗收標準**：無人／待機狀態的 badge 呈現預期的灰色樣式；role 與 QSS 的對應有測試或檢查防回歸。

#### 4.17 `CAP_PROP_BUFFERSIZE` 對 FFMPEG 後端是 no-op

- **現況／根因**：`RTSPSource.open()` 呼叫 `set(cv2.CAP_PROP_BUFFERSIZE, 1)` 試圖降低 RTSP 延遲，實測本機 OpenCV 4.13.0 FFMPEG 後端回傳 False、屬性值為 0——整行無效且失敗未被檢查或記錄（`src/capture/video_source.py:58`）。
- **修正要求**：移除無效設定或改用有效手段，`set()` 類呼叫的回傳值需檢查並於失敗時記 log；降延遲仍由既有高頻抽幀機制承擔。
- **驗收標準**：程式碼不再包含無聲失敗的無效設定；若保留設定行為，失敗時 log 有記錄。

---

## 5. 設定結構彙整（新增／異動總覽）

本輪**不新增、不變更任何設定鍵**。三項新功能皆為純 UI／行為層功能；需求四僅讓既有設定鍵（如 `logging.enabled`）的行為與宣告一致。

| 區域 | 變更 | 對應需求 |
| --- | --- | --- |
| `src/ui/settings.py` / `settings_schema.py` | 運算裝置旁「檢查」按鈕、音檔欄位試聽按鈕、瀏覽對話框副檔名過濾 | 需求一、二、三 |
| `src/detection/detector.py` | CUDA 檢查邏輯（新模組或併入）、CUDA 失敗退回 CPU | 需求一 |
| `src/reminder/sound.py` / `popup.py` | QSoundEffect → QMediaPlayer＋QAudioOutput、hide 停音 | 需求二、三（共用元件） |
| `src/ui/strings.py` | 新增按鈕／對話框／提示字串 | 需求一、三 |
| `src/timer_engine.py`、`src/app/worker.py`、`src/capture/*`、`src/ui/*`、`src/config.py`、`data/assets/*` | 17 項錯誤修正 | 需求四 |

---

## 6. 非目標（Out of Scope）

- 不新增音量控制（維持系統音量，全程式不引入 volume 設定）。
- 不調整偵測／計時演算法與狀態機設計（需求四僅做修復所需的最小變更）。
- 不處理 `[h264] co located POCs unavailable` 訊息（FFmpeg 解碼 RTSP 的無害警告，不影響功能）。
- 不修改 `environment.yml` 的依賴宣告（現有 CUDA 版 torch 為手動安裝、無法由該檔重現一事，記錄於第 8 節供日後處理）。
- 不新增或轉換音檔資產（需求二完成後 mp3 可直接播放）。
- 不重構與本次需求無關的既有模組。

---

## 7. 測試考量

- **需求一**：檢查邏輯純函式化後對四種狀態做單元測試（mock torch 各狀態）；按鈕防重入與「檢查中…」狀態；fallback 以注入失敗的裝置初始化驗證「不終止、記 log、UI 提示」。
- **需求二**：沿用 `FakePlayer` 注入測試（介面不變應全數通過）；新增「檔案存在但格式不支援」情境（本次 bug 未被攔截的測試缺口）；popup hide 停音。
- **需求三**：試聽的播放／停止狀態切換、互斥（單一播放）、關窗自動停止、無效檔錯誤 hint（可注入 FakePlayer 驗證，不需真實發聲）。
- **需求四**：各項驗收標準已內含測試要求；重點補齊本次根因揭露的系統性缺口——暫停期間指令與跨暫停計時（4.1、4.4）、斷線／新影格語意（4.2）、ROI 座標換算幾何（4.3）、畸形 config 驗證（4.5）、恆真測試修正（4.15）。
- 完成定義沿用專案慣例：`rtk pytest`、`rtk ruff check .`、`rtk mypy src cli` 全數通過。

---

## 8. 其他觀察（記錄事實，不列入本輪需求）

- `environment.yml` 的 pip 區僅列 `ultralytics`（未釘版本、未宣告 torch、未指定 CUDA wheel 來源）；現行環境的 `torch 2.9.1+cu128` 無法由該檔重現，重建環境會得到 CPU 版 torch。日後可考慮在 README／environment.yml 明確記錄 GPU 環境安裝步驟。
- README 的 config 範例與功能描述停留在較早版本（無 `return_sound`、`force_lock` 等區段），可於日後文件更新一併處理。
- 上一輪 proposal（休息提醒系統功能擴充）已全部實作完成，惟 `docs/tasks/progress.md` 中「手動驗收（Windows）」4 項尚未勾選。
