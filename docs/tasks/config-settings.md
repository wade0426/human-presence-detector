# 模塊任務：`src/config.py` / `ui/settings_schema.py` / `config.yaml`（修改）

> **對應需求**：FR-1（`reminding_display_mode` 設定）  
> **詳細設計**：`docs/detailed-design.md` §3.2、§4.9  
> **測試檔**：`tests/test_config.py`、`tests/test_settings_schema.py`（擴充）

---

## 任務清單

### 1. 修改 `src/config.py`

- [ ] 在 `ReminderConfig` dataclass 新增欄位：
  ```python
  reminding_display_mode: str = "overtime"   # "overtime" | "work_and_reminder"
  ```
- [ ] 在 `validate()` 新增驗證：`reminding_display_mode` 必須為 `{"overtime", "work_and_reminder"}`；不合法時回報錯誤訊息
- [ ] 在 `_app_config_from_dict()`（或等效載入函式）以 `.get("reminding_display_mode", "overtime")` 讀入（缺欄位 → 預設 `"overtime"`）

### 2. 修改 `ui/settings_schema.py`

- [ ] 在「提醒」類別下新增一個 `FieldSpec`：
  ```python
  FieldSpec(
      "reminder.reminding_display_mode",
      "提醒中顯示",
      "提醒中要顯示『超時時間』還是『工作時間＋提醒持續時間』。",
      WidgetKind.CHOICE,
      "提醒",
      choices=("overtime", "work_and_reminder"),
  )
  ```
- [ ] 確認 `get_value` / `set_value` 方法可正確讀寫該欄位

### 3. 修改 `config.yaml`

- [ ] 在 `reminder:` 區塊下新增（可省略，省略時採預設）：
  ```yaml
  reminding_display_mode: overtime
  ```

### 4. 擴充單元測試

- [ ] **`tests/test_config.py`**
  - [ ] 預設 config 的 `reminder.reminding_display_mode == "overtime"`
  - [ ] 缺欄位的舊 yaml 載入成功且採預設 `"overtime"`
  - [ ] 非法值（如 `"foo"`）使 `validate` 回報錯誤（丟 `ConfigError` 或含錯誤訊息）
- [ ] **`tests/test_settings_schema.py`**
  - [ ] schema 包含 `"reminder.reminding_display_mode"` 欄位
  - [ ] `choices` 為 `("overtime", "work_and_reminder")`
  - [ ] `get_value` / `set_value` 可正確讀寫
- [ ] 執行 `rtk pytest tests/test_config.py tests/test_settings_schema.py` 確認通過

---

## 驗收標準

- 舊 `config.yaml`（無新欄位）仍可正常載入，採預設 `"overtime"`
- 非法值有明確錯誤訊息
- 設定畫面 schema 含正確 `choices`
