# Vibe Coding 起始 Prompt：人體辨識休息提醒系統 — 時間顯示與提醒異常修正

## 你的角色

你是**主 Agent（Orchestrator）**，負責管理並追蹤整個修正工程的端到端進度。
你不直接撰寫實作程式碼；你的職責是：

1. 閱讀並理解所有輸入文件
2. 依照規定順序派發子 Agent，讓它們完成各模塊的實作與測試
3. 驗收每個子 Agent 的成果（pytest + mypy + ruff 三項全部通過）
4. 在 `docs/tasks/progress.md` 即時更新進度 checklist
5. 全程無人工參與，你必須自主完成所有決策

---

## 輸入文件（閱讀順序）

1. **需求文件**：`docs/proposal.md`
   - 定義 6 項功能需求（FR-1 ～ FR-6）與驗收標準
2. **詳細設計**：`docs/detailed-design.md`
   - 每個模塊的介面、資料結構、互動、測試點
3. **任務清單**（每個模塊對應一份）：`docs/tasks/`
   - `types.md`、`duration-format.md`、`today-work-model.md`、`stream-health.md`
   - `timer-engine.md`、`config-settings.md`、`logging-store.md`
   - `connection-state.md`、`reminder-dispatch.md`、`status-strip.md`
   - `today-summary-view.md`、`main-window.md`、`main-entrypoint.md`
4. **總體進度**：`docs/tasks/progress.md`（你負責維護）

開始前請完整閱讀以上所有文件。

---

## 環境約束

- **作業系統**：Windows（PowerShell）
- **Python 環境**：conda env `project`，Python 3.11
- **框架**：PySide6 + OpenCV + YOLOv8 + SQLite
- **測試**：pytest，設定於 `pyproject.toml`（`testpaths = ["tests"]`）
- **Lint**：ruff（`select = ["E", "F", "W", "I", "UP", "B", "SIM"]`，`line-length = 100`）
- **型別檢查**：mypy（`strict = true`，`ignore_missing_imports = true`）
- **Qt 測試環境**：`conftest.py` 已設 `QT_QPA_PLATFORM=offscreen`
- **指令慣例**：優先使用 `rtk` 包裝的指令（如 `rtk pytest`、`rtk mypy src`、`rtk ruff check .`）

---

## 模塊實作順序與子 Agent 派發規則

### 批次順序（嚴格依序，後批依賴前批的介面）

```
批次 1（純邏輯基礎，可平行）
  A. types           → docs/tasks/types.md
  B. duration-format → docs/tasks/duration-format.md

批次 2（依賴批次 1，可平行）
  C. today-work-model → docs/tasks/today-work-model.md
  D. stream-health    → docs/tasks/stream-health.md
  E. timer-engine     → docs/tasks/timer-engine.md
  F. config-settings  → docs/tasks/config-settings.md

批次 3（依賴批次 1、2，可平行）
  G. logging-store    → docs/tasks/logging-store.md
  H. connection-state → docs/tasks/connection-state.md
  I. reminder-dispatch → docs/tasks/reminder-dispatch.md

批次 4（UI 層，依賴批次 1-3，可平行）
  J. status-strip        → docs/tasks/status-strip.md
  K. today-summary-view  → docs/tasks/today-summary-view.md

批次 5（整合層，必須等批次 1-4 全數通過後才開始）
  L. main-window     → docs/tasks/main-window.md
  M. main-entrypoint → docs/tasks/main-entrypoint.md
```

### 子 Agent 派發規則

- **每個模塊文件對應一個子 Agent**。同一批次內的模塊可同時派發多個子 Agent 平行執行。
- 每個子 Agent 接收的 Prompt 必須包含：
  1. 對應任務文件（`docs/tasks/<module>.md`）的**完整內容**
  2. 詳細設計的對應節段（`docs/detailed-design.md` §4.x）
  3. 驗收指令（見下方「子 Agent 驗收指令」）
  4. 明確的**完成回報格式**（見下方「子 Agent 完成回報」）
- 子 Agent **只負責修改或新增其模塊涉及的檔案**，不得修改範圍外的檔案。
- 子 Agent 完成後向你（主 Agent）回報結果，再由你決定下一步。

---

## 子 Agent 指令模板

派發每個子 Agent 時，使用以下模板（填入 `{MODULE}` 與 `{TASK_CONTENT}`）：

```
你是一個實作 Agent，負責完成「{MODULE}」模塊的修改與測試。
全程無人工參與，你必須自主完成並通過所有驗收。

## 你的任務

{TASK_CONTENT}
（貼上 docs/tasks/{module}.md 的完整內容）

## 設計參考

請閱讀 docs/detailed-design.md 中對應的 §4.x 節段，作為實作依據。
若需要理解上下文，也可閱讀 docs/proposal.md 對應的 FR-x 需求說明。

## 驗收指令（必須全部通過，不得跳過）

在 Windows PowerShell + conda env `project` 環境下執行：

1. rtk pytest                    # 全套測試（含你新增的測試）
2. rtk mypy src                  # 型別檢查（strict mode）
3. rtk ruff check .              # Lint 檢查

若任一指令失敗，修復後重新執行，確認三項全部顯示 0 errors / passed。

## 完成回報格式

完成後回報：
- 狀態：DONE / FAILED（超過 3 次重試仍無法通過）
- 修改的檔案列表（含新增）
- pytest 通過數 / 總數
- mypy 結果（errors 數量）
- ruff 結果（violations 數量）
- 若 FAILED：失敗原因摘要與最後一次錯誤訊息
```

---

## 驗收與進度追蹤

### 每個子 Agent 完成後，你必須：

1. **確認三項全部通過**：
   - `pytest`：0 failed（通過數 ≥ 開始前 + 新增測試數）
   - `mypy src`：`Found 0 errors`
   - `ruff check .`：`All checks passed`
   - 若任一未通過，視為 **FAILED**

2. **更新 `docs/tasks/progress.md`**：
   - 通過 → 將該模塊狀態改為 `✅ 已完成`
   - FAILED（重試 > 3 次）→ 改為 `⚠️ BLOCKED`，附失敗原因摘要

3. **確認後才啟動下一批次**：
   - 同批次內某模塊 BLOCKED 時，記錄後繼續啟動同批次其他模塊
   - 批次 5 的整合層，**必須等批次 1-4 所有模塊 DONE（無 BLOCKED）才能啟動**

### 全部完成後的最終驗收

當所有模塊標記為 DONE 後，執行一次完整驗收：

```powershell
rtk pytest          # 全套測試
rtk mypy src        # 全套型別檢查
rtk ruff check .    # 全套 Lint
```

三項全部通過後，在 `docs/tasks/progress.md` 末尾加上：

```markdown
## 最終驗收結果

- pytest：X passed, 0 failed
- mypy：Found 0 errors
- ruff：All checks passed
- 完成時間：YYYY-MM-DD HH:MM
```

---

## 關鍵設計約束（派發子 Agent 前必須確認已傳達）

以下約束適用於所有模塊，子 Agent 必須遵守：

1. **純邏輯模塊不得引入 Qt 或 OpenCV**
   - `duration_format`、`today_work_model`、`stream_health`、`timer_engine`（核心邏輯）、`logging_store` 皆為純 Python，不依賴框架

2. **時間相關測試一律注入時鐘**
   - 使用 `clock` 參數注入假時鐘（`lambda: t`），不依賴真實等待
   - `TimerEngine`、`StreamHealthMonitor` 的所有計時測試皆遵守此原則

3. **向後相容**
   - 所有新增欄位（`TimerSnapshot.overtime_sec`、`ReminderContext.work_elapsed_sec`）必須有預設值
   - `config.yaml` 缺欄位 `reminding_display_mode` 時系統仍可正常啟動（預設 `"overtime"`）
   - 既有測試不得因本次修改而失敗（除非是修正既有測試的錯誤）

4. **mypy strict 模式**
   - 所有新增函式必須有完整型別標註
   - 使用 `from __future__ import annotations`（與既有程式碼風格一致）

5. **ruff line-length = 100**
   - 所有新增程式碼行長不超過 100 字元

6. **SQLite 跨執行緒安全**
   - `logging_store.close()` 只能關閉呼叫端執行緒自己的連線，絕不跨執行緒操作

7. **WORK_ENDED 事件只送一次**
   - 一輪「工作→提醒→休息→返回」流程中，`WORK_ENDED` 恰好送出一次（於 `REMINDING → RESTING` 時送出，`confirm_return()` 不重複送）

---

## 開始執行

請依以下步驟開始：

1. 閱讀所有輸入文件（`docs/proposal.md`、`docs/detailed-design.md`、`docs/tasks/*.md`）
2. 確認 `docs/tasks/progress.md` 中所有模塊狀態均為 `⬜ 未開始`
3. 執行現有測試基線，記錄當前通過數：`rtk pytest`
4. 依批次順序，從**批次 1**開始，同時派發 `types` 與 `duration-format` 兩個子 Agent
5. 收到回報後驗收、更新 progress.md，再啟動批次 2，依此類推
6. 最終完成全套驗收並更新 progress.md
