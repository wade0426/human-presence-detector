# 模塊任務：`src/duration_format.py`（新增）

> **對應需求**：FR-1（狀態列時間格式）、FR-3（彈窗動態單位）  
> **詳細設計**：`docs/detailed-design.md` §4.1  
> **測試檔**：`tests/test_duration_format.py`（新增）

---

## 任務清單

### 1. 建立模組檔案

- [ ] 在 `src/` 下新增 `duration_format.py`
- [ ] 加入模組說明 docstring（用途：把秒數格式化為顯示字串）

### 2. 實作 `format_clock(seconds: float) -> str`

- [ ] 負數或 NaN/inf 截為 0，不丟例外
- [ ] 輸出格式為 `MM:SS`（分鐘可超過 99，如 `'123:45'`）
- [ ] 驗證邊界：`0 → '00:00'`、`59 → '00:59'`、`90 → '01:30'`、`3661 → '61:01'`、`-5 → '00:00'`

### 3. 實作 `format_duration_zh(seconds: float) -> str`

- [ ] 負數或 NaN/inf 以 0 處理，不丟例外
- [ ] `seconds < 60` → `'N 秒'`（向下取整，最小 `'0 秒'`）
- [ ] `seconds >= 60`，餘秒為 0 → `'M 分鐘'`
- [ ] `seconds >= 60`，餘秒不為 0 → `'M 分 S 秒'`
- [ ] 驗證邊界：`0 → '0 秒'`、`29.9 → '29 秒'`、`30 → '30 秒'`、`60 → '1 分鐘'`、`90 → '1 分 30 秒'`、`150 → '2 分 30 秒'`

### 4. 撰寫單元測試（`tests/test_duration_format.py`）

- [ ] 建立測試檔 `tests/test_duration_format.py`
- [ ] 測試 `format_clock` 的所有邊界值（見任務 2）
- [ ] 測試 `format_duration_zh` 的所有邊界值（見任務 3）
- [ ] 測試非有限數輸入不丟例外（`float('nan')`、`float('inf')`）
- [ ] 執行 `rtk pytest tests/test_duration_format.py` 確認全部通過

---

## 驗收標準

- `format_clock` 與 `format_duration_zh` 皆無副作用，純函式
- 所有單元測試通過，無跳過
- 不引入 Qt 或 OpenCV 相依
