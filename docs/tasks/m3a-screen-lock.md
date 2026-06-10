# M3a：平台鎖定函式

> 對應需求：`docs/proposal.md` 需求三（FR-3.6、3.5 行為要點）
> 對應設計：`docs/detailed-design.md` §5.1
> 依賴模塊：無（M3c 依賴本模塊）
> 異動檔案：
> - 新增 `src/app/screen_lock.py`
> - 新增 `tests/test_screen_lock.py`

---

## 任務清單

- [ ] **任務 1：建立 `is_supported()` 與 `lock_screen()`**

  新增 `src/app/screen_lock.py`：

  ```python
  from __future__ import annotations

  import ctypes
  import logging
  import sys

  logger = logging.getLogger(__name__)


  def is_supported() -> bool:
      return sys.platform == "win32"


  def lock_screen() -> bool:
      if not is_supported():
          logger.info("screen_lock: lock_screen no-op (unsupported platform: %s)", sys.platform)
          return False
      return bool(ctypes.windll.user32.LockWorkStation())  # type: ignore[attr-defined]
  ```

  行為（FR-3.6）：
  - `is_supported()`：`sys.platform == "win32"`。
  - `lock_screen()`：非 Windows → 記 log 後回 `False`，**不丟例外**；Windows → 呼叫 `ctypes.windll.user32.LockWorkStation()`，回傳布林結果。

  > `ctypes.windll` 僅存在於 Windows，`mypy`/`ruff` 在非 Windows 開發環境可能對 `windll` 報屬性錯誤——保留 `# type: ignore[attr-defined]` 註解（或依 repo 慣例調整）。

- [ ] **任務 2：撰寫測試（`tests/test_screen_lock.py`）**

  - `test_is_supported_matches_platform`：`screen_lock.is_supported() == (sys.platform == "win32")`。
  - `test_lock_screen_noop_off_windows`：`monkeypatch.setattr(screen_lock, "is_supported", lambda: False)` → `screen_lock.lock_screen() is False`，且不丟例外。

  > **真正的 `LockWorkStation()` 不在自動測試中呼叫**（會鎖住 CI / 開發機）。Windows 路徑靠手動驗收；[[m3c-force-lock-controller]] 的測試一律注入 fake `lock_fn`，不會走到此處的真實實作。

---

## 完成定義（Definition of Done）

- [ ] `is_supported()`、`lock_screen()` 介面與行為與設計文件一致
- [ ] 2 個測試新增並通過（在當前開發平台上）
- [ ] `rtk pytest tests/test_screen_lock.py` 全數通過
- [ ] `rtk ruff check src/app/screen_lock.py` 無錯誤
- [ ] `rtk mypy src/app/screen_lock.py` 無新增錯誤（必要時對 `ctypes.windll` 加型別忽略註解）
