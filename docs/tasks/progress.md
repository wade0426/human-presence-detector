# 實作進度總覽

## 模塊完成狀態

### 基礎層（純邏輯，無 Qt）
- [x] **M1** `src/config.py` — 分鐘欄位驗證強化
- [x] **M2** `src/ui/settings_schema.py` — 設定欄位中繼資料（新增）
- [x] **M3** `src/ui/strings.py` — UI 文案集中（新增）
- [x] **M4** `src/app/connection_state.py` — 連線狀態模型（新增）

### 基礎設施層
- [x] **M5** `src/logging_setup.py` — Log 設定與解碼噪音壓制（新增）
- [x] **A1** `src/ui/icons.py` — 後備程式圖示（新增）

### I/O 介面卡層
- [x] **M6** `src/logging_store.py` — 今日彙總唯讀查詢（修改）

### Qt 接線層
- [x] **M7** `src/app/worker.py` — 豐富連線狀態（修改）

### Qt UI 層
- [x] **M8** `src/ui/theme.py` — 主題管理（新增）
- [x] **M9** `src/ui/settings.py` — 設定視窗重構
- [ ] **M10** `src/ui/main_window.py` + `src/ui/widgets/` — 主視窗重構
- [x] **M11** `src/ui/tray.py` — 系統匣修正（修改）
- [x] **M12** `src/reminder/media.py` + `src/reminder/*` — 提醒統一與媒體降級

### 入口層
- [ ] **M13** `src/main.py` — 組裝與接線（修改）

---

## 建議實作順序

```
A1 → M3 → M4 → M1 → M2 → M5 → M6 → M7 → M8 → M9 → M11 → M12 → M10 → M13
```

> 純邏輯模塊（M1–M4, M5, M6, A1）先完成，確保有堅實基礎再做 Qt UI 層。

---

## 無障礙（FR-6）橫切任務

FR-6 不對應單一模塊，在各 UI 模塊完成後，進行最終橫切掃描：

- [ ] 所有按鈕與 icon-only 控制項設定 `setAccessibleName` / `setAccessibleDescription`
- [ ] 確認 `Tab` 焦點順序合理（Settings、MainWindow、ActionBar）
- [ ] 確認文字對比符合可讀標準（不只靠顏色）
- [ ] 避免固定 px 高度卡死文字（尊重系統字級）
