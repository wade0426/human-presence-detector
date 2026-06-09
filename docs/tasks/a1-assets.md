# A1 `src/ui/icons.py` — 後備程式圖示

**目標**：提供程式內繪製的後備圖示，確保缺少外部資產時 `No Icon set` 不再出現。

**涉及檔案**：
- 新增：`src/ui/icons.py`
- 新增：`tests/test_icons.py`

**相依**：`PySide6`（`QIcon`、`QPixmap`、`QPainter`、`QColor`）。

---

## 任務清單

- [ ] **1. 建立 `src/ui/icons.py`，實作 `make_app_icon()`**

  ```python
  from __future__ import annotations
  from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

  def make_app_icon(size: int = 64) -> QIcon:
      """以 QPainter 繪製簡單的佔位圖示，確保不依賴外部檔案。"""
      pixmap = QPixmap(size, size)
      pixmap.fill(QColor("#007AFF"))
      painter = QPainter(pixmap)
      painter.setPen(QColor("#FFFFFF"))
      font = painter.font()
      font.setPixelSize(int(size * 0.5))
      font.setBold(True)
      painter.setFont(font)
      painter.drawText(pixmap.rect(), 0x84, "H")   # 0x84 = AlignCenter
      painter.end()
      return QIcon(pixmap)

  def load_app_icon(asset_path: str = "data/assets/icon.png", size: int = 64) -> QIcon:
      """優先載入外部檔案，不存在或空時回退 make_app_icon()。"""
      from pathlib import Path
      if Path(asset_path).exists():
          icon = QIcon(asset_path)
          if not icon.isNull():
              return icon
      return make_app_icon(size)
  ```

- [ ] **2. 新增 `tests/test_icons.py`**

  ```python
  import pytest
  from pytestqt.plugin import QtBot

  def test_make_app_icon_not_null(qtbot):
      from src.ui.icons import make_app_icon
      icon = make_app_icon()
      assert not icon.isNull()

  def test_load_app_icon_fallback_when_missing(qtbot, tmp_path):
      from src.ui.icons import load_app_icon
      icon = load_app_icon(asset_path=str(tmp_path / "nonexistent.png"))
      assert not icon.isNull()
  ```

- [ ] **3. 執行測試確認通過**

  ```bash
  rtk pytest tests/test_icons.py -v
  ```

- [ ] **4. Commit**

  ```bash
  rtk git add src/ui/icons.py tests/test_icons.py
  rtk git commit -m "feat(A1): 新增後備程式圖示 icons.py"
  ```
