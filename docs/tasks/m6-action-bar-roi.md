# M6 動作列與 ROI 編輯

**涉及檔案**：
- 修改：`src/ui/widgets/action_bar.py`
- 修改：`src/ui/widgets/preview_view.py`
- 修改：`src/ui/theme.py`
- 修改：`src/ui/strings.py`

**相依**：M1（strings 新增已於 M1/M5 完成）

---

## 任務清單

### strings.py（補齊 M6 所需文字）

- [ ] 新增 `ACTION_QUIT = "離開"`
- [ ] 新增 `ACTION_EDIT_ROI_ACTIVE = "完成編輯"`
- [ ] 新增 `ROI_HINT = "拖曳以選取偵測區域"`
- [ ] 新增 `QUIT_CONFIRM_TITLE = "離開"`
- [ ] 新增 `QUIT_CONFIRM_BODY = "確定要關閉系統嗎？"`

### theme.py 新增樣式

- [ ] 在 `build_qss()` 加入 `QPushButton:checked { background: <accent 深色>; border: 2px solid <accent>; }` 規則
- [ ] 加入 `QPushButton[role="danger"] { background: <danger 紅色>; color: white; }` 規則

### action_bar.py — 離開按鈕（需求 2）

- [ ] 新增 `request_quit = Signal()`
- [ ] 在 ActionBar 右側（stretch 後、設定鈕前）新增「離開」按鈕
- [ ] 離開按鈕設 `setProperty("role", "danger")` 以套用 danger 樣式
- [ ] 點擊離開鈕 → emit `request_quit`

### action_bar.py — ROI 編輯視覺回饋（需求 6）

- [ ] 新增 `set_edit_active(self, on: bool)` 方法：
  - `on=True` → 按鈕文字改為 `ACTION_EDIT_ROI_ACTIVE`
  - `on=False` → 按鈕文字還原為原文字（`ACTION_EDIT_ROI` 或既有）
- [ ] ROI 鈕確認為 `setCheckable(True)`；toggled(True/False) 呼叫 `set_edit_active`

### preview_view.py — ROI 提示文字（需求 6）

- [ ] 確認 `set_edit_mode(on: bool)` 存在（新增若不存在）
- [ ] `on=True` → 顯示覆蓋提示文字標籤（`ROI_HINT`）
- [ ] `on=False` → 隱藏提示文字標籤

---

## 單元測試（`tests/test_ui.py` 或 `tests/test_theme.py`）

- [ ] 測試 1：`ActionBar` ROI 鈕 `toggled(True)` → 文字 == `"完成編輯"`、`isChecked() == True`
- [ ] 測試 2：ROI 鈕 `toggled(False)` → 文字還原為原始文字
- [ ] 測試 3：`PreviewView.set_edit_mode(True)` → 提示文字標籤 `isVisible() == True`；`set_edit_mode(False)` → 隱藏
- [ ] 測試 4：點離開鈕 → `request_quit` 訊號被發出
- [ ] 測試 5：`build_qss()` 輸出字串含 `"QPushButton:checked"` 與 `'[role="danger"]'`

---

## 驗收

- [ ] `rtk pytest tests/test_ui.py tests/test_theme.py -v` 相關測試通過
- [ ] （手動）點「編輯 ROI」後按鈕樣式與文字明顯改變；退出後還原
- [ ] （手動）離開鈕呈紅色；點擊後出現確認對話框（確認行為由 M9 完成）
