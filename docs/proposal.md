# 人體辨識休息提醒系統 — 需求文檔 (Proposal)

| 項目 | 內容 |
|---|---|
| 文件名稱 | 人體辨識休息提醒系統 需求文檔 |
| 版本 | v1.0 (MVP) |
| 日期 | 2026-06-09 |
| 狀態 | 待開發 |
| 平台 | Windows 11 桌面 |
| Python | 3.11+ (conda 環境名稱:`project`) |

---

## 1. 專案概述

### 1.1 目標

一個跑在 **Windows 桌面**的個人健康工具。透過攝影機(**RTSP 為主、USB webcam 為輔**)即時判斷使用者是否坐在座位上工作;當使用者**連續工作達設定時間 (N 分鐘)** 時提醒休息。若工作期間離開超過設定時間 (M 分鐘),自動將工作計時歸零。

### 1.2 要解決的問題

長時間連續工作而忘記休息,造成眼睛與身體疲勞。本系統用電腦視覺自動偵測「人是否真的坐在電腦前」,只在真正工作時計時,並在適當時機主動提醒。

### 1.3 使用對象

**個人自用**。跑在使用者自己的電腦上,不需考慮多使用者、跨環境相容或產品化打包。

### 1.4 設計原則

- **MVP 優先**:先把核心價值(偵測 + 計時 + 提醒)做穩,其餘列為後續階段。
- **模組化**:影像來源、提醒方式都做成可抽換,各模組單一職責、可獨立測試。
- **可設定**:核心參數與行為可由使用者在 UI 或設定檔調整。

---

## 2. 名詞定義 (Glossary)

| 名詞 | 定義 |
|---|---|
| **在場 / 工作中** | 攝影機畫面中偵測到「人」,其偵測框中心落在使用者框選的**座位區 (ROI)** 內,**且**框高度 ≥ 畫面高度的設定比例(代表夠靠近、真的坐著)。 |
| **離開** | 不滿足上述「在場」條件。 |
| **N(工作提醒門檻)** | 連續工作累計達此時間即觸發休息提醒。 |
| **M(離開重置門檻)** | 離開時間若 ≤ M,工作計時暫停凍結;若 > M,視為已休息,工作計時歸零。 |
| **R(提醒後所需休息)** | 提醒觸發後,需離開達此時間才算休息完成、可開始下一輪。預設 = M。 |
| **去抖動 (Debounce)** | 連續數次偵測結果一致才切換「在場/離開」狀態,避免偵測瞬斷造成計時閃爍。 |
| **ROI** | Region of Interest,使用者在畫面上框選的「座位區」矩形。 |

---

## 3. 範圍 (Scope)

### 3.1 MVP 納入 ✅

1. 即時影像取得(RTSP 預設 / webcam,可切換)。
2. YOLOv8 人體偵測。
3. 在場判定(ROI + 大小門檻 + 去抖動)。
4. 工作 / 休息計時狀態機(N / M / R)。
5. 休息提醒,三種方式可切換:彈出視窗(預設,含圖片/影片)、系統通知、置頂懸浮倒數視窗。
6. 提醒後重置邏輯,三種模式可切換(預設:偵測為準)。
7. 完整主視窗 UI(即時預覽 + 偵測框 + 座位區 + 計時) + 系統匣。
8. 設定管理(UI 可調 + 設定檔持久化 + 驗證)。
9. 基本記錄寫檔(SQLite):每段工作 / 休息的開始、結束、長度。

### 3.2 後續階段 ⏸️(本次不做,但架構預留)

- 統計圖表、每日工作時間統計、工作效率分析、休息模式分析、歷史趨勢檢視。
- 記錄匯出、設定檔匯入 / 匯出。
- **強制休息模式**(以指令鎖定 window 強制使用者休息)。
- 進階使用者偏好管理。

### 3.3 明確不做 ❌

- **Docker 部署**(已從計畫移除)。
- 多使用者 / 雲端 / 跨平台(僅 Windows 桌面、個人自用)。

---

## 4. 系統架構

### 4.1 資料流

```
影像來源(RTSP/webcam)
   → 偵測(YOLOv8 person)
   → 在場判定(ROI + 大小 + 去抖動)
   → 計時狀態機(N / M / R)
   → 提醒系統(彈窗 / 通知 / 置頂倒數)
                       ↘ 記錄寫檔(SQLite)
   主視窗 UI(即時預覽 + 偵測框 + 座位區 + 計時) / 系統匣 / 設定
```

### 4.2 模組與職責

| 模組 | 職責 | 主要相依 |
|---|---|---|
| `capture/video_source.py` | 抽象影像來源:RTSP / webcam,含**斷線自動重連** | OpenCV |
| `detection/detector.py` | 封裝 YOLOv8,輸入影格輸出 person 偵測框 | ultralytics |
| `presence.py` | ROI + 大小判定 + 去抖動 → 輸出「在場 / 離開」 | numpy |
| `timer_engine.py` | 工作 / 休息狀態機,維護計時與狀態轉移 | — |
| `reminder/base.py` | 提醒元件共同介面 | — |
| `reminder/popup.py` | 彈出視窗(圖片 / 影片 + 提示音) | PySide6 |
| `reminder/toast.py` | 系統通知 | PySide6 / plyer |
| `reminder/floating.py` | 置頂懸浮倒數視窗 | PySide6 |
| `ui/main_window.py` | 主視窗:即時預覽、偵測框、座位區、計時 | PySide6 |
| `ui/settings.py` | 設定介面 | PySide6 |
| `ui/tray.py` | 系統匣 | PySide6 |
| `config.py` | 設定載入 / 驗證 / 儲存 | pyyaml |
| `logging_store.py` | 工作 / 休息記錄寫入 | sqlite3 |
| `main.py` | 進入點,組裝各模組、啟動事件迴圈 | — |

### 4.3 建議檔案結構

```
human-presence-detector/
├─ src/
│  ├─ main.py
│  ├─ config.py
│  ├─ capture/video_source.py
│  ├─ detection/detector.py
│  ├─ presence.py
│  ├─ timer_engine.py
│  ├─ reminder/{base,popup,toast,floating}.py
│  ├─ ui/{main_window,settings,tray}.py
│  └─ logging_store.py
├─ data/
│  ├─ model/yolov8n.pt          # 已存在
│  ├─ assets/rest_placeholder.png  # 預設假圖(實作時建立)
│  └─ records.sqlite            # 執行時產生
├─ config.yaml                  # 設定檔
├─ environment.yml              # conda 環境
├─ docs/proposal.md             # 本文件
└─ README.md
```

---

## 5. 功能需求 (Functional Requirements)

### FR-1 影像來源
- FR-1.1 支援兩種來源:**RTSP 串流(預設)** 與 **本機 USB webcam**,以設定檔/UI 切換。
- FR-1.2 來源以統一介面封裝,上層模組不需知道來源型別。
- FR-1.3 RTSP **斷線時自動重連**(間隔可設定),重連期間 UI 顯示連線狀態,不可使程式崩潰。
- FR-1.4 取得的影格供偵測與 UI 預覽共用。

### FR-2 人體偵測
- FR-2.1 使用 **YOLOv8**(模型 `data/model/yolov8n.pt`,已備)偵測類別 person。
- FR-2.2 偵測頻率可設定(預設每 1 秒一次),不需逐影格偵測。
- FR-2.3 置信度低於門檻(預設 0.4)的偵測捨棄。
- FR-2.4 支援 GPU(CUDA)加速,偵測不到 GPU 時自動退回 CPU。
- FR-2.5 偵測在獨立執行緒進行,不可阻塞 UI。

### FR-3 在場判定
- FR-3.1 使用者可在即時預覽畫面上**拖拉框選座位區 (ROI)**;ROI 以畫面比例儲存以適應不同解析度。
- FR-3.2 「在場」需**同時**滿足:(a) 偵測框中心落在 ROI 內;(b) 框高度 ≥ 畫面高度的設定比例(預設 25%)。
- FR-3.3 套用**去抖動**:連續 N 次(預設 3)判定一致才切換在場/離開狀態。
- FR-3.4 畫面同時有多人時,只要**任一人**滿足在場條件即視為在場。

### FR-4 計時狀態機(詳見第 6 節)
- FR-4.1 在場時工作計時持續累加。
- FR-4.2 短暫離開(≤ M)時計時**暫停凍結**,回到座位後從原值繼續累加。
- FR-4.3 離開超過 M 時工作計時**歸零**,並記錄該段工作結束。
- FR-4.4 工作計時達 N 時觸發提醒。

### FR-5 休息提醒
- FR-5.1 提供三種提醒方式,使用者可切換,**預設為彈出視窗**:
  - **彈出視窗 + 提示音(預設)**:明顯視窗,**可顯示圖片或影片**;預設載入一張預設假圖,使用者可替換為自訂圖片或影片。
  - **系統通知 (toast)**:右下角通知。
  - **置頂懸浮倒數視窗**:畫面常駐置頂小視窗顯示倒數,時間到以閃爍 / 變色提醒。
- FR-5.2 提示音、提醒媒體(圖片/影片)的檔案路徑可設定。

### FR-6 提醒後重置邏輯
提供三種模式,使用者可切換,**預設為模式 1**:
- FR-6.1 **模式 1 — 偵測為準(預設)**:提醒後需真的離開達 R 分鐘,系統確認休息完成才將工作計時歸零;未離開則每隔設定間隔(預設 2 分鐘)持續提醒。
- FR-6.2 **模式 2 — 點掉即重置**:按下提醒視窗即將工作計時歸零,立刻開始下一輪。
- FR-6.3 **模式 3 — 兩段式**:點掉只是貪睡(snooze)X 分鐘後再響;真正歸零仍需離開達 R 分鐘。

### FR-7 主視窗 UI
- FR-7.1 顯示攝影機**即時影像預覽**。
- FR-7.2 疊加顯示**偵測框、座位區 (ROI) 框線、目前狀態與工作計時**。
- FR-7.3 提供在預覽上框選 / 調整座位區的操作。
- FR-7.4 可最小化至系統匣於背景執行。

### FR-8 系統匣
- FR-8.1 提供系統匣圖示,可開啟主視窗 / 設定、暫停或繼續偵測、結束程式。
- FR-8.2 圖示或提示反映目前狀態(工作中 / 離開 / 提醒中)。

### FR-9 設定管理
- FR-9.1 所有可調項目(來源型別、RTSP 網址、webcam 編號、N/M/R、各門檻、去抖動、提醒方式與媒體、重置模式等)可在 UI 設定介面調整。
- FR-9.2 設定持久化於 `config.yaml`,啟動時載入,修改後寫回。
- FR-9.3 設定載入與儲存需**驗證**(網址格式、數值範圍、檔案存在性),不合法時給予明確提示並退回安全預設。

### FR-10 記錄寫檔
- FR-10.1 每段工作 / 休息的開始時間、結束時間、長度、結束原因寫入本機 **SQLite**(`data/records.sqlite`)。
- FR-10.2 MVP 僅負責寫入;讀取分析、圖表、匯出列為後續階段(schema 預留)。

---

## 6. 計時狀態機詳述 ⭐

### 6.1 狀態

| 狀態 | 說明 |
|---|---|
| **IDLE(待機)** | 尚無人在場,工作計時 = 0。 |
| **WORKING(工作中)** | 在場,工作計時持續累加。 |
| **PAUSED(短暫離開)** | 離開但離開時間 ≤ M,工作計時凍結。 |
| **REMINDING(提醒中)** | 工作計時達 N,提醒進行中。 |

### 6.2 狀態轉移

| 來源狀態 | 事件 / 條件 | 目標狀態 | 動作 |
|---|---|---|---|
| IDLE | 偵測到在場 | WORKING | 開始工作計時 |
| WORKING | 離開 | PAUSED | 凍結工作計時,啟動離開計時 |
| WORKING | 工作計時達 N | REMINDING | 觸發提醒 |
| PAUSED | 在場 且 離開時間 ≤ M | WORKING | 繼續累加工作計時 |
| PAUSED | 離開時間 > M | IDLE | 工作計時歸零,記錄該段工作 |
| REMINDING | 模式1:離開達 R | IDLE | 歸零,記錄工作段 + 休息段 |
| REMINDING | 模式1:離開未達 R 後又在場 | REMINDING | 維持提醒(按間隔重複) |
| REMINDING | 模式2:點掉提醒 | WORKING | 歸零,立即開始新一輪 |
| REMINDING | 模式3:點掉提醒 | REMINDING | 貪睡 X 分鐘後再提醒;離開達 R 才歸零 |

### 6.3 文字流程示意

```
IDLE ──在場──> WORKING ──工作達 N──> REMINDING
                 │  ↑                    │
            離開 │  │ 在場(≤M)           │ 離開達 R(模式1)
                 ↓  │                    ↓
              PAUSED ──離開>M──> IDLE <───┘(記錄工作+休息)
```

---

## 7. 預設參數

| 參數 | 說明 | 預設值 | 可調 |
|---|---|---|---|
| **N** 工作提醒門檻 | 連續工作多久後提醒 | **45 分鐘** | ✅ |
| **M** 離開重置門檻 | 離開多久視為休息並重置(短於此僅暫停) | **5 分鐘** | ✅ |
| **R** 提醒後所需休息 | 提醒後需離開多久才算休息完成(預設 = M) | **5 分鐘** | ✅ |
| 偵測間隔 | 每隔多久跑一次 YOLO | 1 秒 | ✅ |
| 信心門檻 | person 置信度下限 | 0.4 | ✅ |
| 大小門檻 | 偵測框高 ≥ 畫面高比例 | 25% | ✅ |
| 去抖動次數 | 連續幾次一致才切換狀態 | 3 次 | ✅ |
| 提醒重複間隔 | 模式 1 未休息時多久再提醒 | 2 分鐘 | ✅ |
| 貪睡 X | 模式 3 貪睡多久再響 | 5 分鐘 | ✅ |
| RTSP 重連間隔 | 斷線後多久重試 | 5 秒 | ✅ |

---

## 8. 技術方案

### 8.1 採用方案

| 層 | 選用 | 理由 |
|---|---|---|
| GUI | **PySide6 (Qt)** | 原生支援影片播放、置頂視窗、系統匣、在預覽上畫 ROI,完全契合需求 |
| 影像擷取 | **OpenCV (`cv2.VideoCapture`)** | RTSP / webcam 通吃,成熟穩定 |
| 偵測 | **Ultralytics YOLOv8** | yolov8n 已備,API 簡潔,支援 CPU/GPU |
| 設定 | **PyYAML** | 人類可讀設定檔 |
| 記錄 | **sqlite3(標準庫)** | 免額外服務,為後續統計鋪路 |

### 8.2 已評估的替代方案(不採用)

- **Tkinter + plyer**:標準庫、輕量,但**彈出視窗放影片困難**、置頂/系統匣較陽春,不符合需求。
- **FastAPI + 瀏覽器 UI**:日後做圖表方便,但桌面置頂、系統匣、(後續的)強制鎖定都需額外處理,對個人桌面應用過重。

### 8.3 環境

- conda 環境名稱:`project`,Python 3.11+。
- 主要套件:`pyside6`、`opencv-python`、`ultralytics`、`pyyaml`(toast 視情況用 `plyer`)。
- 以 `environment.yml` 管理。GPU 為可選;無 CUDA 時以 CPU 低頻偵測執行。

---

## 9. 資料設計

### 9.1 設定檔 `config.yaml`(結構示意)

```yaml
source:
  type: rtsp                # rtsp | webcam
  rtsp_url: "rtsp://user:pass@host:554/stream"
  webcam_index: 0
  reconnect_interval_sec: 5

detection:
  model_path: "data/model/yolov8n.pt"
  interval_sec: 1.0
  confidence: 0.4
  device: auto              # auto | cpu | cuda

presence:
  roi: [0.30, 0.20, 0.40, 0.70]   # x, y, w, h(畫面比例)
  min_box_height_ratio: 0.25
  debounce_count: 3

timer:
  work_threshold_min: 45    # N
  reset_threshold_min: 5    # M
  required_rest_min: 5      # R

reminder:
  method: popup             # popup | toast | floating
  reset_mode: detection     # detection | dismiss | snooze
  repeat_interval_min: 2
  snooze_min: 5
  popup:
    media_path: "data/assets/rest_placeholder.png"
    media_type: image       # image | video
    sound_path: ""
  floating:
    position: top-right

logging:
  enabled: true
  db_path: "data/records.sqlite"

ui:
  start_minimized: false
```

### 9.2 SQLite Schema(MVP)

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    type         TEXT    NOT NULL,   -- 'work' | 'rest'
    start_ts     TEXT    NOT NULL,   -- ISO8601
    end_ts       TEXT,
    duration_sec INTEGER,
    ended_by     TEXT                -- 'reset' | 'reminder' | 'manual' | 'rest_done'
);
```

---

## 10. 非功能需求 (Non-Functional Requirements)

| 類別 | 需求 |
|---|---|
| **效能** | 偵測在獨立執行緒、低頻執行,UI 維持流暢(預覽不卡頓)。 |
| **可靠性** | RTSP 斷線自動重連;任何單一影格/偵測錯誤不得使程式崩潰。 |
| **可用性** | 介面為繁體中文;座位區框選直覺;預設值即可正常運作。 |
| **可維護性** | 模組單一職責、介面清晰;來源與提醒可抽換;核心狀態機可獨立單元測試。 |
| **資源** | 至少 4GB RAM(建議 8GB+);CUDA GPU 可選。 |

---

## 11. MVP 驗收標準

1. 能從 RTSP(預設)或 webcam 取得影像並在主視窗即時預覽。
2. 能在預覽上框選座位區 (ROI),並設定大小門檻。
3. 坐在座位區且夠近時開始累計工作時間;短暫離開(≤ M)暫停;離開達 M 重置。
4. 工作達 N 觸發提醒,預設彈出視窗(顯示預設假圖 + 提示音),可切換為 toast / 置頂倒數。
5. 提醒後依預設模式 1,需真的離開達 R 分鐘才重置並開始下一輪。
6. 每段工作 / 休息寫入 `data/records.sqlite`。
7. 設定(來源、RTSP 網址、N/M/R、各門檻、提醒方式)可在 UI 調整並保存至 `config.yaml`。
8. RTSP 斷線能自動重連而不崩潰。

---

## 12. 風險與待確認事項

| 項目 | 說明 |
|---|---|
| 預設假圖資產 | 實作時於 `data/assets/` 建立預設假圖;因 `.gitignore` 忽略 `/data`,如需隨版控散布需另行調整忽略規則(使用者自行處理 git)。 |
| 影片播放格式 | 彈窗播放影片之編解碼相依於系統 Qt multimedia 後端,需於實作時確認常見格式(mp4/h264)可播。 |
| RTSP 延遲 | 高延遲或不穩定串流可能影響在場判定即時性;以低頻偵測 + 去抖動緩解。 |
| GPU 環境 | 若需 CUDA 加速,須另行安裝對應的 PyTorch CUDA 版本。 |

---

## 附錄:與原始 README 的對應

- README 中「攝像頭 / RTSP Server」的矛盾 → 確定為 **RTSP 預設 + webcam 輔助(可切換)**。
- README 中「Docker 部署」 → **移除**。
- README 中統計 / 分析 / 匯出 / 匯入 / 強制休息 → 列為**後續階段**,MVP 不實作但架構與資料表預留。
- README 中「懸浮置頂倒數視窗」 → 納入 MVP,作為三種提醒方式之一。
