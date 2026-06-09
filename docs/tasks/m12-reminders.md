# M12 `src/reminder/` — 提醒統一與媒體降級

**目標**：(a) 媒體載入優雅降級（修 D7）；(b) 三種提醒視覺/文案統一、按鈕依 `reset_mode` 呈現；(c) 修 `FloatingReminder.dismissed` 未發射（D2）；(d) 擴充 `ReminderContext`（M12b）。

**涉及檔案**：
- 新增：`src/reminder/media.py`
- 修改：`src/types.py`（`ReminderContext` 擴充欄位）
- 修改：`src/reminder/popup.py`（使用 media.py，按鈕集依 reset_mode）
- 修改：`src/reminder/floating.py`（修 D2：補發 `dismissed`）
- 修改：`src/reminder/toast.py`（文案統一）
- 修改：`tests/test_reminder.py`

**相依**：M3 文案、M8 語意色、`PySide6`（Widgets/Gui）。

**前置條件**：M3 需先完成。

---

## 任務清單

### M12a — 媒體輔助模塊

- [ ] **1. 建立 `src/reminder/media.py`，實作 `load_pixmap()`**

  ```python
  from __future__ import annotations
  from pathlib import Path
  from PySide6.QtGui import QColor, QPainter, QPixmap
  from PySide6.QtCore import Qt

  def load_pixmap(path: str, *, fallback_text: str = "該休息一下了") -> QPixmap:
      """載入圖片；空路徑 / 不存在 / 毀損 → 繪製含 fallback_text 的預設圖。"""
      if path and Path(path).exists():
          pix = QPixmap(path)
          if not pix.isNull():
              return pix
      return _make_placeholder(fallback_text)

  def _make_placeholder(text: str) -> QPixmap:
      pix = QPixmap(320, 200)
      pix.fill(QColor("#1C1C1E"))
      painter = QPainter(pix)
      painter.setPen(QColor("#F2F2F7"))
      font = painter.font()
      font.setPixelSize(20)
      painter.setFont(font)
      painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, text)
      painter.end()
      return pix

  def is_playable_video(path: str) -> bool:
      """副檔名 + 存在性粗篩。"""
      if not path:
          return False
      suffix = Path(path).suffix.lower()
      return suffix in {".mp4", ".avi", ".mkv", ".mov", ".webm"} and Path(path).exists()

  def safe_sound_url(path: str):
      """空路徑或不存在 → None，否則回傳 QUrl。"""
      from PySide6.QtCore import QUrl
      if not path or not Path(path).exists():
          return None
      return QUrl.fromLocalFile(path)
  ```

- [ ] **2. 新增 media 測試到 `tests/test_reminder.py`**

  ```python
  def test_load_pixmap_missing_path_returns_placeholder(qtbot):
      from src.reminder.media import load_pixmap
      pix = load_pixmap("nonexistent_file.png")
      assert not pix.isNull()

  def test_load_pixmap_empty_path_returns_placeholder(qtbot):
      from src.reminder.media import load_pixmap
      pix = load_pixmap("")
      assert not pix.isNull()

  def test_safe_sound_url_empty_returns_none():
      from src.reminder.media import safe_sound_url
      assert safe_sound_url("") is None
      assert safe_sound_url("nonexistent.wav") is None
  ```

### M12b — 擴充 `ReminderContext`

- [ ] **3. 在 `src/types.py` 的 `ReminderContext` 新增欄位（向後相容）**

  ```python
  @dataclass(frozen=True)
  class ReminderContext:
      work_minutes: int
      media_path: str
      media_type: str
      sound_path: str
      reset_mode: str = "detection"   # 新增
      snooze_minutes: int = 5         # 新增
  ```

  > 給預設值確保既有程式碼不需改動。

- [ ] **4. 確認 `test_types.py` 仍通過（不應需要改動）**

  ```bash
  rtk pytest tests/test_types.py -v
  ```

### M12c — 修正三種提醒

- [ ] **5. 修正 `src/reminder/popup.py`：使用 `media.py` 取代直載（修 D7）**

  找到 `QPixmap(path)` 或 `QLabel.setPixmap(QPixmap(...))` 的載入邏輯，改為：
  ```python
  from src.reminder.media import load_pixmap
  # 使用
  pixmap = load_pixmap(ctx.media_path)
  ```

- [ ] **6. 更新 `PopupReminder` 按鈕集依 `ctx.reset_mode`**

  在 `PopupReminder.show()` 或建構按鈕的地方，依 `ctx.reset_mode` 決定按鈕：
  ```python
  from src.ui import strings

  def _setup_buttons(self, ctx: ReminderContext) -> None:
      self._btn_layout.clear()  # 清除舊按鈕
      if ctx.reset_mode == "snooze":
          primary = strings.REMIND_SNOOZE.format(minutes=ctx.snooze_minutes)
      elif ctx.reset_mode == "dismiss":
          primary = strings.REMIND_START_REST
      else:  # detection
          primary = strings.REMIND_ACK
      btn_primary = QPushButton(primary)
      btn_primary.clicked.connect(self._on_primary)
      btn_close = QPushButton(strings.REMIND_CLOSE)
      btn_close.clicked.connect(self.hide)  # 關閉只隱藏，不 emit dismissed
      self._btn_layout.addWidget(btn_primary)
      self._btn_layout.addWidget(btn_close)

  def _on_primary(self) -> None:
      self.dismissed.emit()
      self.hide()
  ```

- [ ] **7. 修正 `src/reminder/floating.py`：補發 `dismissed`（修 D2）**

  找到 `FloatingReminder`，確認 `dismissed = Signal()` 已宣告，然後在點擊事件補發射：
  ```python
  def mousePressEvent(self, event) -> None:
      self.dismissed.emit()
      self.hide()
      super().mousePressEvent(event)
  ```

- [ ] **8. 新增提醒相關測試到 `tests/test_reminder.py`**

  ```python
  def test_popup_snooze_mode_shows_snooze_button(qtbot):
      from src.reminder.popup import PopupReminder
      from src.types import ReminderContext
      ctx = ReminderContext(
          work_minutes=30, media_path="", media_type="image",
          sound_path="", reset_mode="snooze", snooze_minutes=5
      )
      popup = PopupReminder()
      qtbot.addWidget(popup)
      popup.show_reminder(ctx)
      # 確認「再 5 分鐘」按鈕存在
      buttons = popup.findChildren(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton)
      texts = [b.text() for b in buttons]
      assert any("5" in t for t in texts)

  def test_floating_reminder_emits_dismissed_on_click(qtbot):
      from src.reminder.floating import FloatingReminder
      from src.types import ReminderContext
      ctx = ReminderContext(work_minutes=30, media_path="", media_type="image", sound_path="")
      floating = FloatingReminder()
      qtbot.addWidget(floating)
      dismissed_signals = []
      floating.dismissed.connect(lambda: dismissed_signals.append(True))
      qtbot.mouseClick(floating, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.MouseButton.LeftButton)
      assert len(dismissed_signals) == 1
  ```

- [ ] **9. 執行全部提醒測試確認通過**

  ```bash
  rtk pytest tests/test_reminder.py -v
  ```

- [ ] **10. Commit**

  ```bash
  rtk git add src/reminder/media.py src/reminder/popup.py src/reminder/floating.py src/reminder/toast.py src/types.py tests/test_reminder.py
  rtk git commit -m "feat(M12): 媒體降級、提醒按鈕統一、修正 FloatingReminder.dismissed"
  ```
