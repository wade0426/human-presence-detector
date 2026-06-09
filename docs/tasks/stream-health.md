# 模塊任務：`src/capture/stream_health.py`（新增）

> **對應需求**：FR-6（RTSP 串流穩定性與狀態呈現）  
> **詳細設計**：`docs/detailed-design.md` §4.3  
> **測試檔**：`tests/test_stream_health.py`（新增）

---

## 任務清單

### 1. 定義 `StreamHealth` 枚舉

- [ ] 在 `src/capture/stream_health.py` 新增 `StreamHealth(Enum)`
- [ ] 成員：`OK = "ok"`、`NO_SIGNAL = "no_signal"`、`TIMEOUT = "timeout"`、`DISCONNECTED = "disconnected"`
- [ ] 定義常數 `DEFAULT_STREAM_TIMEOUT_SEC: float = 10.0`

### 2. 實作 `StreamHealthMonitor` 類別

- [ ] `__init__(self, timeout_sec: float = DEFAULT_STREAM_TIMEOUT_SEC, clock: Callable[[], float] = time.monotonic) -> None`
  - [ ] 初始化 `_last_frame_t = clock()`（避免啟動瞬間誤判逾時）
  - [ ] 儲存 `_timeout_sec`

- [ ] `update(self, has_frame: bool, is_opened: bool, now: float) -> StreamHealth`
  - [ ] `has_frame=True` → 更新 `_last_frame_t = now`，回傳 `OK`
  - [ ] `has_frame=False` 且 `is_opened=True` → 比較 `(now - _last_frame_t)` 與 `timeout`：小於 timeout 回 `NO_SIGNAL`，否則回 `TIMEOUT`
  - [ ] `is_opened=False` → 回傳 `DISCONNECTED`

### 3. 確認純邏輯設計

- [ ] 不引入 Qt 或 OpenCV
- [ ] 使用注入 `clock` 而非直接呼叫 `time.monotonic()`（使測試可控）

### 4. 撰寫單元測試（`tests/test_stream_health.py`）

- [ ] 建立測試檔 `tests/test_stream_health.py`
- [ ] 注入假時鐘（`lambda: t` 形式）
- [ ] 測試：首次 `update(False, True, t0)` → `NO_SIGNAL`（未超 timeout）
- [ ] 測試：持續 `has_frame=False`，時間超越 `timeout_sec` → `TIMEOUT`
- [ ] 測試：`is_opened=False` → `DISCONNECTED`（不論 `has_frame`）
- [ ] 測試：`has_frame=True` 後再 `False`，逾時計算自最後一張影像起算
- [ ] 執行 `rtk pytest tests/test_stream_health.py` 確認全部通過

---

## 驗收標準

- 純計算類別，不丟例外
- 注入時鐘可精確控制時間，所有狀態轉換都有對應測試
- 不引入 Qt 或 OpenCV 相依
