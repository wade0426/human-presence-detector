# M2b：清除服務

> 對應需求：`docs/proposal.md` 需求二（FR-2.x）
> 對應設計：`docs/detailed-design.md` §4.2
> 依賴模塊：[[m0-config]]（`AppConfig`/`save_config`）、[[m2a-logging-store-clear]]（`SessionStore.clear_today/clear_all`）
> 異動檔案：
> - 新增 `src/app/clear_data.py`
> - 新增 `tests/test_clear_data.py`

---

## 任務清單

- [ ] **任務 1：建立 `ClearScope` 與 `ClearResult`**

  新增 `src/app/clear_data.py`：

  ```python
  from __future__ import annotations

  from dataclasses import dataclass
  from enum import Enum

  from src.config import AppConfig, save_config
  from src.logging_store import SessionStore


  class ClearScope(Enum):
      TODAY = "today"
      ALL = "all"
      ALL_AND_RESET = "all_and_reset"


  @dataclass(frozen=True)
  class ClearResult:
      deleted: int
      reset_config: bool
  ```

- [ ] **任務 2：建立 `ClearDataService`**

  ```python
  class ClearDataService:
      def __init__(self, store: SessionStore, config_path: str) -> None:
          self._store = store
          self._config_path = config_path

      def clear(self, scope: ClearScope) -> ClearResult:
          if scope is ClearScope.TODAY:
              deleted = self._store.clear_today()
              return ClearResult(deleted=deleted, reset_config=False)

          if scope is ClearScope.ALL:
              deleted = self._store.clear_all()
              return ClearResult(deleted=deleted, reset_config=False)

          # ClearScope.ALL_AND_RESET
          deleted = self._store.clear_all()
          save_config(AppConfig(), self._config_path)
          return ClearResult(deleted=deleted, reset_config=True)
  ```

  行為對照表（設計文件 §4.2）：

  | scope | 動作 | 回傳 |
  | --- | --- | --- |
  | `TODAY` | `store.clear_today()` | `ClearResult(deleted=n, reset_config=False)` |
  | `ALL` | `store.clear_all()` | `ClearResult(deleted=n, reset_config=False)` |
  | `ALL_AND_RESET` | `store.clear_all()` → `save_config(AppConfig(), config_path)` | `ClearResult(deleted=n, reset_config=True)` |

- [ ] **任務 3：撰寫測試（`tests/test_clear_data.py`，純 Python，無 Qt）**

  - `test_clear_today_scope`：建立指向 `tmp_path` sqlite 的 `SessionStore`，寫入今日＋非今日各一筆 → `service.clear(ClearScope.TODAY)` → `result.deleted == 1`（今日筆數）、`result.reset_config is False`、非今日列仍存在。
  - `test_clear_all_scope`：寫入多筆 → `service.clear(ClearScope.ALL)` → `result.deleted == 寫入總筆數`、`result.reset_config is False`、`store.today_summary()` 全 0。
  - `test_clear_all_and_reset_writes_default_config`：
    1. 建立 `tmp_path` 下的 `config.yaml`，內容為非預設值（例如先 `save_config(AppConfig(timer=TimerConfig(work_threshold_min=99.0)), config_path)`）。
    2. 寫入若干 session 列。
    3. `service.clear(ClearScope.ALL_AND_RESET)`。
    4. 斷言 `result.reset_config is True`，且 `load_config(config_path) == AppConfig()`（已回到全預設值）。

  > 注入點：真實 `SessionStore` 指向臨時 db（`tmp_path`），`config_path` 為臨時檔；完全不依賴 Qt。

---

## 完成定義（Definition of Done）

- [ ] `ClearScope`、`ClearResult`、`ClearDataService` 介面與簽章與設計文件一致
- [ ] 3 個測試新增並通過
- [ ] `rtk pytest tests/test_clear_data.py` 全數通過
- [ ] `rtk ruff check src/app/clear_data.py` 無錯誤
- [ ] `rtk mypy src/app/clear_data.py` 無錯誤
