# 人體辨識休息提醒系統

一個基於 YOLO 深度學習模型的智能健康提醒工具，透過攝像頭即時監控使用者是否在電腦前工作，並在適當時機提醒休息。

## 🎯 功能特色

- **智能人體檢測**: 使用 YOLO v8 模型進行即時人體檢測
- **自動計時**: 只在檢測到使用者時計算工作時間
- **智能重置**: 離開超過設定時間自動重置計時器
- **工作記錄**: 詳細記錄每日工作時段和休息情況
- **統計分析**: 提供工作時間統計和分析功能
- **可自訂設定**: 靈活調整工作時間和休息提醒間隔
- **友善介面**: 美觀易用的圖形化介面

## 📋 系統需求

- **作業系統**: Windows 10/11
- **Python 版本**: 3.8 或以上
- **硬體需求**:
  - 可用的攝像頭設備
  - 至少 4GB RAM (推薦 8GB+)
  - 支援 CUDA 的顯示卡 (可選，用於加速)

## 🚀 快速開始

### 1. 安裝依賴套件

```bash
pip install -r requirements.txt
```

### 2. 執行程式

#### 基本版本
```bash
python main.py
```

#### 增強版本 (包含工作記錄和統計功能)
```bash
python main_enhanced.py
```

### 3. 開始使用

1. 確保攝像頭正常運作
2. 點擊「開始監控」按鈕
3. 系統開始監控並計時
4. 達到設定時間會自動彈出休息提醒

## 📁 檔案結構

```
human-presence-detector/
├── main.py              # 基本版主程式
├── main_enhanced.py     # 增強版主程式 (推薦)
├── config.py            # 配置檔案
├── utils.py             # 工具模組 (記錄、設定管理)
├── requirements.txt     # 依賴套件清單
├── README.md           # 說明文件
├── 開發說明.md          # 詳細開發文檔
├── work_log.json       # 工作記錄檔 (自動生成)
└── settings.ini        # 使用者設定檔 (自動生成)
```

## ⚙️ 配置選項

### 時間設定

| 參數 | 預設值 | 說明 |
|------|--------|------|
| WORK_DURATION | 3600秒 (1小時) | 工作提醒間隔 |
| AWAY_THRESHOLD | 300秒 (5分鐘) | 離開重置閾值 |
| DETECTION_INTERVAL | 1秒 | 檢測間隔 |

### 攝像頭設定

| 參數 | 預設值 | 說明 |
|------|--------|------|
| CAMERA_INDEX | 0 | 攝像頭索引 |
| FRAME_WIDTH | 640 | 畫面寬度 |
| FRAME_HEIGHT | 480 | 畫面高度 |

可以透過程式內的設定介面或直接修改 `config.py` 來調整這些參數。

## 🔧 進階功能

### 工作記錄

增強版本提供完整的工作記錄功能：

- 自動記錄每日工作時段
- 追蹤休息和中斷時間
- 提供詳細的統計分析
- 支援記錄匯出功能

### 設定管理

- 支援設定檔的匯入/匯出
- 自動儲存使用者偏好設定
- 提供設定驗證功能

### 統計分析

- 每日工作時間統計
- 工作效率分析
- 休息模式分析
- 歷史趨勢檢視

## 🛠️ 常見問題解決

### YOLO 模型下載問題

如果指定的模型路徑不存在，程式會自動下載 YOLO 模型到當前目錄。首次執行時需要網路連線。

### 攝像頭無法使用

1. 確認攝像頭連接正常
2. 檢查是否被其他程式佔用
3. 嘗試更改 CAMERA_INDEX 參數
4. 使用程式內的「攝像頭測試」功能

### 檢測精度問題

1. 確保光線充足
2. 調整攝像頭角度和距離
3. 修改 CONFIDENCE_THRESHOLD 參數
4. 考慮使用更大的 YOLO 模型 (yolov8s.pt 或 yolov8m.pt)

### 效能最佳化

1. 使用支援 CUDA 的顯示卡
2. 安裝 PyTorch CUDA 版本
3. 降低檢測解析度
4. 調整檢測間隔

## 🎨 自訂功能

### 修改提醒訊息

編輯 `config.py` 中的 `REST_REMINDER_MESSAGE` 來自訂提醒訊息。

### 更改外觀主題

修改 `config.py` 中的 `COLORS` 字典來自訂介面顏色。

### 添加新功能

參考 `utils.py` 中的類別結構來添加新的功能模組。

## 📊 API 參考

### WorkLogger 類別

```python
from utils import WorkLogger

logger = WorkLogger("my_log.json")
logger.start_work_session()
logger.end_work_session()
stats = logger.get_daily_stats("2024-01-01")
```

### ConfigManager 類別

```python
from utils import ConfigManager

config_mgr = ConfigManager("my_settings.ini")
work_time = config_mgr.get_int_setting('TIMING', 'work_duration')
config_mgr.set_setting('TIMING', 'work_duration', '7200')
```

## 🤝 貢獻指南

1. Fork 本專案
2. 建立功能分支 (`git checkout -b feature/新功能`)
3. 提交變更 (`git commit -am '添加新功能'`)
4. 推送到分支 (`git push origin feature/新功能`)
5. 建立 Pull Request

## 📝 版本歷史

- **v2.0**: 增強版本，新增工作記錄、統計分析、設定管理功能
- **v1.0**: 基本版本，提供人體檢測和休息提醒功能

## 📄 授權條款

本專案採用 MIT 授權條款。詳見 LICENSE 檔案。

## 🆘 技術支援

如有問題或建議，請透過以下方式聯繫：

- 建立 Issue 在 GitHub 儲存庫
- 查看 `開發說明.md` 獲取詳細技術文檔

## 🏥 健康提醒

使用電腦時請注意：

- 👁️ 每 20 分鐘看向 20 公尺外的物體 20 秒 (20-20-20 法則)
- 🚶 每小時起身活動至少 5-10 分鐘
- 💧 適時補充水分
- 🪑 保持正確坐姿
- 😴 確保充足睡眠

祝您工作愉快，身體健康！ 💪✨
