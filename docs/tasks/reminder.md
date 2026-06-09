# 提醒元件 `reminder/`

> **對應檔案**：`src/reminder/{base,popup,toast,floating,factory}.py`、`tests/test_reminder.py`  
> **前置條件**：[[types]]、[[config]]、[[environment]]（需要 `data/assets/rest_placeholder.png`）  
> **相依**：`PySide6.QtWidgets`、`PySide6.QtCore`、`PySide6.QtMultimedia`（影片用）

## 任務

- [ ] **R1** 建立 `src/reminder/base.py`，定義 `Reminder` Protocol：
  ```python
  class Reminder(Protocol):
      dismissed: Signal       # 使用者點掉時發出
      def show(self, ctx: ReminderContext) -> None: ...
      def hide(self) -> None: ...
  ```
  以及 `ReminderContext` 已定義於 `src/types.py`（確認 import 正確即可）

- [ ] **R2** 建立 `src/reminder/popup.py`，實作 `PopupReminder(QDialog)`：
  - `show(ctx)`：依 `ctx.media_type` 決定顯示方式：
    - `'image'`：`QLabel` + `QPixmap` 顯示圖片
    - `'video'`：`QMediaPlayer` + `QVideoWidget` 播放影片
  - 若 `ctx.sound_path` 非空：用 `QSoundEffect` 播放提示音
  - 顯示「我要休息」按鈕，點擊後 emit `dismissed`，關閉視窗
  - `hide()`：關閉視窗

- [ ] **R3** 建立 `src/reminder/toast.py`，實作 `ToastReminder`：
  - `show(ctx)`：呼叫 `QSystemTrayIcon.showMessage`，顯示工作分鐘數
  - emit `dismissed` 立即（toast 不需使用者互動）
  - `hide()`：無操作

- [ ] **R4** 建立 `src/reminder/floating.py`，實作 `FloatingReminder(QWidget)`：
  - `__init__`：設定 `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`
  - `show(ctx)`：以 `QLabel` 顯示倒數文字；啟動 `QTimer` 每秒更新
  - 倒數到零時：閃爍或變色提醒（背景色切換紅色）
  - `hide()`：停止計時器，隱藏視窗

- [ ] **R5** 建立 `src/reminder/factory.py`，實作 `create_reminder(cfg: ReminderConfig, tray=None) -> Reminder`：
  - `cfg.method == 'popup'` → `PopupReminder()`
  - `cfg.method == 'toast'` → `ToastReminder(tray)`
  - `cfg.method == 'floating'` → `FloatingReminder(cfg.floating)`

- [ ] **R6** 建立 `tests/test_reminder.py`（pytest-qt）：
  - `create_reminder(cfg_popup)` 回傳 `PopupReminder` 實例
  - `create_reminder(cfg_toast)` 回傳 `ToastReminder` 實例
  - `create_reminder(cfg_floating)` 回傳 `FloatingReminder` 實例
  - `PopupReminder.show(ctx)` 在 `media_type='image'` 下可建立不崩潰
  - `PopupReminder` 點擊「我要休息」按鈕發出 `dismissed` signal

- [ ] **R7** 執行 `rtk pytest tests/test_reminder.py -v` 確認全部通過

- [ ] **R8** `git commit -m "feat: add reminder components (popup/toast/floating)"`
