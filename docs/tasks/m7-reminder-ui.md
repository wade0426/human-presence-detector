# M7 提醒/休息流程 UI

**涉及檔案**：
- 修改：`src/reminder/popup.py`
- 新增：`src/reminder/return_prompt.py`
- 修改：`src/ui/strings.py`

**相依**：M1（ReminderContext 無 reset_mode/snooze）

---

## 任務清單

### strings.py — 歡迎回來文字

- [ ] 新增 `RETURN_TITLE = "歡迎回來"`
- [ ] 新增 `RETURN_BODY = "休息結束，要開始新一輪工作嗎？"`
- [ ] 新增 `RETURN_CONFIRM = "開始新一輪"`
- [ ] 確認 `REMIND_START_REST = "開始休息"` 已存在（若無則新增）
- [ ] 移除（或標記棄用）`REMIND_ACK`、`REMIND_CLOSE`、`REMIND_SNOOZE` 的使用

### popup.py 簡化（需求 4）

- [ ] 移除 `_setup_buttons()` 中的 `reset_mode` / `snooze` 分支
- [ ] 僅保留單一動作鈕，文字為 `REMIND_START_REST`（「開始休息」）
- [ ] 將訊號從 `dismissed` 改名為 `start_rest = Signal()`
- [ ] 點按鈕 → emit `start_rest` → 呼叫 `self.hide()`
- [ ] 以 X 關閉視窗（`closeEvent`）→ 僅 hide，**不** emit start_rest（視為暫不處理，等 repeat_interval 後再次提醒）
- [ ] 確認媒體（圖片/影片/音效）顯示邏輯不受影響

### return_prompt.py 新增（需求 3）

- [ ] 定義 `class ReturnPromptDialog(QDialog)`
- [ ] 新增 `confirmed = Signal()`
- [ ] `show_prompt(self, rest_minutes: int | None = None)`：設定標題/訊息並 `self.show()`
  - 標題：`RETURN_TITLE`
  - 訊息：`RETURN_BODY`（可加入 `rest_minutes` 資訊）
  - 單一按鈕：`RETURN_CONFIRM`
- [ ] 點按鈕 → emit `confirmed` → `self.accept()`
- [ ] `closeEvent(self, e)`：`e.ignore()`（未確認前不可關閉，持續顯示）

---

## 單元測試（`tests/test_reminder.py`）

- [ ] 測試 1：`PopupReminder` 僅有一顆動作鈕、文字為「開始休息」
- [ ] 測試 2：點「開始休息」→ 發出 `start_rest`、視窗 `isVisible() == False`
- [ ] 測試 3：`ReturnPromptDialog` 點「開始新一輪」→ 發出 `confirmed`
- [ ] 測試 4：`ReturnPromptDialog.close()` → 視窗仍 `isVisible() == True`（closeEvent 被忽略）
- [ ] 測試 5：以無 `reset_mode`/`snooze_minutes` 的 `ReminderContext` 呼叫 `popup.show()` 不拋例外

---

## 驗收

- [ ] `rtk pytest tests/test_reminder.py -v` 全通過
- [ ] （手動）提醒彈窗僅顯示一顆「開始休息」鈕
- [ ] （手動）關閉彈窗後於 repeat_interval 後再次提醒
- [ ] （手動）「歡迎回來」窗無法以 X 關閉、點確認後才開始計時
