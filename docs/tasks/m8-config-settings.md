# M8 設定與結構

**涉及檔案**：
- 修改：`src/config.py`
- 修改：`src/ui/settings_schema.py`
- 修改：`src/ui/settings.py`
- 修改：`tests/test_config.py`
- 修改：`tests/test_settings_schema.py`（若存在）

**相依**：M1（`RestCountMode` 列舉）

---

## 任務清單

### config.py — TimerConfig

- [ ] 新增欄位 `rest_count_mode: str = "presence"`

### config.py — ReminderConfig

- [ ] 移除欄位 `reset_mode`
- [ ] 移除欄位 `snooze_min`

### config.py — validate()

- [ ] 移除對 `reset_mode` 的驗證邏輯
- [ ] 移除對 `snooze_min` 的範圍檢查
- [ ] 新增：`timer.rest_count_mode` 需在 `{"presence", "fixed"}` 內，否則報錯

### config.py — _app_config_from_dict() 與 _serialize_app_config()

- [ ] 移除讀取/寫出 `reset_mode`（使用 `.get()` 忽略舊鍵，不報錯）
- [ ] 移除讀取/寫出 `snooze_min`
- [ ] 新增讀取/寫出 `timer.rest_count_mode`

### settings_schema.py — SCHEMA

- [ ] 移除 `FieldSpec("reminder.reset_mode", ...)`
- [ ] 移除 `FieldSpec("reminder.snooze_min", ...)`
- [ ] 新增 `FieldSpec("timer.rest_count_mode", "休息計算方式", "presence＝必須離座才算休息；fixed＝固定倒數。", CHOICE, "基本", choices=("presence", "fixed"))`

### settings.py

- [ ] 移除 `_get_widget_value` 中針對 `reminder.reset_mode` / `ResetMode` 的特例邏輯

---

## 單元測試（`tests/test_config.py`）

- [ ] 測試 1：預設 `TimerConfig().rest_count_mode == "presence"`
- [ ] 測試 2：`validate()` 對 `rest_count_mode = "invalid"` 報錯；對 `"presence"` / `"fixed"` 通過
- [ ] 測試 3：載入含舊 `reminder.reset_mode` / `reminder.snooze_min` 的 YAML → 不報錯、欄位被忽略
- [ ] 測試 4：round-trip（save → load）後 `rest_count_mode` 保留；序列化輸出不含 `reset_mode` / `snooze_min`
- [ ] 測試 5：`settings_schema.SCHEMA` 不含 `reset_mode` / `snooze_min` 欄位；含 `timer.rest_count_mode`

---

## 驗收

- [ ] `rtk pytest tests/test_config.py -v` 全通過
- [ ] `rtk pytest tests/test_settings_schema.py -v` 全通過（若存在）
- [ ] 舊版 `config.yaml`（含 reset_mode/snooze_min）可正常載入不報錯
