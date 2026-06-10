# M2c：清除對話框與流程

> 對應需求：`docs/proposal.md` 需求二（FR-2.1～FR-2.6，§2.4）
> 對應設計：`docs/detailed-design.md` §4.3
> 依賴模塊：[[m2b-clear-data-service]]（`ClearDataService`/`ClearScope`/`ClearResult`）
> 異動檔案：
> - 修改 `src/ui/strings.py`（新增字串）
> - 新增 `src/ui/clear_data_dialog.py`
> - 新增 `tests/test_clear_data_dialog.py`

> 註：主視窗與設定頁的「清除資料」按鈕＋訊號接線屬於 [[m4-tooltips]]（設定頁）與 [[int-integration]]（主視窗＋`main.py` 接線），本模塊只負責對話框元件與流程函式本身。

---

## 任務清單

- [ ] **任務 1：於 `src/ui/strings.py` 新增清除資料相關字串**

  ```python
  # Clear data (M2c)
  CLEAR_DATA_BUTTON = "清除資料"
  CLEAR_DATA_TITLE = "清除資料"
  CLEAR_SCOPE_TODAY = "清除今日紀錄"
  CLEAR_SCOPE_ALL = "清除全部紀錄"
  CLEAR_SCOPE_RESET = "清除全部紀錄並重設設定"
  CLEAR_RESET_WARNING = "此選項將清空所有紀錄，並將設定回復為預設值，此操作無法復原。"
  CLEAR_CONFIRM_BODY = "此操作無法復原，確定要繼續嗎？"
  CLEAR_DONE = "已清除 {count} 筆紀錄。"
  ```

  > `CLEAR_RESET_WARNING` 文案為建議值，需符合 FR-2.3「明顯警語」要求；其餘 7 個字串取自 `docs/proposal.md` §2.4。
  > 完成後執行 [[m5-text-fixes]] 的掃描測試（`test_no_stray_angle_quote_in_strings`）確認新字串未引入 `》`。

- [ ] **任務 2：建立 `ClearDataDialog`**

  新增 `src/ui/clear_data_dialog.py`：

  ```python
  class ClearDataDialog(QDialog):
      def __init__(self, parent: QWidget | None = None) -> None: ...
      def selected_scope(self) -> ClearScope: ...   # 預設 ClearScope.TODAY
  ```

  UI 規格：
  - 三個互斥 `QRadioButton`（建議用 `QButtonGroup` 管理）：`CLEAR_SCOPE_TODAY` / `CLEAR_SCOPE_ALL` / `CLEAR_SCOPE_RESET`；**預設選取「今日」**。
  - 一個警語 `QLabel`（`CLEAR_RESET_WARNING`），預設隱藏；當「全部＋重設」被選取時顯示（`setProperty("role", "danger")`，比照 `src/ui/widgets/action_bar.py` 中 `_quit_btn` 的 `"danger"` role 樣式）。
  - `QDialogButtonBox`（確定／取消），`exec()` 回傳 `Accepted`/`Rejected`。
  - `selected_scope()`：依目前選取的 radio button 回傳對應 `ClearScope`。

- [ ] **任務 3：建立 `run_clear_data_flow()`**

  ```python
  def run_clear_data_flow(
      parent: QWidget,
      service: ClearDataService,
      on_done: Callable[[ClearResult], None],
  ) -> None:
      dialog = ClearDataDialog(parent)
      if dialog.exec() != QDialog.DialogCode.Accepted:
          return

      scope = dialog.selected_scope()

      # 二次確認（FR-2.3）
      confirm = QMessageBox.question(
          parent,
          strings.CLEAR_DATA_TITLE,
          strings.CLEAR_CONFIRM_BODY,
          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
          QMessageBox.StandardButton.No,
      )
      if confirm != QMessageBox.StandardButton.Yes:
          return

      result = service.clear(scope)
      QMessageBox.information(
          parent, strings.CLEAR_DATA_TITLE, strings.CLEAR_DONE.format(count=result.deleted)
      )
      if result.reset_config:
          QMessageBox.information(parent, strings.SETTINGS_TITLE, strings.SETTINGS_SAVED_RESTART)

      on_done(result)
  ```

  - 流程順序：開對話框選範圍 → 二次確認 → 執行 `service.clear(scope)` → 顯示完成訊息 → 若 `reset_config` 則額外提示需重啟（FR-2.6，沿用 `SETTINGS_SAVED_RESTART`）→ 呼叫 `on_done(result)` 觸發刷新。

- [ ] **任務 4：撰寫測試（`tests/test_clear_data_dialog.py`，qt）**

  - `test_dialog_default_scope_is_today`：開啟 `ClearDataDialog`，斷言 `dialog.selected_scope() == ClearScope.TODAY`。
  - `test_dialog_select_all_and_reset`：以 `qtbot` 勾選「全部＋重設」radio → `dialog.selected_scope() == ClearScope.ALL_AND_RESET`，且警語 label 變為可見（`isVisible()`）。
  - `test_flow_executes_service_on_confirm`：
    - `monkeypatch.setattr(ClearDataDialog, "exec", lambda self: QDialog.DialogCode.Accepted)`
    - `monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)`
    - `monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)`
    - 用 fake/spy `ClearDataService`（記錄 `clear(scope)` 呼叫引數，回傳固定 `ClearResult`）
    - 斷言 `service.clear` 以 dialog 預設（或設定的）scope 被呼叫一次，且 `on_done` 被呼叫並收到該 `ClearResult`。
  - `test_flow_aborts_on_cancel`：`monkeypatch.setattr(ClearDataDialog, "exec", lambda self: QDialog.DialogCode.Rejected)` → `service.clear` 不被呼叫、`on_done` 不被呼叫。

  > 對話框測試使用 fake/spied `ClearDataService`（記錄 `clear` 引數），不接真實 db（真實 db 行為已由 [[m2b-clear-data-service]] 的測試覆蓋）。

---

## 完成定義（Definition of Done）

- [ ] `src/ui/strings.py` 新增 8 個 `CLEAR_*` 字串
- [ ] `ClearDataDialog`、`run_clear_data_flow` 介面與簽章與設計文件一致
- [ ] 4 個測試新增並通過
- [ ] `rtk pytest tests/test_clear_data_dialog.py` 全數通過
- [ ] `rtk pytest tests/test_strings.py` 仍通過（含 [[m5-text-fixes]] 的掃描測試）
- [ ] `rtk ruff check src/ui/clear_data_dialog.py` 無錯誤
