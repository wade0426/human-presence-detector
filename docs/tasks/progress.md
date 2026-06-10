# 總體進度

> 對應需求文檔：`docs/proposal.md`（休息結束音效／清除資料／強制休息鎖定／強化提示說明／修正介面文字錯誤）
> 對應設計文檔：`docs/detailed-design.md`
> 任務檔目錄：`docs/tasks/`

本文件追蹤 13 個模塊的完成狀態。每個模塊的細項任務（含程式碼、測試、完成定義）請見對應的 `docs/tasks/<module-name>.md`。模塊全部完成後，請執行整合驗證（見文末）。

---

## 建議實作順序（依 §1.2 依賴方向拓撲排序）

- [x] 1. [[m0-config]] — M0 設定模型擴充（`src/config.py`，新增 `ReturnSoundConfig`／`ForceLockConfig`）
- [x] 2. [[m5-text-fixes]] — M5 文字修正（`strings.py`／`settings_schema.py` 錯字與引號掃描）
- [x] 3. [[m1a-sound-player]] — M1a 循環音效播放器（`src/reminder/sound.py`，新）
- [x] 4. [[m1b-return-prompt-sound]] — M1b 「歡迎回來」對話框播放音效
- [x] 5. [[m2a-logging-store-clear]] — M2a 紀錄清除方法（`SessionStore.clear_today`/`clear_all`）
- [x] 6. [[m2b-clear-data-service]] — M2b 清除服務（`ClearScope`/`ClearResult`/`ClearDataService`）
- [x] 7. [[m2c-clear-data-dialog]] — M2c 清除對話框與啟動流程（`ClearDataDialog`/`run_clear_data_flow`）
- [x] 8. [[m3a-screen-lock]] — M3a 平台鎖定函式（`is_supported`/`lock_screen`）
- [x] 9. [[m3b-force-lock-policy]] — M3b 鎖定決策（純邏輯，`ForceLockPolicy`）
- [x] 10. [[m3d-force-lock-window]] — M3d 倒數警示視窗（`ForceLockCountdownWindow`）
- [x] 11. [[m3c-force-lock-controller]] — M3c 鎖定控制器（`ForceLockController`）
- [x] 12. [[m4-tooltips]] — M4 提示與 tooltip（`FieldSpec.tooltip`、新分類「強制休息」、設定頁清除鈕）
- [x] 13. [[int-integration]] — INT 整合接線（`main.py`／`main_window.py`）

> M5 與 M0 互不相依，可平行進行；但建議先完成 M5，建立乾淨的字串／引號基準，供 M2c、M3d、M4 新增字串時遵循同樣規範。M3 系列建議順序為 M3a → M3b → M3d → M3c（M3c 同時依賴 M3a/M3b/M3d）。

---

## 模塊清單

| # | 模塊 | 異動檔案 | 對應需求 | Qt？ | 任務檔 |
| --- | --- | --- | --- | --- | --- |
| 1 | M0 設定模型擴充 | `src/config.py` (M) | 一、三 | 否 | [m0-config.md](m0-config.md) |
| 2 | M5 文字修正 | `src/ui/strings.py` (M)、`src/ui/settings_schema.py` (M) | 五 | 否 | [m5-text-fixes.md](m5-text-fixes.md) |
| 3 | M1a 循環音效播放器 | `src/reminder/sound.py` (N) | 一 | 是 | [m1a-sound-player.md](m1a-sound-player.md) |
| 4 | M1b 回來對話框音效 | `src/reminder/return_prompt.py` (M) | 一 | 是 | [m1b-return-prompt-sound.md](m1b-return-prompt-sound.md) |
| 5 | M2a 紀錄清除方法 | `src/logging_store.py` (M) | 二 | 否 | [m2a-logging-store-clear.md](m2a-logging-store-clear.md) |
| 6 | M2b 清除服務 | `src/app/clear_data.py` (N) | 二 | 否 | [m2b-clear-data-service.md](m2b-clear-data-service.md) |
| 7 | M2c 清除對話框與流程 | `src/ui/clear_data_dialog.py` (N) | 二 | 是 | [m2c-clear-data-dialog.md](m2c-clear-data-dialog.md) |
| 8 | M3a 平台鎖定函式 | `src/app/screen_lock.py` (N) | 三 | 否 | [m3a-screen-lock.md](m3a-screen-lock.md) |
| 9 | M3b 鎖定決策（純） | `src/app/force_lock.py` (N) | 三 | 否 | [m3b-force-lock-policy.md](m3b-force-lock-policy.md) |
| 10 | M3d 倒數警示視窗 | `src/ui/force_lock_window.py` (N) | 三 | 是 | [m3d-force-lock-window.md](m3d-force-lock-window.md) |
| 11 | M3c 鎖定控制器 | `src/app/force_lock_controller.py` (N) | 三 | 是 | [m3c-force-lock-controller.md](m3c-force-lock-controller.md) |
| 12 | M4 提示與 tooltip | `src/ui/settings_schema.py` (M)、`src/ui/settings.py` (M) | 四 | 部分 | [m4-tooltips.md](m4-tooltips.md) |
| 13 | INT 整合接線 | `src/main.py` (M)、`src/ui/main_window.py` (M) | 一～三 | 是 | [int-integration.md](int-integration.md) |

> (N) = 新增檔案，(M) = 修改既有檔案。

---

## 需求覆蓋（§11 設計自我審查）

- [x] **需求一　休息結束音效** — 模塊：M0、M1a、M1b、INT
  驗收：啟用時循環播放／確認後停止／關閉視窗不停止／停用時無聲／音效檔缺失時容錯不崩潰。
- [x] **需求二　清除資料** — 模塊：M0（重設用）、M2a、M2b、M2c、M4（設定頁按鈕）、INT
  驗收：今日／全部／全部並重設三種範圍／預設選取今日／二次確認／主視窗與設定頁兩入口／清除後即時刷新今日統計／重設後提示需重啟。
- [x] **需求三　強制休息鎖定** — 模塊：M0、M3a、M3b、M3c、M3d、INT
  驗收：預設關閉／`overtime`與`on_rest`兩種觸發時機／`immediate`、`countdown_cancel`、`countdown_only`三種警示方式／同一週期只觸發一次／非 Windows 平台 no-op 不崩潰／不回寫計時狀態。
- [x] **需求四　強化提示說明** — 模塊：M4
  驗收：所有設定欄位皆有非空 `hint`；`reminder.method`/`timer.rest_count_mode`/`reminder.reminding_display_mode` 等關鍵欄位有完整 tooltip；`SettingsWindow` 元件套用 tooltip。
- [x] **需求五　修正介面文字錯誤** — 模塊：M5
  驗收：`reminder.reminding_display_mode` 的 hint 引號修正為成對「」；`strings.py`／`settings_schema.py` 全面掃描無 `》` 殘留；不改變任何文字語意。

---

## 整合驗證（全部模塊完成後）

- [x] `rtk pytest` 全專案測試通過
- [x] `rtk ruff check .`
- [x] `rtk mypy src cli`
- [ ] 手動驗收（Windows）：
  - [ ] 設定 `reminder.return_sound.enabled=true` → 觸發「歡迎回來」時可聽到循環音效，按確認後停止
  - [ ] 主視窗與設定頁「清除資料」皆可開啟對話框並完成三種範圍的清除與刷新
  - [ ] 設定 `force_lock.enabled=true`，分別測試 `overtime`/`on_rest` 觸發與 `immediate`/`countdown_cancel`/`countdown_only` 三種警示模式，確認 `LockWorkStation()` 實際鎖定畫面
  - [ ] 設定頁「強制休息」分類可正常調整上述欄位並儲存
