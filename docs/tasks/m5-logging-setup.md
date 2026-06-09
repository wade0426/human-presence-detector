# M5 `src/logging_setup.py` — Log 設定與解碼噪音壓制

**目標**：(a) 設定可輪替的應用程式 log 檔；(b) 壓制 OpenCV / FFmpeg 解碼噪音。

**涉及檔案**：
- 新增：`src/logging_setup.py`
- 新增：`tests/test_logging_setup.py`

**相依**：標準庫 `logging`、`os`；`cv2`（容錯匯入，缺少時只設 env）。

> **順序約束**：`suppress_decoder_noise()` **必須**在任何 `cv2.VideoCapture` 建立**之前**呼叫。`main.py`（M13）在最前段呼叫。

---

## 任務清單

- [ ] **1. 建立 `src/logging_setup.py`，實作 `setup_logging()`**

  ```python
  from __future__ import annotations
  import logging
  import os
  from logging.handlers import RotatingFileHandler
  from pathlib import Path

  def setup_logging(
      log_dir: str = "data/logs",
      level: int = logging.INFO,
      max_bytes: int = 1_000_000,
      backup_count: int = 3,
  ) -> logging.Logger:
      Path(log_dir).mkdir(parents=True, exist_ok=True)
      log_path = Path(log_dir) / "app.log"
      fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

      file_handler = RotatingFileHandler(
          log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
      )
      file_handler.setFormatter(fmt)

      root = logging.getLogger()
      root.setLevel(level)
      root.addHandler(file_handler)
      return root
  ```

- [ ] **2. 實作 `suppress_decoder_noise()`**

  ```python
  def suppress_decoder_noise() -> None:
      os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")
      try:
          import cv2
          cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
      except Exception:
          pass
  ```

- [ ] **3. 新增 `tests/test_logging_setup.py`**

  ```python
  import logging
  import os
  from logging.handlers import RotatingFileHandler

  def test_setup_logging_creates_file_handler(tmp_path):
      from src.logging_setup import setup_logging
      logger = setup_logging(log_dir=str(tmp_path), level=logging.DEBUG)
      handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
      assert len(handlers) >= 1
      log_file = tmp_path / "app.log"
      assert log_file.exists()

  def test_setup_logging_level(tmp_path):
      from src.logging_setup import setup_logging
      logger = setup_logging(log_dir=str(tmp_path), level=logging.WARNING)
      assert logger.level == logging.WARNING

  def test_suppress_decoder_noise_sets_env(monkeypatch):
      monkeypatch.delenv("OPENCV_FFMPEG_LOGLEVEL", raising=False)
      from src.logging_setup import suppress_decoder_noise
      suppress_decoder_noise()
      assert os.environ.get("OPENCV_FFMPEG_LOGLEVEL") == "-8"

  def test_suppress_decoder_noise_no_cv2(monkeypatch):
      """缺少 cv2 時不拋例外。"""
      import builtins
      real_import = builtins.__import__
      def mock_import(name, *args, **kwargs):
          if name == "cv2":
              raise ImportError("no cv2")
          return real_import(name, *args, **kwargs)
      monkeypatch.setattr(builtins, "__import__", mock_import)
      from src.logging_setup import suppress_decoder_noise
      suppress_decoder_noise()  # 不應拋例外
  ```

  > 注意：每個測試之後 logging 的 root handler 會累積，若影響其他測試，可在 fixture 中先清理 root handlers：
  > ```python
  > @pytest.fixture(autouse=True)
  > def clean_root_handlers():
  >     yield
  >     logging.root.handlers.clear()
  > ```

- [ ] **4. 執行測試確認通過**

  ```bash
  rtk pytest tests/test_logging_setup.py -v
  ```

- [ ] **5. Commit**

  ```bash
  rtk git add src/logging_setup.py tests/test_logging_setup.py
  rtk git commit -m "feat(M5): 新增 logging_setup，壓制解碼噪音並建立 log 輪替"
  ```
