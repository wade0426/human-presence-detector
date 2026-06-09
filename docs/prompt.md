# Vibe Coding Prompt — 人體辨識休息提醒系統 UI/UX 與渲染改善

## 你的角色

你是**主 Agent（Orchestrator）**，負責統籌本次改善工程的全部實作流程。
整個過程**不會有人工介入**。你需要依序為每個模塊（M1–M9）**派遣子 Agent** 完成實作，並追蹤整體進度直到所有模塊完成。

---

## 專案背景

本專案是一個 Python / PyQt6 人體辨識休息提醒系統，使用 RTSP/Webcam 偵測人是否在座位上並於連續工作達門檻時提醒休息。

本次改善涵蓋以下 8 項需求：

| 需求 | 說明 |
|---|---|
| 1 | 主視窗顯示人體在場狀態（有人 / 無人徽章） |
| 2 | ActionBar 新增「離開」按鈕（二次確認後結束程式） |
| 3 | 休息完成回座後彈出「歡迎回來」確認窗，確認後才開始新一輪計時 |
| 4 | 提醒彈窗改為單一「開始休息」按鈕，移除混淆的第二顆按鈕 |
| 5 | 修正暫停 bug：繼續後工作時間不得跳增 |
| 6 | ROI 編輯模式下按鈕樣式與文字明顯改變並顯示操作提示 |
| 7 | 狀態文字補齊「休息中」「已暫停」新狀態 |
| 8 | RTSP 預覽獨立高頻擷取執行緒，降低延遲與破圖 |

### 關鍵設計文件（必須閱讀）

- `docs/proposal.md` — 需求文檔：背景、根因分析、逐項驗收標準、涉及檔案
- `docs/detailed-design.md` — 詳細設計：完整型別簽章、狀態機轉移表、虛擬碼、測試案例清單
- `docs/tasks/` — 各模塊最小任務清單（M1–M9，每個模塊一個 .md）
- `docs/tasks/progress.md` — 整體進度追蹤（主 Agent 維護）

---

## 實作順序（嚴格序列，不可並行）

```
M1（Domain 型別）
  → M2（計時/狀態機）
    → M3（影像擷取）
      → M8（設定與結構）
        → M4（協調器）
          → M5（主視窗與狀態顯示）
            → M6（動作列與 ROI 編輯）
              → M7（提醒/休息流程 UI）
                → M9（應用組裝）
```

必須等前一個模塊的子 Agent **完整通過所有品質關卡後**，才開始下一個。

---

## 主 Agent 行為規範

### 每輪執行流程

1. **讀取 `docs/tasks/progress.md`**，找出序列中下一個 `- [ ]` 未完成的模塊。
2. **派遣子 Agent**（見「子 Agent 派遣規格」），傳入該模塊所需的完整上下文。
3. **等待子 Agent 回報結果**：
   - **成功** → 將 `docs/tasks/progress.md` 中該模塊的 `- [ ]` 改為 `- [x]`；繼續步驟 1。
   - **失敗** → 進入重試邏輯（見下方）。
4. **所有模塊完成**（progress.md 全勾選）→ 輸出最終 Summary 報告。

### 重試邏輯

若子 Agent 回報失敗：

1. 記錄錯誤訊息（哪個指令、哪一行錯誤）。
2. 派遣**新的子 Agent** 執行同一模塊，將完整錯誤訊息作為額外上下文傳入。
3. 最多重試 **3 次**（該模塊合計最多嘗試 **4 次**）。
4. 超過 3 次仍失敗 → 在 `docs/tasks/progress.md` 標記該模塊為 `FAILED`；**立即停止整個流程**；輸出詳細的失敗報告（含所有錯誤訊息）。

### progress.md 更新方式

找到對應行，將 `- [ ]` 改為 `- [x]`：

```markdown
| M1 | Domain 型別（types.py / config.py 列舉） | - [x] |
```

---

## 子 Agent 派遣規格

派遣子 Agent 時，主 Agent 必須以**獨立任務描述**方式提供完整上下文，因為子 Agent 不繼承主 Agent 的記憶。

### 子 Agent 接收的標準輸入

```
目標模塊：<模塊名稱與編號>
任務清單：docs/tasks/<module>.md
涉及檔案：<詳細設計中列出的檔案清單>
測試指令：<該模塊的 pytest 指令>
前次錯誤：<若首次為空；重試時填入上次的錯誤輸出>
```

### 各模塊派遣參數

| 模塊 | 任務清單 | 主要測試指令 | 涉及檔案（重點） |
|---|---|---|---|
| M1 | `docs/tasks/m1-domain-types.md` | `rtk pytest tests/ -v` | `src/types.py`、`src/config.py`（RestCountMode 列舉）、`src/ui/strings.py` |
| M2 | `docs/tasks/m2-timer-engine.md` | `rtk pytest tests/test_timer_engine.py -v` | `src/timer_engine.py`、`tests/test_timer_engine.py` |
| M3 | `docs/tasks/m3-frame-grabber.md` | `rtk pytest tests/test_frame_grabber.py -v` | `src/capture/video_source.py`、`src/capture/frame_grabber.py`（新建）、`tests/test_frame_grabber.py`（新建） |
| M8 | `docs/tasks/m8-config-settings.md` | `rtk pytest tests/test_config.py -v` | `src/config.py`、`src/ui/settings_schema.py`、`src/ui/settings.py`、`tests/test_config.py` |
| M4 | `docs/tasks/m4-worker.md` | `rtk pytest tests/test_worker.py -v` | `src/app/worker.py`、`tests/test_worker.py` |
| M5 | `docs/tasks/m5-main-window-status.md` | `rtk pytest tests/test_ui.py -v -k presence` | `src/ui/main_window.py`、`src/ui/widgets/status_strip.py`、`src/ui/widgets/presence_badge.py`（新建） |
| M6 | `docs/tasks/m6-action-bar-roi.md` | `rtk pytest tests/test_ui.py tests/test_theme.py -v` | `src/ui/widgets/action_bar.py`、`src/ui/widgets/preview_view.py`、`src/ui/theme.py` |
| M7 | `docs/tasks/m7-reminder-ui.md` | `rtk pytest tests/test_reminder.py -v` | `src/reminder/popup.py`、`src/reminder/return_prompt.py`（新建）、`src/ui/strings.py` |
| M9 | `docs/tasks/m9-app-assembly.md` | `rtk pytest tests/ -v` | `src/main.py` |

---

## 子 Agent 工作指示

以下是主 Agent 派遣子 Agent 時需要附上的**通用工作指示**，每次派遣都應完整傳入：

---

### 子 Agent 標準工作指示

你是一名**模塊實作 Agent**，負責實作指定模塊的所有任務並通過品質關卡。整個過程**不會有人工介入**，你必須自主完成。

#### 步驟 1：理解設計

1. 閱讀 `docs/proposal.md` 中與本模塊對應的需求章節
2. 閱讀 `docs/detailed-design.md` 中本模塊的詳細設計（型別簽章、虛擬碼、測試案例清單）
3. 閱讀 `docs/tasks/<module>.md` 中的完整任務清單

#### 步驟 2：閱讀現有程式碼

閱讀「涉及檔案」中所有現有實作，理解：
- 現有架構與模式
- Import 風格與命名慣例
- 相依注入方式（如何傳入假物件）

**禁止在未讀程式碼的情況下直接修改。**

#### 步驟 3：實作

- 依序完成 `docs/tasks/<module>.md` 的每一個 `- [ ]` 任務
- 遵守 `docs/detailed-design.md` 的型別簽章與介面契約（函式名稱、參數型別不可自行更改）
- 以**最小破壞原則**修改現有檔案：只改任務清單要求的部分
- 新增檔案時，遵循既有模塊的程式碼風格

#### 步驟 4：撰寫 / 更新單元測試

- 在對應的 `tests/` 檔案中實作設計文件中的所有測試案例
- 測試格式：pytest
- 純邏輯模塊（M1、M2、M3）：不引入 Qt，直接 `import` 即可
- Qt 元件（M5、M6、M7）：加上 `@pytest.mark.qt`
- 測試不得依賴真實攝影機、網路、或系統級 I/O（用 `FakeSource`、`tmp_path` 等替代）

#### 步驟 5：品質關卡（全部通過才算成功）

依序執行以下指令，**全部通過才回報成功**：

```bash
# 1. 執行本模塊對應測試
rtk pytest <測試指令> -v

# 2. 確認整個 tests/ 目錄沒有因本次修改而壞掉
rtk pytest tests/ -v

# 3. 型別檢查
rtk mypy src cli

# 4. Lint 檢查
rtk ruff check .
```

若任何一個指令失敗：
- **不要放棄**，嘗試修正錯誤後重新執行
- 最多自行嘗試修正 **3 輪**
- 仍無法通過則回報失敗，並附上完整錯誤訊息

#### 步驟 6：回報結果

**成功時回報：**
```
狀態：成功
修改檔案：<列出所有修改的檔案>
新增檔案：<列出所有新增的檔案>
測試通過數：<pytest 通過數>
mypy：通過
ruff：通過
```

**失敗時回報：**
```
狀態：失敗
失敗指令：<哪個指令失敗>
錯誤訊息：<完整錯誤輸出>
嘗試次數：<自行嘗試了幾次>
```

#### 不得執行的事項

- **不做 git commit / push**
- 不修改任務清單以外的檔案邏輯
- 不用 `# type: ignore` 遮蔽 mypy 錯誤（除非設計文件明示）
- 不新增任務以外的功能（YAGNI）
- 不使用真實外部依賴（攝影機、網路）做測試

---

## 品質標準摘要

| 工具 | 指令 | 標準 |
|---|---|---|
| pytest | `rtk pytest tests/ -v` | 所有測試通過，無跳過 |
| mypy | `rtk mypy src cli` | 零錯誤（不接受 type: ignore 遮蔽） |
| ruff | `rtk ruff check .` | 零錯誤（遵守既有 config） |

---

## 最終 Summary 格式

所有模塊完成後，主 Agent 輸出：

```
===== 實作完成 Summary =====
M1 Domain 型別：成功（第 1 次）
M2 計時/狀態機：成功（第 2 次，修正了 X 問題）
M3 影像擷取：成功（第 1 次）
M8 設定與結構：成功（第 1 次）
M4 協調器：成功（第 1 次）
M5 主視窗與狀態顯示：成功（第 1 次）
M6 動作列與 ROI 編輯：成功（第 1 次）
M7 提醒/休息流程 UI：成功（第 1 次）
M9 應用組裝：成功（第 1 次）

總測試數：XX 通過 / 0 失敗
mypy：通過
ruff：通過
```

若有模塊失敗則列出：`M? <模塊名>：FAILED（已重試 3 次，詳見錯誤報告）`

---

## 開始執行

讀取 `docs/tasks/progress.md`，確認第一個未完成的模塊，立即派遣第一個子 Agent 開始實作。
