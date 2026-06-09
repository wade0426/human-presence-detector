# 總體進度：人體辨識休息提醒系統 — 時間顯示與提醒異常修正

> **上游文件**：`docs/proposal.md`（需求）、`docs/detailed-design.md`（詳細設計）  
> **最後更新**：2026-06-10 01:36（已完成）

## 基線測試結果

- pytest 基線：151 passed（執行前量測）
- 開始執行時間：2026-06-10 00:18

---

## 模塊完成狀態

| 模塊 | 任務檔 | 對應 FR | 狀態 |
|---|---|---|---|
| `src/types.py` | [types.md](./types.md) | FR-1, FR-3 | ✅ 已完成 |
| `src/duration_format.py`（新增） | [duration-format.md](./duration-format.md) | FR-1, FR-3 | ✅ 已完成 |
| `src/today_work_model.py`（新增） | [today-work-model.md](./today-work-model.md) | FR-4 | ✅ 已完成 |
| `src/capture/stream_health.py`（新增） | [stream-health.md](./stream-health.md) | FR-6 | ✅ 已完成 |
| `src/timer_engine.py` | [timer-engine.md](./timer-engine.md) | FR-1, FR-2, FR-4 | ✅ 已完成 |
| `src/config.py` / `settings_schema.py` / `config.yaml` | [config-settings.md](./config-settings.md) | FR-1 | ✅ 已完成 |
| `src/logging_store.py` | [logging-store.md](./logging-store.md) | FR-5 | ✅ 已完成 |
| `src/app/connection_state.py` 等（連線狀態） | [connection-state.md](./connection-state.md) | FR-6 | ✅ 已完成 |
| 提醒派發（`worker.py` / `popup.py` / `toast.py` / `strings.py`） | [reminder-dispatch.md](./reminder-dispatch.md) | FR-3 | ✅ 已完成 |
| `src/ui/widgets/status_strip.py` | [status-strip.md](./status-strip.md) | FR-1, FR-2 | ✅ 已完成 |
| `src/ui/widgets/today_summary_view.py` | [today-summary-view.md](./today-summary-view.md) | FR-4 | ✅ 已完成 |
| `src/ui/main_window.py` | [main-window.md](./main-window.md) | FR-1, FR-4 | ✅ 已完成 |
| `src/main.py` | [main-entrypoint.md](./main-entrypoint.md) | FR-5, FR-6 | ✅ 已完成 |

---

## 建議實作順序（依相依性）

```
第一批（純邏輯，無相依，可平行）
  1. types.py           ← 所有模塊的共同契約
  2. duration_format.py ← 格式化工具，被多處使用

第二批（依賴第一批）
  3. today_work_model.py  ← 依賴 types
  4. stream_health.py     ← 純邏輯，依賴 types
  5. timer_engine.py      ← 依賴 types
  6. config/settings      ← 獨立設定

第三批（依賴第一、二批）
  7. logging_store.py       ← 獨立 DB 邏輯
  8. connection_state.py 等 ← 依賴 stream_health、strings
  9. reminder-dispatch      ← 依賴 duration_format、types

第四批（UI 層，依賴純邏輯）
  10. status_strip.py         ← 依賴 duration_format、types、config
  11. today_summary_view.py   ← 依賴 duration_format

第五批（整合層）
  12. main_window.py   ← 串接 TodayWorkModel、status_strip
  13. main.py          ← 最終接線
```

---

## 驗收檢查清單（按 FR）

- [x] **FR-1**：提醒中顯示「超時 MM:SS」，切換模式後顯示「工作 + 提醒」
- [x] **FR-2**：暫停後數字凍結，恢復後不回溯
- [x] **FR-3**：彈窗顯示實際工作時間，不顯示「0 分鐘」
- [x] **FR-4**：「今日工作」工作中持續更新，休息結束後完整記錄
- [x] **FR-5**：完整一輪流程，背景無 `SQLite objects created in a thread...` 例外
- [x] **FR-6**：串流中斷時 UI 顯示「影像異常」，背景錯誤訊息不刷屏

---

## 最終驗收結果

- pytest：236 passed, 0 failed
- mypy：Found 0 errors
- ruff：All checks passed
- 完成時間：2026-06-10 01:36
