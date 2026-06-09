# M5 主視窗與狀態顯示

**涉及檔案**：
- 新增：`src/ui/widgets/presence_badge.py`
- 修改：`src/ui/main_window.py`
- 修改：`src/ui/widgets/status_strip.py`
- 修改：`src/ui/strings.py`（STATE_TEXT / PRESENCE_YES / PRESENCE_NO 已於 M1 新增）

**相依**：M1（STATE_TEXT 新狀態）、M4（presence_changed 訊號）

---

## 任務清單

### 新增 PresenceBadge 元件（`src/ui/widgets/presence_badge.py`）

參考 `connection_badge.py` 的實作風格。

- [ ] 定義 `class PresenceBadge(QWidget)`
- [ ] 實作 `set_present(self, present: bool)`：
  - `present=True` → 綠色圓點 + 文字 `PRESENCE_YES`（`strings.py`）
  - `present=False` → 灰色圓點 + 文字 `PRESENCE_NO`
- [ ] 預設初始狀態為「無人」

### 更新 main_window.py

- [ ] 在頂部徽章區新增 `PresenceBadge` 實例（置於 `ConnectionBadge` 旁）
- [ ] 改寫 `on_presence_changed(self, present: bool)`：移除 `del present`，改為呼叫 `self._presence_badge.set_present(present)`
- [ ] 更新 `on_connection_status(self, status: str)`：當 `status` 為 `"no_signal"` 或 `"reconnecting"` 時，呼叫 `self._presence_badge.set_present(False)`

### 更新 status_strip.py

- [ ] 更新狀態文字顯示：使用 `STATE_TEXT[snapshot.state]`（已含新狀態）
- [ ] `RESTING` 狀態下顯示休息倒數/已休息：
  - FIXED 模式：顯示 `rest_remaining_sec` 倒數
  - PRESENCE 模式：顯示 `rest_elapsed_sec` 已休息
  - （依 `snapshot.rest_remaining_sec > 0` 判斷模式，或由 M2 snapshot 統一傳入）
- [ ] 確保 `SUSPENDED` 顯示「已暫停」（`STATE_TEXT` key 查表即可）

---

## 單元測試（`tests/test_ui.py`）

- [ ] 測試 1：`PresenceBadge.set_present(True)` → 標籤文字為「有人」
- [ ] 測試 2：`PresenceBadge.set_present(False)` → 標籤文字為「無人」
- [ ] 測試 3：`StatusStrip.update_snapshot(snap)` 其中 `snap.state == RESTING` → 顯示「休息中」
- [ ] 測試 4：`snap.state == SUSPENDED` → 顯示「已暫停」
- [ ] 測試 5：`on_connection_status("no_signal")` → PresenceBadge 顯示「無人」

---

## 驗收

- [ ] `rtk pytest tests/test_ui.py -v` 相關測試通過
- [ ] （手動）人進入/離開 ROI 後，徽章在去抖動延遲內正確切換
- [ ] （手動）休息倒數期間狀態文字顯示「休息中」而非「提醒中」
