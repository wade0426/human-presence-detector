# 人體辨識休息提醒系統

一個以 Windows 桌面為目標的個人健康工具。系統透過 RTSP 或 webcam 擷取畫面，使用 YOLOv8 偵測人體，判斷使用者是否真的坐在座位前工作，並在連續工作達門檻後主動提醒休息。

## 功能特色

- 支援兩種影像來源：`RTSP` 與 `webcam`
- 使用 `YOLOv8` 進行人體偵測
- 以 `ROI + 人體框高度門檻 + 去抖動` 判定是否在場
- 內建工作 / 短暫離開 / 提醒中的計時狀態機
- 支援三種提醒方式：
  - 彈出視窗
  - 系統通知
  - 置頂懸浮倒數視窗
- 支援三種提醒後重置模式：
  - `detection`：離開達休息門檻才重置
  - `dismiss`：按掉提醒立即重置
  - `snooze`：先貪睡，再次提醒；真正重置仍要離開達門檻
- 設定可持久化到 [config.yaml](/D:/Code/Python/human-presence-detector/config.yaml)
- 工作 / 休息紀錄寫入 SQLite

## 系統需求

- Windows 11
- Python 3.11+
- 建議使用 conda 環境 `project`
- 可選 GPU：若要使用 CUDA，需自行安裝對應 PyTorch CUDA 環境

## 快速開始

### 1. 建立環境

```powershell
conda env create -f environment.yml
conda activate project
```

如果你不是用 conda，也可以手動安裝：

```powershell
python -m pip install PySide6 opencv-python ultralytics pyyaml pytest pytest-qt
```

### 2. 檢查模型與設定

- YOLO 模型預設路徑：`data/model/yolov8n.pt`
- 預設設定檔：`config.yaml`
- 預設提醒圖片：`data/assets/rest_placeholder.png`

若使用 RTSP，請先把 `config.yaml` 的 `source.rtsp_url` 改成你的串流位址；若使用 webcam，請把 `source.type` 改為 `webcam`。

### 3. 啟動程式

```powershell
python -m src.main
```

或：

```powershell
python src/main.py
```

## 打包成 Windows 應用程式

把專案打包成帶自家圖示、可直接執行的 onedir 應用程式：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

產物在 `dist/HumanPresenceDetector/`，整包壓縮即可發佈。詳見
[packaging/README.md](packaging/README.md)（圖示如何生效、路徑解析設計、疑難排解）。

## 設定說明

主要設定位於 [config.yaml](/D:/Code/Python/human-presence-detector/config.yaml)：

```yaml
source:
  type: rtsp
  rtsp_url: "rtsp://user:pass@host:554/stream"
  webcam_index: 0

detection:
  confidence: 0.4
  interval_sec: 1.0
  device: auto

presence:
  roi: [0.3, 0.2, 0.4, 0.7]
  min_box_height_ratio: 0.25
  debounce_count: 3

timer:
  work_threshold_min: 45
  reset_threshold_min: 5
  required_rest_min: 5

reminder:
  method: popup
  reset_mode: detection
```

幾個最常調的參數：

- `source.type`：`rtsp` 或 `webcam`
- `detection.confidence`：人體偵測信心門檻
- `presence.roi`：座位區域，使用比例座標 `[x, y, w, h]`
- `timer.work_threshold_min`：連續工作多久提醒
- `timer.reset_threshold_min`：離開多久視為真正休息
- `reminder.method`：`popup`、`toast`、`floating`
- `reminder.reset_mode`：`detection`、`dismiss`、`snooze`

## 專案結構

```text
src/
├─ main.py
├─ types.py
├─ config.py
├─ presence.py
├─ timer_engine.py
├─ logging_store.py
├─ capture/
│  └─ video_source.py
├─ detection/
│  └─ detector.py
├─ app/
│  └─ worker.py
├─ reminder/
│  ├─ base.py
│  ├─ popup.py
│  ├─ toast.py
│  ├─ floating.py
│  └─ factory.py
└─ ui/
   ├─ main_window.py
   ├─ settings.py
   └─ tray.py
```

分層概念：

- 核心純邏輯：`types`、`config`、`presence`、`timer_engine`
- I/O 介面卡：`video_source`、`detector`、`logging_store`
- Qt 接線層：`app/worker`
- Qt UI：`reminder/*`、`ui/*`
- 組裝入口：`main.py`

## 測試與品質檢查

執行完整測試：

```powershell
rtk pytest tests/ -v --tb=short
```

型別檢查：

```powershell
rtk mypy src/ --strict --ignore-missing-imports
```

Lint：

```powershell
rtk ruff check src/ tests/
```

目前這個工作區的狀態：

- `pytest`: 46 passed
- `mypy`: 0 errors
- `ruff`: 0 errors

## 目前實作狀態

已完成：

- 專案骨架與環境設定
- 共用型別與設定管理
- 在場判定與計時狀態機
- 影像來源、YOLO 偵測、SQLite 記錄
- 背景 worker、提醒元件、主視窗 / 設定 / 系統匣
- `main.py` 組裝入口

待完成：

- 依實機 RTSP / webcam 做完整手動驗收
- 驗證影片提醒格式相容性
- 視需要補強更多 UI 行為與端到端情境

## 手動驗收重點

建議至少確認以下項目：

1. 能從 RTSP 或 webcam 取得影像。
2. 能在預覽上框選 ROI。
3. 坐在 ROI 內時工作時間會累積。
4. 短暫離開時會暫停，離開超過門檻會重置。
5. 工作達門檻後會跳出提醒。
6. `data/records.sqlite` 有正確寫入工作 / 休息紀錄。
7. 設定可以透過 UI 或 `config.yaml` 調整並保存。
8. RTSP 斷線時程式不崩潰並能重連。

## 注意事項

- `data/` 目前被 `.gitignore` 忽略，執行產物與本地資產預期不進版控。
- Qt 相關測試需要 `PySide6` 與 `pytest-qt`。
- 若使用 `device: cuda`，請自行確認本機 CUDA / PyTorch 環境匹配。
