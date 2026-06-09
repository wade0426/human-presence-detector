# 主視窗 / 設定 / 系統匣 `ui/`

> **對應檔案**：`src/ui/{main_window,settings,tray}.py`、`tests/test_ui.py`  
> **前置條件**：[[types]]、[[config]]  
> **相依**：`PySide6.QtWidgets`、`PySide6.QtGui`、`PySide6.QtCore`

## 任務

### MainWindow

- [ ] **UI1** 建立 `src/ui/main_window.py`，定義 `MainWindow(QMainWindow)` 骨架：
  ```python
  class MainWindow(QMainWindow):
      roi_changed = Signal(object)    # BBox（正規化）
      def __init__(self, config: AppConfig): ...
      def on_frame_ready(self, frame: Frame): ...
      def on_presence_changed(self, present: bool): ...
      def on_timer_updated(self, snapshot: TimerSnapshot): ...
      def on_connection_status(self, status: str): ...
  ```
  - 中央 widget 為 `QLabel`（`preview_label`）
  - 右側或底部加入 `QLabel` 顯示：狀態（工作中/離開/提醒中）、工作計時

- [ ] **UI2** 實作 `on_frame_ready`，在 `QLabel` 上顯示影像（BGR → RGB → `QImage` → `QPixmap`），**疊加**：
  - 偵測框（綠色矩形）— 先以空 list 初始化，等 `presence_changed` 更新
  - ROI 框線（藍色矩形，從 `config.presence.roi` 初始化）
  - 目前狀態與工作計時文字（白色，左上角）

- [ ] **UI3** 實作 ROI 拖拉框選：
  - override `mousePressEvent`：記錄起始點
  - override `mouseReleaseEvent`：記錄終止點，計算正規化 `BBox`（除以 label 的顯示解析度），emit `roi_changed`
  - 拖拉中以半透明矩形即時顯示（override `mouseMoveEvent`，觸發 `update()`）

- [ ] **UI4** 實作 `on_timer_updated`：依 `TimerSnapshot.state` 更新狀態 label 文字（繁體中文：待機 / 工作中 / 短暫離開 / 提醒中）與工作計時顯示（`MM:SS`）

- [ ] **UI5** 實作最小化至系統匣：`closeEvent` 改為 `hide()` 而非真正關閉（若有系統匣時）

### SettingsDialog

- [ ] **UI6** 建立 `src/ui/settings.py`，實作 `SettingsDialog(QDialog)`：
  ```python
  class SettingsDialog(QDialog):
      config_changed = Signal(object)    # AppConfig
      def __init__(self, config: AppConfig, parent=None): ...
  ```
  - 表單包含：來源選擇（RTSP/webcam）、RTSP URL、Webcam index、N/M/R（分鐘）、信心門檻、大小門檻、去抖動次數、提醒方式、重置模式、媒體路徑
  - 「儲存」按鈕：呼叫 `save_config`，emit `config_changed`
  - 「取消」按鈕：`reject()`
  - 輸入驗證失敗時顯示錯誤訊息（`QMessageBox`），不關閉對話框

### TrayIcon

- [ ] **UI7** 建立 `src/ui/tray.py`，實作 `TrayIcon(QSystemTrayIcon)`：
  - context menu：「開啟主視窗」、「暫停/繼續偵測」、「設定」、分隔線、「結束」
  - `update_status(state: TimerState)`：依狀態更新 tooltip 文字（工作中/離開/提醒中）
  - double-click 開啟主視窗

### 測試

- [ ] **UI8** 建立 `tests/test_ui.py`（pytest-qt）：
  - `MainWindow(config)` 可建立不崩潰
  - ROI 拖拉換算：模擬 press(10,20) → release(110,120) 在 500×400 的 label 上 → `roi_changed` 收到 `BBox(0.02, 0.05, 0.2, 0.25)` 誤差 < 0.01
  - `SettingsDialog(config)` 可建立不崩潰
  - `TrayIcon` 可建立不崩潰

- [ ] **UI9** 執行 `rtk pytest tests/test_ui.py -v` 確認全部通過

- [ ] **UI10** `git commit -m "feat: add main window, settings dialog, tray icon"`
