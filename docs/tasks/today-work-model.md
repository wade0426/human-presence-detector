# 模塊任務：`src/today_work_model.py`（新增）

> **對應需求**：FR-4（今日工作統計即時更新與完整記錄）  
> **詳細設計**：`docs/detailed-design.md` §4.2  
> **測試檔**：`tests/test_today_work_model.py`（新增）

---

## 任務清單

### 1. 定義 `TodayWorkDisplay` 資料類別

- [ ] 在 `src/today_work_model.py` 新增 `TodayWorkDisplay` frozen dataclass
- [ ] 欄位：`display_seconds: int`（= base + in_progress）、`base_refresh_needed: bool`

### 2. 實作 `TodayWorkModel` 類別

- [ ] 建立 `__init__(self) -> None`，初始化 `_base: int = 0`、`_prev_in_progress: float = 0.0`

- [ ] 實作 `set_base(self, work_seconds: int) -> None`
  - [ ] 設定 `_base`，代表資料庫已完成工作 session 秒數總和

- [ ] 實作 `observe(self, snapshot: TimerSnapshot) -> TodayWorkDisplay`
  - [ ] 取 `in_progress = snapshot.work_elapsed_sec`
  - [ ] 計算 `display_seconds = round(self._base + in_progress)`
  - [ ] 判斷 `base_refresh_needed = (self._prev_in_progress > 0) and (in_progress == 0)`
  - [ ] 更新 `self._prev_in_progress = in_progress`
  - [ ] 回傳 `TodayWorkDisplay(display_seconds=..., base_refresh_needed=...)`

### 3. 確認與 `TimerSnapshot` 互動正確

- [ ] 匯入 `TimerSnapshot` 自 `src/types.py`，不引入 Qt 或 OpenCV
- [ ] 暫停狀態（`work_elapsed` 凍結）→ `display_seconds` 不增加（由 `TimerEngine` 保證）

### 4. 撰寫單元測試（`tests/test_today_work_model.py`）

- [ ] 建立測試檔 `tests/test_today_work_model.py`
- [ ] 測試：`set_base(600)` + 快照 `work_elapsed=30` → `display_seconds=630`
- [ ] 測試：連續快照 `work_elapsed` 從 30→60，`display_seconds` 遞增，`base_refresh_needed=False`
- [ ] 測試：`work_elapsed` 由 60→0（工作結束）→ `base_refresh_needed=True`
- [ ] 測試：`set_base` 更新後 `in_progress=0` → `display=新 base`，無重複累加
- [ ] 測試：SUSPENDED 快照（`work_elapsed` 凍結不變）→ `display_seconds` 不變
- [ ] 執行 `rtk pytest tests/test_today_work_model.py` 確認全部通過

---

## 驗收標準

- 純計算類別，不存取 DB 或 Qt
- `base_refresh_needed` 只在「in_progress 由 > 0 轉 0」的那次 `observe` 為 `True`，其後回 `False`
- 所有單元測試通過
