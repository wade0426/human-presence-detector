# M2 `src/ui/settings_schema.py` — 設定欄位中繼資料

**目標**：以純資料集中描述每個設定欄位，讓設定頁完全由資料驅動；提供點路徑讀寫 `AppConfig` 的工具函式。

**涉及檔案**：
- 新增：`src/ui/settings_schema.py`
- 新增：`tests/test_settings_schema.py`

**相依**：`src/config.py`（dataclass 結構）、`src/types.py`（`ResetMode`）；無 Qt 相依。

---

## 任務清單

- [ ] **1. 建立 `src/ui/settings_schema.py`，定義 WidgetKind 與 FieldSpec**

  ```python
  from __future__ import annotations
  from dataclasses import dataclass
  from enum import Enum
  from typing import Any
  import dataclasses
  from src.config import AppConfig, MINUTE_MIN, MINUTE_MAX

  class WidgetKind(Enum):
      TEXT = "text"
      INT = "int"
      FLOAT = "float"
      CHOICE = "choice"
      PATH = "path"
      BOOL = "bool"

  @dataclass(frozen=True)
  class FieldSpec:
      key: str
      label: str
      hint: str
      widget: WidgetKind
      category: str
      minimum: float | None = None
      maximum: float | None = None
      step: float | None = None
      decimals: int | None = None
      choices: tuple[str, ...] | None = None

  CATEGORIES: tuple[str, ...] = ("基本", "偵測", "提醒", "紀錄", "進階")
  ```

- [ ] **2. 定義 `SCHEMA` — 填入全部欄位（對應 proposal §9）**

  ```python
  SCHEMA: tuple[FieldSpec, ...] = (
      # 基本
      FieldSpec("source.type", "影像來源", "選擇影像來源：網路串流（RTSP）或本機 Webcam。",
                WidgetKind.CHOICE, "基本", choices=("rtsp", "webcam")),
      FieldSpec("source.rtsp_url", "RTSP 位址", "RTSP 串流位址，例 rtsp://帳號:密碼@主機:554/stream。",
                WidgetKind.TEXT, "基本"),
      FieldSpec("source.webcam_index", "Webcam 編號", "本機攝影機編號，通常 0 是內建鏡頭。",
                WidgetKind.INT, "基本", minimum=0),
      FieldSpec("timer.work_threshold_min", "工作門檻（分鐘）",
                "連續工作達此時間就提醒休息。",
                WidgetKind.FLOAT, "基本",
                minimum=MINUTE_MIN, maximum=MINUTE_MAX, step=0.1, decimals=1),
      FieldSpec("timer.reset_threshold_min", "重置門檻（分鐘）",
                "離開超過此時間，才把工作計時歸零。",
                WidgetKind.FLOAT, "基本",
                minimum=MINUTE_MIN, maximum=MINUTE_MAX, step=0.1, decimals=1),
      FieldSpec("timer.required_rest_min", "休息門檻（分鐘）",
                "離開達此時間才算真正完成休息。",
                WidgetKind.FLOAT, "基本",
                minimum=MINUTE_MIN, maximum=MINUTE_MAX, step=0.1, decimals=1),
      # 偵測
      FieldSpec("detection.confidence", "偵測把握度",
                "人體偵測的最低把握度，越高越嚴格、誤判越少但可能漏抓。",
                WidgetKind.FLOAT, "偵測", minimum=0.05, maximum=1.0, step=0.05, decimals=2),
      FieldSpec("presence.min_box_height_ratio", "最小人體高度比例",
                "人體框需占畫面高度的最小比例，用來濾掉遠處的人。",
                WidgetKind.FLOAT, "偵測", minimum=0.05, maximum=1.0, step=0.05, decimals=2),
      FieldSpec("presence.debounce_count", "去抖動次數",
                "連續幾次判定一致才改變在場狀態，避免閃爍誤判。",
                WidgetKind.INT, "偵測", minimum=1),
      FieldSpec("detection.interval_sec", "偵測間隔（秒）",
                "每隔幾秒做一次偵測，越短越即時但越耗資源。",
                WidgetKind.FLOAT, "偵測", minimum=0.1, step=0.1, decimals=1),
      # 提醒
      FieldSpec("reminder.method", "提醒方式",
                "提醒呈現方式：彈出視窗、系統通知、置頂懸浮倒數。",
                WidgetKind.CHOICE, "提醒", choices=("popup", "toast", "floating")),
      FieldSpec("reminder.reset_mode", "提醒重置方式",
                "提醒後如何重置：離開才重置 / 按掉即重置 / 先貪睡。",
                WidgetKind.CHOICE, "提醒", choices=("detection", "dismiss", "snooze")),
      FieldSpec("reminder.repeat_interval_min", "重複提醒間隔（分鐘）",
                "未處理時，每隔多久再提醒一次。",
                WidgetKind.FLOAT, "提醒",
                minimum=MINUTE_MIN, maximum=MINUTE_MAX, step=0.1, decimals=1),
      FieldSpec("reminder.snooze_min", "貪睡時間（分鐘）",
                "按下貪睡後，延後多久再次提醒。",
                WidgetKind.FLOAT, "提醒",
                minimum=MINUTE_MIN, maximum=MINUTE_MAX, step=0.1, decimals=1),
      FieldSpec("reminder.popup.media_path", "提醒媒體路徑",
                "提醒時顯示的圖片或影片檔路徑。",
                WidgetKind.PATH, "提醒"),
      FieldSpec("reminder.popup.media_type", "媒體類型",
                "上面媒體的類型。",
                WidgetKind.CHOICE, "提醒", choices=("image", "video")),
      FieldSpec("reminder.popup.sound_path", "音效路徑",
                "提醒時播放的音效檔，留空則不播放。",
                WidgetKind.PATH, "提醒"),
      FieldSpec("reminder.floating.position", "懸浮視窗位置",
                "置頂懸浮倒數視窗出現的位置。",
                WidgetKind.CHOICE, "提醒",
                choices=("top-right", "top-left", "bottom-right", "bottom-left")),
      # 紀錄
      FieldSpec("logging.enabled", "啟用紀錄",
                "是否把工作 / 休息紀錄寫入資料庫。",
                WidgetKind.BOOL, "紀錄"),
      FieldSpec("logging.db_path", "資料庫路徑",
                "紀錄資料庫（SQLite）檔案位置。",
                WidgetKind.PATH, "紀錄"),
      # 進階
      FieldSpec("detection.model_path", "模型路徑",
                "YOLOv8 模型權重檔路徑。",
                WidgetKind.PATH, "進階"),
      FieldSpec("detection.device", "運算裝置",
                "運算裝置：自動 / CPU / GPU（CUDA）。",
                WidgetKind.CHOICE, "進階", choices=("auto", "cpu", "cuda")),
      FieldSpec("source.reconnect_interval_sec", "重連間隔（秒）",
                "串流斷線後，每隔幾秒嘗試重新連線。",
                WidgetKind.FLOAT, "進階", minimum=0.5, step=0.5, decimals=1),
      FieldSpec("ui.start_minimized", "啟動時最小化",
                "啟動時直接最小化到系統匣。",
                WidgetKind.BOOL, "進階"),
  )
  ```

- [ ] **3. 實作 `fields_for()`**

  ```python
  def fields_for(category: str) -> tuple[FieldSpec, ...]:
      return tuple(f for f in SCHEMA if f.category == category)
  ```

- [ ] **4. 實作 `get_value()`**

  ```python
  def get_value(cfg: AppConfig, key: str) -> Any:
      parts = key.split(".")
      obj: Any = cfg
      for part in parts:
          obj = getattr(obj, part)
      return obj
  ```

- [ ] **5. 實作 `set_value()`（不可變風格，逐層 replace）**

  ```python
  def set_value(cfg: AppConfig, key: str, value: Any) -> AppConfig:
      parts = key.split(".")
      if len(parts) == 2:
          section, field = parts
          sub = getattr(cfg, section)
          new_sub = dataclasses.replace(sub, **{field: value})
          return dataclasses.replace(cfg, **{section: new_sub})
      elif len(parts) == 3:
          section, subsection, field = parts
          sub = getattr(cfg, section)
          subsub = getattr(sub, subsection)
          new_subsub = dataclasses.replace(subsub, **{field: value})
          new_sub = dataclasses.replace(sub, **{subsection: new_subsub})
          return dataclasses.replace(cfg, **{section: new_sub})
      raise ValueError(f"Unsupported key depth: {key}")
  ```

- [ ] **6. 新增 `tests/test_settings_schema.py` 並測試涵蓋率與 round-trip**

  ```python
  from src.config import AppConfig, MINUTE_MIN, MINUTE_MAX
  from src.ui.settings_schema import SCHEMA, CATEGORIES, fields_for, get_value, set_value

  def test_fields_for_covers_all_categories():
      for cat in CATEGORIES:
          assert len(fields_for(cat)) > 0

  def test_get_set_roundtrip():
      cfg = AppConfig()
      for spec in SCHEMA:
          original = get_value(cfg, spec.key)
          restored = set_value(cfg, spec.key, original)
          assert get_value(restored, spec.key) == original

  def test_minute_fields_have_correct_constraints():
      minute_keys = {
          "timer.work_threshold_min", "timer.reset_threshold_min",
          "timer.required_rest_min", "reminder.repeat_interval_min",
          "reminder.snooze_min",
      }
      for spec in SCHEMA:
          if spec.key in minute_keys:
              assert spec.minimum == MINUTE_MIN
              assert spec.maximum == MINUTE_MAX
              assert spec.step == 0.1
              assert spec.decimals == 1
  ```

- [ ] **7. 執行測試確認通過**

  ```bash
  rtk pytest tests/test_settings_schema.py -v
  ```

- [ ] **8. Commit**

  ```bash
  rtk git add src/ui/settings_schema.py tests/test_settings_schema.py
  rtk git commit -m "feat(M2): 新增設定欄位中繼資料 settings_schema"
  ```
