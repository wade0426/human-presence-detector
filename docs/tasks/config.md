# 設定管理 `config.py`

> **對應檔案**：`src/config.py`、`tests/test_config.py`  
> **前置條件**：[[types]]  
> **相依**：`pyyaml`、`src.types.BBox`、`src.types.ResetMode`

## 任務

- [ ] **C1** 建立 `src/config.py`，定義以下 dataclass（照 `docs/detailed-design.md` §5.1 的欄位與預設值）：
  - `SourceConfig`、`DetectionConfig`、`PresenceConfig`、`TimerConfig`
  - `PopupConfig`、`FloatingConfig`、`ReminderConfig`、`LoggingConfig`、`UIConfig`
  - `AppConfig`（組合上述所有 Config）
  - `class ConfigError(Exception): ...`

- [ ] **C2** 實作 `validate(raw: dict) -> list[str]`，驗證以下規則（回傳錯誤訊息清單，空清單代表通過）：
  - `source.type` ∈ `{rtsp, webcam}`；`rtsp` 時 `rtsp_url` 不可為空
  - `0 < confidence ≤ 1`、`0 < min_box_height_ratio ≤ 1`、`debounce_count ≥ 1`
  - `work_threshold_min > 0`、`reset_threshold_min > 0`、`required_rest_min > 0`
  - `reminder.method` ∈ `{popup, toast, floating}`
  - `reset_mode` 可對應到 `ResetMode` enum
  - `media_type` ∈ `{image, video}`

- [ ] **C3** 實作 `load_config(path: str) -> AppConfig`：
  - 路徑不存在 → 回傳 `AppConfig()`（全預設）
  - 載入 YAML 並呼叫 `validate`；有錯誤 → raise `ConfigError`
  - 缺漏欄位以 dataclass 預設值補齊
  - `roi` list `[x, y, w, h]` → `BBox`；`reset_mode` 字串 → `ResetMode`

- [ ] **C4** 實作 `save_config(config: AppConfig, path: str) -> None`：
  - 將 `AppConfig` 序列化為 dict（`BBox` → list，`ResetMode` → `.value` 字串）
  - 以 `yaml.dump` 寫入 path

- [ ] **C5** 建立 `tests/test_config.py`，測試以下情境：
  - 不存在路徑 → `load_config` 回傳 `AppConfig()`（全預設值）
  - YAML 缺少 `detection` 區塊 → 仍以預設補齊，不報錯
  - `confidence=2.0` → `validate` 回傳含 `confidence` 字串的錯誤清單
  - `source.type='x'` → `validate` 回傳含 `source.type` 錯誤
  - `source.type='rtsp'` 且 `rtsp_url=''` → `validate` 回傳錯誤
  - round-trip：`save_config` 後 `load_config` 回傳相同值（含 `roi` BBox 與 `reset_mode` 轉換）

- [ ] **C6** 執行 `rtk pytest tests/test_config.py -v` 確認全部通過

- [ ] **C7** `git commit -m "feat: add config load/validate/save"`
