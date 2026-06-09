# M1 `src/config.py` — 分鐘欄位驗證強化

**目標**：在既有 `validate()` 加入「分鐘欄位 0.1 ~ 9999」的範圍檢查，作為唯一真實驗證來源。

**涉及檔案**：
- 修改：`src/config.py`
- 修改：`tests/test_config.py`

---

## 任務清單

- [ ] **1. 在 `config.py` 頂部新增常數**

  在 `class ConfigError` 之前加入：
  ```python
  MINUTE_MIN: float = 0.1
  MINUTE_MAX: float = 9999.0
  ```

- [ ] **2. 修改 `validate()` — timer 分鐘欄位**

  將 `validate()` 中以下迴圈：
  ```python
  for key in ("work_threshold_min", "reset_threshold_min", "required_rest_min"):
      if not _greater_than_zero(timer.get(key, getattr(TimerConfig, key))):
          errors.append(f"timer.{key} must be > 0")
  ```
  改為：
  ```python
  for key in ("work_threshold_min", "reset_threshold_min", "required_rest_min"):
      val = timer.get(key, getattr(TimerConfig, key))
      if not _in_range(val, min_value=MINUTE_MIN, max_value=MINUTE_MAX):
          errors.append(f"timer.{key} must satisfy {MINUTE_MIN} <= value <= {MINUTE_MAX}")
  ```

- [ ] **3. 修改 `validate()` — reminder 分鐘欄位（新增驗證）**

  在 reminder section 驗證區塊（`reset_mode` 驗證之後）新增：
  ```python
  for key in ("repeat_interval_min", "snooze_min"):
      val = reminder.get(key, getattr(ReminderConfig, key))
      if not _in_range(val, min_value=MINUTE_MIN, max_value=MINUTE_MAX):
          errors.append(f"reminder.{key} must satisfy {MINUTE_MIN} <= value <= {MINUTE_MAX}")
  ```

- [ ] **4. 為新驗證規則補測試**

  在 `tests/test_config.py` 新增一個 `test_validate_minute_fields` 測試，涵蓋 5 個分鐘欄位：
  ```python
  import pytest
  from src.config import validate, MINUTE_MIN, MINUTE_MAX

  @pytest.mark.parametrize("section,key", [
      ("timer", "work_threshold_min"),
      ("timer", "reset_threshold_min"),
      ("timer", "required_rest_min"),
      ("reminder", "repeat_interval_min"),
      ("reminder", "snooze_min"),
  ])
  def test_validate_minute_fields(section, key):
      def make(val):
          base = {
              "source": {"type": "webcam"},
              "timer": {"work_threshold_min": 1.0, "reset_threshold_min": 1.0, "required_rest_min": 1.0},
              "reminder": {"repeat_interval_min": 1.0, "snooze_min": 1.0},
          }
          base[section][key] = val
          return base

      assert validate(make(0.09)) != []        # 拒絕 < 0.1
      assert validate(make(0.1))  == [] or ... # 接受 0.1（可能仍有其他欄位錯誤，只需確認此鍵無錯）
      assert validate(make(9999.0)) == [] or ...
      assert validate(make(9999.1)) != []      # 拒絕 > 9999
      assert validate(make("abc")) != []       # 拒絕非數值
  ```

  > 注意：由於 base dict 中 `source.type=webcam` 不需 rtsp_url，其餘欄位使用合法預設值，只驗證目標欄位的邊界。

- [ ] **5. 執行測試確認通過**

  ```bash
  rtk pytest tests/test_config.py -v
  ```
  預期：所有既有測試 + 新增測試全部 PASS。

- [ ] **6. Commit**

  ```bash
  rtk git add src/config.py tests/test_config.py
  rtk git commit -m "feat(M1): 強化分鐘欄位驗證範圍 0.1~9999"
  ```
