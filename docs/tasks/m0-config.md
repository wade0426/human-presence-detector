# M0：設定模型擴充

> 對應需求：`docs/proposal.md` 需求一（1.3 設定欄位）、需求三（3.3 設定欄位）
> 對應設計：`docs/detailed-design.md` §2
> 依賴模塊：無（基礎模塊）。M1b、M2b、M3b、M4 皆依賴本模塊提供的設定型別。
> 異動檔案：
> - 修改 `src/config.py`
> - 擴充 `tests/test_config.py`

---

## 任務清單

- [ ] **任務 1：新增 `ReturnSoundConfig` 並掛入 `ReminderConfig`**

  在 `src/config.py` 新增（建議放在 `FloatingConfig` 之後、`ReminderConfig` 之前）：

  ```python
  @dataclass
  class ReturnSoundConfig:
      enabled: bool = False
      sound_path: str = "data/assets/Radar.mp3"
  ```

  `ReminderConfig` 新增欄位：

  ```python
  return_sound: ReturnSoundConfig = field(default_factory=ReturnSoundConfig)
  ```

  測試（`tests/test_config.py`）：
  - `test_return_sound_defaults`：`ReminderConfig().return_sound.enabled is False`，且 `sound_path == "data/assets/Radar.mp3"`。

- [ ] **任務 2：新增 `ForceLockConfig` 並掛入 `AppConfig`**

  在 `src/config.py` 新增：

  ```python
  @dataclass
  class ForceLockConfig:
      enabled: bool = False
      trigger: str = "overtime"          # "overtime" | "on_rest"
      overtime_threshold_min: float = 10.0
      warning_mode: str = "immediate"    # "countdown_cancel" | "countdown_only" | "immediate"
      countdown_sec: int = 10
  ```

  `AppConfig` 新增頂層欄位：

  ```python
  force_lock: ForceLockConfig = field(default_factory=ForceLockConfig)
  ```

  測試：
  - `test_force_lock_defaults`：`AppConfig().force_lock` 五個欄位皆等於上述預設值。

- [ ] **任務 3：擴充 `validate()` — `force_lock.*` 規則**

  在 `validate()` 中新增一段（取得方式比照既有 `reminder = _section(raw, "reminder")`）：

  ```python
  force_lock = _section(raw, "force_lock")
  trigger = force_lock.get("trigger", ForceLockConfig.trigger)
  if trigger not in {"overtime", "on_rest"}:
      errors.append("force_lock.trigger must be one of: overtime, on_rest")

  warning_mode = force_lock.get("warning_mode", ForceLockConfig.warning_mode)
  if warning_mode not in {"countdown_cancel", "countdown_only", "immediate"}:
      errors.append(
          "force_lock.warning_mode must be one of: countdown_cancel, countdown_only, immediate"
      )

  overtime_threshold_min = force_lock.get(
      "overtime_threshold_min", ForceLockConfig.overtime_threshold_min
  )
  if not _in_range(overtime_threshold_min, min_value=MINUTE_MIN, max_value=MINUTE_MAX):
      errors.append(
          f"force_lock.overtime_threshold_min must satisfy {MINUTE_MIN} <= value <= {MINUTE_MAX}"
      )

  countdown_sec = force_lock.get("countdown_sec", ForceLockConfig.countdown_sec)
  if not isinstance(countdown_sec, int) or isinstance(countdown_sec, bool) or countdown_sec < 1:
      errors.append("force_lock.countdown_sec must be an integer >= 1")
  ```

  > `reminder.return_sound.enabled` 採寬鬆 `bool()` 轉換，不在 `validate()` 中強制報錯（依設計文件 §2.3）。

  測試：
  - `test_validate_force_lock_trigger_invalid`：`trigger="bad"` → 錯誤列表含 `"force_lock.trigger"`。
  - `test_validate_force_lock_warning_mode_invalid`：`warning_mode="bad"` → 錯誤列表含 `"force_lock.warning_mode"`。
  - `test_validate_countdown_sec_min`：`countdown_sec=0` 與 `countdown_sec="abc"` → 皆回報含 `"force_lock.countdown_sec"` 的錯誤；`countdown_sec=1` → 不報錯。
  - 可選：仿照既有 `test_validate_minute_fields`，為 `force_lock.overtime_threshold_min` 加上 `MINUTE_MIN`/`MINUTE_MAX` 邊界 parametrize 測試。

- [ ] **任務 4：擴充 `_app_config_from_dict()` 解析 `return_sound` 與 `force_lock`**

  在 `reminder_raw` 區段內（與 `popup_raw`/`floating_raw` 同層）新增：

  ```python
  return_sound_raw = _section(reminder_raw, "return_sound")
  ```

  並在建構 `ReminderConfig(...)` 時加入：

  ```python
  return_sound=ReturnSoundConfig(
      enabled=bool(return_sound_raw.get("enabled", ReturnSoundConfig.enabled)),
      sound_path=str(return_sound_raw.get("sound_path", ReturnSoundConfig.sound_path)),
  ),
  ```

  在函式頂部（與 `logging_raw`/`ui_raw` 同層）新增：

  ```python
  force_lock_raw = _section(raw, "force_lock")
  ```

  並在 `AppConfig(...)` 回傳值中加入：

  ```python
  force_lock=ForceLockConfig(
      enabled=bool(force_lock_raw.get("enabled", ForceLockConfig.enabled)),
      trigger=str(force_lock_raw.get("trigger", ForceLockConfig.trigger)),
      overtime_threshold_min=float(
          force_lock_raw.get(
              "overtime_threshold_min", ForceLockConfig.overtime_threshold_min
          )
      ),
      warning_mode=str(force_lock_raw.get("warning_mode", ForceLockConfig.warning_mode)),
      countdown_sec=int(
          force_lock_raw.get("countdown_sec", ForceLockConfig.countdown_sec)
      ),
  ),
  ```

  缺鍵時沿用 dataclass 預設值（與既有區段一致的 `.get(key, Default.field)` 模式）。

- [ ] **任務 5：設定往返（round-trip）測試**

  確認 `_serialize_app_config()` **不需修改**——`asdict()` 會自動遞迴序列化巢狀 dataclass，`return_sound`／`force_lock` 會自動出現在輸出 dict 中（僅 `presence.roi` 有特例處理）。

  測試：
  - `test_roundtrip_serialize_force_lock`（使用 `tmp_path`）：
    1. 建立 `AppConfig()`，修改 `force_lock`（例如 `enabled=True`、`trigger="on_rest"`、`warning_mode="countdown_cancel"`、`countdown_sec=20`、`overtime_threshold_min=15.0`）與 `reminder.return_sound`（`enabled=True`、`sound_path="custom.mp3"`）。
    2. `save_config(config, path)` → `load_config(path)`。
    3. 斷言 `reloaded == config`（含 `force_lock` 與 `reminder.return_sound` 的所有欄位）。

---

## 完成定義（Definition of Done）

- [ ] `AppConfig().force_lock` 與 `ReminderConfig().return_sound` 預設值與設計文件一致
- [ ] `validate()` 對 4 種 `force_lock.*` 非法值各自回報含對應欄位名稱的錯誤訊息
- [ ] `config.yaml` save → load round-trip 後 `force_lock`、`reminder.return_sound` 完全一致
- [ ] `rtk pytest tests/test_config.py` 全數通過
- [ ] `rtk ruff check src/config.py` 無錯誤
- [ ] `rtk mypy src` 無新增錯誤
