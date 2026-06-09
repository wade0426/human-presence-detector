# M9 應用組裝

**涉及檔案**：`src/main.py`

**相依**：M1–M8 全部完成後進行

---

## 任務清單

### FrameGrabber 建立與接線（需求 8）

- [ ] 建立 `source = create_source(cfg.source)`（或既有工廠）
- [ ] 建立 `grabber = FrameGrabber(source)`
- [ ] 呼叫 `grabber.start()` 於 worker 啟動前

### DetectionWorker 建構更新

- [ ] 改傳 `frames=grabber` 取代原 `source=source`
- [ ] 移除 `reset_mode`、`snooze_sec` 等已刪除參數
- [ ] 傳入 `RestCountMode(cfg.timer.rest_count_mode)` 給 `TimerEngine`

### 預覽渲染 QTimer（需求 8）

- [ ] 建立 `preview_timer = QTimer()`；設 interval 33ms（~30fps）
- [ ] 連接 `preview_timer.timeout → lambda: window.on_frame_ready(grabber.latest())`
- [ ] 啟動 `preview_timer`

### 訊號接線更新

- [ ] `worker.presence_changed → window.on_presence_changed`（需求 1）
- [ ] `worker.reminder_show → popup.show`（需求 4，取代舊接線）
- [ ] `worker.return_prompt → return_prompt_dialog.show_prompt`（需求 3，新增）
- [ ] `popup.start_rest → worker.start_rest`（需求 4，取代 dismissed）
- [ ] `return_prompt_dialog.confirmed → worker.confirm_return`（需求 3，新增）
- [ ] `actions.request_quit → self._confirm_quit`（需求 2，新增）
- [ ] 移除對已刪除訊號（`frame_ready`、`reminder_repeat`、`dismissed`）的舊接線

### 離開確認（需求 2）

- [ ] 實作 `_confirm_quit(self)`：以 `QMessageBox.question` 彈出二次確認
  - 確認 → `QApplication.instance().quit()`
  - 取消 → 不做任何事

### 暫停/繼續同步 preview_timer（需求 5）

- [ ] `pause_toggled(True)` → `worker.pause()`；`preview_timer.stop()`（畫面定格）
- [ ] `pause_toggled(False)` → `worker.resume()`；`preview_timer.start()`

### 退出清理（需求 8 執行緒安全）

- [ ] `app.aboutToQuit` 回呼中：先 `grabber.stop()`，再呼叫既有 `_shutdown_worker_thread()`
- [ ] 確認 `preview_timer.stop()` 也在退出時執行

---

## 驗收（手動整合測試）

- [ ] 啟動 → 預覽即時顯示（延遲 < 1s）、偵測正常
- [ ] 有人進入 ROI → PresenceBadge 顯示「有人」
- [ ] 工作達門檻 → 出現單一「開始休息」彈窗
- [ ] 點「開始休息」→ 狀態文字切換為「休息中」
- [ ] 休息完成回座 → 出現「歡迎回來」確認窗；確認前計時不前進
- [ ] 暫停 N 秒後繼續 → 工作時間未跳增
- [ ] 點「離開」→ 二次確認對話框；確認後程式完全結束
- [ ] 程式退出時無殘留 FrameGrabber 執行緒（console 無報錯）
