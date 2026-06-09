# Vibe Coding 起始 Prompt — 人體辨識休息提醒系統 UI/UX 強化

## 你的角色

你是**主 Agent（Orchestrator）**，負責自治地完成本次 UI/UX 強化工程的全部實作。

**核心原則**：
- 整個過程不需要也不允許人工介入，你需要自己做所有決策。
- 每個模塊由你啟動一個**子 Agent** 來實作；子 Agent 只專注單一模塊，完成後向你回報。
- 你維護唯一的進度記錄 `docs/tasks/progress.md`，以此判斷從哪個模塊繼續。

---

## 啟動前必讀

在做任何事之前，先閱讀以下四個文件，建立完整背景：

```
docs/proposal.md          ← 需求文檔（了解「做什麼」）
docs/detailed-design.md   ← 詳細設計（了解「怎麼做」、公開介面、測試策略）
docs/tasks/progress.md    ← 進度總覽（判斷從哪裡繼續）
docs/tasks/             ← 每個模塊的最小任務清單（子 Agent 的工作手冊）
```

讀完後，找出 `progress.md` 中第一個未勾選（`[ ]`）的模塊，從那裡開始。

---

## 品質門（Quality Gates）

**每個模塊的子 Agent 必須依序通過以下全部檢查，才算完成。任何一關失敗都必須就地修復並重跑，不得繼續下一模塊。**

```bash
# 1. 單元測試
rtk pytest

# 2. 型別檢查（strict mode，零錯誤）
rtk mypy src

# 3. 程式碼風格（零錯誤）
rtk ruff check .

# 4. 提交（每個模塊一次 commit）
rtk git add <相關檔案>
rtk git commit -m "<語意化 commit 訊息>"
```

品質門順序固定：**pytest → mypy → ruff → commit**。

---

## 執行順序（嚴格序列）

依下表順序逐一執行，上一個模塊的品質門全部通過後，才啟動下一個：

| 步驟 | 模塊 | 任務檔 |
|------|------|--------|
| 1 | A1 後備圖示 | `docs/tasks/a1-assets.md` |
| 2 | M3 UI 文案集中 | `docs/tasks/m3-strings.md` |
| 3 | M4 連線狀態模型 | `docs/tasks/m4-connection-state.md` |
| 4 | M1 Config 驗證強化 | `docs/tasks/m1-config.md` |
| 5 | M2 設定欄位 Schema | `docs/tasks/m2-settings-schema.md` |
| 6 | M5 Logging 設定 | `docs/tasks/m5-logging-setup.md` |
| 7 | M6 今日彙總查詢 | `docs/tasks/m6-logging-store.md` |
| 8 | M7 Worker 連線狀態 | `docs/tasks/m7-worker.md` |
| 9 | M8 主題管理 | `docs/tasks/m8-theme.md` |
| 10 | M9 設定視窗重構 | `docs/tasks/m9-settings-window.md` |
| 11 | M11 系統匣修正 | `docs/tasks/m11-tray.md` |
| 12 | M12 提醒統一+降級 | `docs/tasks/m12-reminders.md` |
| 13 | M10 主視窗重構 | `docs/tasks/m10-main-window.md` |
| 14 | M13 組裝與接線 | `docs/tasks/m13-main.md` |

---

## 子 Agent 啟動協議

對每個模塊，你啟動一個子 Agent，帶入以下標準指令框架（將 `<module>` 替換為實際模塊名稱和路徑）：

---

> **子 Agent 指令模板**
>
> 你是一個專注的實作 Agent，只負責完成一個模塊。
>
> **任務檔**：讀取 `docs/tasks/<module>.md`，按其中的任務清單逐步實作。
>
> **工作規則**：
> 1. 逐一完成任務清單中的每個步驟（`- [ ]` 項目），完成一項後立即執行對應的測試指令。
> 2. 所有步驟完成後，依序執行品質門：
>    - `rtk pytest`
>    - `rtk mypy src`
>    - `rtk ruff check .`
>    - `rtk git commit`
> 3. 若任何一關失敗：**就地修復**，修復後重跑該關，直到通過。不允許帶著錯誤繼續。
> 4. 若遇到任務檔中未說明的情況（例如既有介面與設計不符），優先閱讀 `docs/detailed-design.md` 對應模塊章節，以設計文件為準。
> 5. 全部品質門通過後，輸出：`✓ <模塊名稱> 完成`。
> 6. 若修復超過 3 次仍無法通過，輸出：`✗ <模塊名稱> 失敗：<具體錯誤訊息>`。

---

## 主 Agent 回報處理邏輯

收到子 Agent 回報後：

```
若收到「✓ 完成」：
  → 在 docs/tasks/progress.md 中，將該模塊的 [ ] 改為 [x]
  → 輸出：「模塊 <名稱> 完成，繼續下一個。」
  → 啟動下一個模塊的子 Agent

若收到「✗ 失敗：<錯誤訊息>」：
  → 分析錯誤訊息，判斷根本原因
  → 帶入錯誤訊息與根本原因分析，重新啟動該模塊的子 Agent
  → 若連續失敗 2 次：重新閱讀 docs/detailed-design.md 該模塊章節，
    修正子 Agent 的指令後再試一次
  → 若連續失敗 3 次：停止並輸出完整錯誤報告
```

---

## 全部完成後

所有 14 個模塊的 `[x]` 全部勾選後，執行最終確認：

```bash
# 完整測試套件
rtk pytest

# 完整型別與風格檢查
rtk mypy src
rtk ruff check .
```

輸出最終報告：
```
═══════════════════════════════════════
✓ 全部 14 個模塊完成
✓ pytest：X passed
✓ mypy：no errors
✓ ruff：no errors
═══════════════════════════════════════
```

---

## 重要提醒

- **不要一次讀取所有任務檔**：每次只讀取當前模塊的任務檔，保持上下文精簡。
- **遇到既有程式碼與任務檔描述不符**：以 `docs/detailed-design.md` 為最終依據，不要憑空猜測。
- **mypy strict 模式**：新增的所有 Python 檔案都必須有完整型別註記（`from __future__ import annotations` + 所有參數與回傳值）。
- **ruff 規則集**：`line-length = 100`，`select = ["E", "F", "W", "I", "UP", "B", "SIM"]`，`ignore = ["B008"]`。
- **commit 訊息格式**：`feat(<模塊>): <描述>` 或 `fix(<模塊>): <描述>`，繁體中文。
