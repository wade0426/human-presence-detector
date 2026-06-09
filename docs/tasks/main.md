# 進入點組裝 `main.py`

> **對應檔案**：`src/main.py`  
> **前置條件**：所有模塊（[[types]]、[[config]]、[[video-source]]、[[detector]]、[[presence]]、[[timer-engine]]、[[logging-store]]、[[worker]]、[[reminder]]、[[ui]]）全部完成  
> **相依**：`PySide6.QtWidgets`、所有 src 模塊

## 任務

- [ ] **M1** 建立 `src/main.py`，實作 `main()` 函數，照 `docs/detailed-design.md` §5.10 組裝所有模塊：
  - `QApplication`
  - `load_config("config.yaml")`
  - 建立 `create_source`、`PersonDetector`、`PresenceEvaluator`、`TimerEngine`、`SessionStore`
  - 建立 `ReminderContext`
  - 建立 `DetectionWorker`，`moveToThread(QThread)`
  - 建立 `MainWindow`、`TrayIcon`、`create_reminder`

- [ ] **M2** 完成所有 signal → slot 接線：
  - `worker.frame_ready → window.on_frame_ready`
  - `worker.presence_changed → window.on_presence_changed`
  - `worker.timer_updated → window.on_timer_updated`
  - `worker.connection_status → window.on_connection_status`
  - `worker.reminder_show → reminder.show`
  - `worker.reminder_repeat → reminder.show`
  - `reminder.dismissed → worker.dismiss_reminder`
  - `window.roi_changed → worker.set_roi`
  - `tray` 的開啟/暫停/設定/結束選單 → 對應 slot
  - `settings.config_changed → worker` 重新套用設定（重建 source / detector 或更新參數）

- [ ] **M3** 加入 `if __name__ == '__main__': main()` 入口

- [ ] **M4** 手動驗收（照 `docs/proposal.md` §11 的 MVP 驗收標準逐項確認）：
  - [ ] 從 RTSP 或 webcam 取得影像，主視窗即時預覽
  - [ ] 在預覽上框選 ROI；坐在座位區且夠近時工作計時開始累積
  - [ ] 短暫離開（≤ M）計時暫停；離開達 M 計時歸零
  - [ ] 工作達 N 分鐘彈出提醒視窗（預設假圖）
  - [ ] 提醒後模式1：需離開達 R 分鐘才重置開始新一輪
  - [ ] 每段工作/休息寫入 `data/records.sqlite`（用 DB Browser 或 sqlite3 CLI 確認）
  - [ ] 設定對話框可調整 N/M/R、提醒方式並保存至 `config.yaml`
  - [ ] 拔掉/斷開 RTSP 後程式不崩潰，能自動重連

- [ ] **M5** `git commit -m "feat: wire up main entry point"`
