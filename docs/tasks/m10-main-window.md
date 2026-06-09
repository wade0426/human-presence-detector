# M10 `src/ui/main_window.py` + `src/ui/widgets/` — 主視窗重構

**目標**：以「內容優先」重整主視窗，拆出可獨立測試的子元件。

**涉及檔案**：
- 新增目錄：`src/ui/widgets/`
- 新增：`src/ui/widgets/__init__.py`
- 新增：`src/ui/widgets/preview_view.py`
- 新增：`src/ui/widgets/status_strip.py`
- 新增：`src/ui/widgets/connection_badge.py`
- 新增：`src/ui/widgets/today_summary_view.py`
- 新增：`src/ui/widgets/action_bar.py`
- 重構：`src/ui/main_window.py`
- 修改：`tests/test_ui.py`

**相依**：M4（`ConnectionState`）、M3（文案）、M6（`TodaySummary`）、M8（主題）、`src/types.py`。

**前置條件**：M3、M4、M6 需先完成。

---

## 任務清單

### 子元件：PreviewView

- [ ] **1. 建立 `src/ui/widgets/preview_view.py`**

  ```python
  from __future__ import annotations
  from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QRubberBand, QSizePolicy
  from PySide6.QtCore import Signal, QPoint, QRect, QSize, Qt
  from PySide6.QtGui import QImage, QPixmap
  from src.types import BBox, Frame

  class PreviewView(QWidget):
      roi_committed = Signal(object)   # BBox，放開滑鼠且在編輯模式時

      def __init__(self, parent: QWidget | None = None) -> None:
          super().__init__(parent)
          self._edit_mode = False
          self._origin: QPoint | None = None
          self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
          self._label = QLabel(self)
          self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
          self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
          layout = QVBoxLayout(self)
          layout.setContentsMargins(0, 0, 0, 0)
          layout.addWidget(self._label)
          self._overlay_text = ""

      def set_frame(self, frame: Frame) -> None:
          h, w = frame.image.shape[:2]
          image = QImage(frame.image.data, w, h, 3 * w, QImage.Format.Format_RGB888)
          self._label.setPixmap(
              QPixmap.fromImage(image).scaled(
                  self._label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                  Qt.TransformationMode.SmoothTransformation,
              )
          )

      def set_roi(self, roi: BBox) -> None:
          self._roi = roi

      def set_edit_mode(self, on: bool) -> None:
          self._edit_mode = on
          self.setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.ArrowCursor)

      def set_overlay_text(self, text: str) -> None:
          self._overlay_text = text
          if not text:
              self._label.setText("")
          else:
              self._label.setText(f'<div style="font-size:16px; color:#FFF; background:#0008; padding:8px">{text}</div>')

      def mousePressEvent(self, event) -> None:
          if self._edit_mode and event.button() == Qt.MouseButton.LeftButton:
              self._origin = event.position().toPoint()
              self._rubber.setGeometry(QRect(self._origin, QSize()))
              self._rubber.show()

      def mouseMoveEvent(self, event) -> None:
          if self._edit_mode and self._origin:
              self._rubber.setGeometry(
                  QRect(self._origin, event.position().toPoint()).normalized()
              )

      def mouseReleaseEvent(self, event) -> None:
          if self._edit_mode and self._origin and event.button() == Qt.MouseButton.LeftButton:
              rect = QRect(self._origin, event.position().toPoint()).normalized()
              self._rubber.hide()
              self._origin = None
              pw, ph = max(self.width(), 1), max(self.height(), 1)
              roi = BBox(
                  x=rect.x() / pw,
                  y=rect.y() / ph,
                  w=rect.width() / pw,
                  h=rect.height() / ph,
              )
              self.roi_committed.emit(roi)
  ```

### 子元件：StatusStrip

- [ ] **2. 建立 `src/ui/widgets/status_strip.py`**

  ```python
  from __future__ import annotations
  from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar
  from src.types import TimerSnapshot
  from src.ui.strings import STATE_TEXT

  class StatusStrip(QWidget):
      def __init__(self, parent: QWidget | None = None) -> None:
          super().__init__(parent)
          self._state_label = QLabel("待機")
          self._time_label = QLabel("00:00")
          self._progress = QProgressBar()
          self._progress.setMaximumHeight(6)
          self._progress.setTextVisible(False)
          layout = QHBoxLayout(self)
          layout.addWidget(self._state_label)
          layout.addWidget(self._time_label)
          layout.addWidget(self._progress, stretch=1)

      def update_snapshot(self, snap: TimerSnapshot, work_threshold_sec: float) -> None:
          self._state_label.setText(STATE_TEXT.get(snap.state, ""))
          elapsed = int(snap.work_elapsed_sec)
          self._time_label.setText(f"{elapsed // 60:02d}:{elapsed % 60:02d}")
          self._progress.setMaximum(max(1, int(work_threshold_sec)))
          self._progress.setValue(min(int(snap.work_elapsed_sec), int(work_threshold_sec)))
  ```

### 子元件：ConnectionBadge

- [ ] **3. 建立 `src/ui/widgets/connection_badge.py`**

  ```python
  from __future__ import annotations
  from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
  from src.app.connection_state import ConnectionState, severity, icon_key
  from src.ui.strings import CONN_TEXT

  # 簡單 Unicode 圖示作為文字圖示（確保不只靠顏色）
  _ICON_CHARS: dict[str, str] = {
      "conn-idle":        "○",
      "conn-connecting":  "◌",
      "conn-connected":   "●",
      "conn-reconnecting": "↻",
      "conn-no-signal":   "⊘",
      "conn-error":       "✕",
  }

  class ConnectionBadge(QWidget):
      def __init__(self, parent: QWidget | None = None) -> None:
          super().__init__(parent)
          self._icon_label = QLabel("○")
          self._text_label = QLabel("待機")
          layout = QHBoxLayout(self)
          layout.setContentsMargins(4, 2, 4, 2)
          layout.addWidget(self._icon_label)
          layout.addWidget(self._text_label)
          self._current_state = ConnectionState.IDLE

      def set_state(self, state: ConnectionState) -> None:
          self._current_state = state
          role = severity(state)
          text = CONN_TEXT.get(state, "")
          icon = _ICON_CHARS.get(icon_key(state), "?")
          self._icon_label.setText(icon)
          self._text_label.setText(text)
          for label in (self._icon_label, self._text_label):
              label.setProperty("role", role)
              label.style().unpolish(label)
              label.style().polish(label)
  ```

### 子元件：TodaySummaryView

- [ ] **4. 建立 `src/ui/widgets/today_summary_view.py`**

  ```python
  from __future__ import annotations
  from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
  from src.logging_store import TodaySummary
  from src.ui.strings import TODAY_EMPTY, TODAY_WORK_LABEL, TODAY_REST_LABEL

  class TodaySummaryView(QWidget):
      def __init__(self, parent: QWidget | None = None) -> None:
          super().__init__(parent)
          self._work_label = QLabel(TODAY_EMPTY)
          self._rest_label = QLabel("")
          layout = QHBoxLayout(self)
          layout.addWidget(self._work_label)
          layout.addWidget(self._rest_label)

      def set_summary(self, summary: TodaySummary | None) -> None:
          if summary is None or (summary.work_seconds == 0 and summary.rest_count == 0):
              self._work_label.setText(TODAY_EMPTY)
              self._rest_label.setText("")
              return
          mins = summary.work_seconds // 60
          self._work_label.setText(f"{TODAY_WORK_LABEL}：{mins} 分鐘")
          self._rest_label.setText(f"{TODAY_REST_LABEL}：{summary.rest_count} 次")
  ```

### 子元件：ActionBar

- [ ] **5. 建立 `src/ui/widgets/action_bar.py`**

  ```python
  from __future__ import annotations
  from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
  from PySide6.QtCore import Signal
  from src.ui.strings import ACTION_EDIT_ROI, ACTION_PAUSE, ACTION_RESUME, ACTION_SETTINGS

  class ActionBar(QWidget):
      edit_roi_toggled = Signal(bool)
      pause_toggled = Signal(bool)
      open_settings = Signal()

      def __init__(self, parent: QWidget | None = None) -> None:
          super().__init__(parent)
          self._roi_btn = QPushButton(ACTION_EDIT_ROI)
          self._roi_btn.setCheckable(True)
          self._pause_btn = QPushButton(ACTION_PAUSE)
          self._pause_btn.setCheckable(True)
          self._settings_btn = QPushButton(ACTION_SETTINGS)
          self._roi_btn.toggled.connect(self.edit_roi_toggled)
          self._pause_btn.toggled.connect(self._on_pause_toggled)
          self._settings_btn.clicked.connect(self.open_settings)
          layout = QHBoxLayout(self)
          layout.addWidget(self._roi_btn)
          layout.addWidget(self._pause_btn)
          layout.addStretch()
          layout.addWidget(self._settings_btn)

      def _on_pause_toggled(self, checked: bool) -> None:
          self._pause_btn.setText(ACTION_RESUME if checked else ACTION_PAUSE)
          self.pause_toggled.emit(checked)
  ```

### 組裝 MainWindow

- [ ] **6. 重構 `src/ui/main_window.py`：組合子元件**

  ```python
  from __future__ import annotations
  from PySide6.QtCore import Signal, QTimer
  from PySide6.QtGui import QCloseEvent
  from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout
  from src.config import AppConfig, save_config
  from src.ui.settings_schema import set_value
  from src.logging_store import SessionStore
  from src.types import BBox, Frame, TimerSnapshot
  from src.app.connection_state import ConnectionState, from_status
  from src.ui.widgets.preview_view import PreviewView
  from src.ui.widgets.status_strip import StatusStrip
  from src.ui.widgets.connection_badge import ConnectionBadge
  from src.ui.widgets.today_summary_view import TodaySummaryView
  from src.ui.widgets.action_bar import ActionBar

  class MainWindow(QMainWindow):
      roi_changed = Signal(object)      # BBox → worker.set_roi
      request_pause = Signal(bool)      # → worker.pause/resume
      request_settings = Signal()

      def __init__(
          self,
          config: AppConfig,
          store: SessionStore,
          config_path: str = "config.yaml",
      ) -> None:
          super().__init__()
          self._config = config
          self._store = store
          self._config_path = config_path
          self._work_threshold_sec = config.timer.work_threshold_min * 60.0
          self._build_ui()
          self._wire_internal()
          # 定時刷新今日彙總（30s）
          self._summary_timer = QTimer(self)
          self._summary_timer.setInterval(30_000)
          self._summary_timer.timeout.connect(self._refresh_summary)
          self._summary_timer.start()
          self._refresh_summary()

      def _build_ui(self) -> None:
          central = QWidget()
          self.setCentralWidget(central)
          self._preview = PreviewView()
          self._status = StatusStrip()
          self._badge = ConnectionBadge()
          self._summary = TodaySummaryView()
          self._actions = ActionBar()
          top_bar = QHBoxLayout()
          top_bar.addStretch()
          top_bar.addWidget(self._badge)
          main_layout = QVBoxLayout(central)
          main_layout.addLayout(top_bar)
          main_layout.addWidget(self._preview, stretch=1)
          main_layout.addWidget(self._status)
          middle = QHBoxLayout()
          middle.addWidget(self._summary, stretch=1)
          main_layout.addLayout(middle)
          main_layout.addWidget(self._actions)

      def _wire_internal(self) -> None:
          self._actions.edit_roi_toggled.connect(self._preview.set_edit_mode)
          self._actions.pause_toggled.connect(self.request_pause)
          self._actions.open_settings.connect(self.request_settings)
          self._preview.roi_committed.connect(self._on_roi_committed)

      def _refresh_summary(self) -> None:
          try:
              summary = self._store.today_summary()
              self._summary.set_summary(summary)
          except Exception:
              pass

      def _on_roi_committed(self, roi: BBox) -> None:
          updated = set_value(self._config, "presence.roi", roi)
          self._config = updated
          save_config(updated, self._config_path)
          self.roi_changed.emit(roi)

      # ── slots ─────────────────────────────────────────────────
      def on_frame_ready(self, frame: Frame) -> None:
          self._preview.set_frame(frame)

      def on_presence_changed(self, present: bool) -> None:
          pass  # 可用於未來狀態顯示

      def on_timer_updated(self, snap: TimerSnapshot) -> None:
          self._status.update_snapshot(snap, self._work_threshold_sec)

      def on_connection_status(self, status: str) -> None:
          state = from_status(status)
          self._badge.set_state(state)
          if state in (ConnectionState.NO_SIGNAL, ConnectionState.RECONNECTING, ConnectionState.CONNECTING):
              from src.ui.strings import CONN_TEXT
              self._preview.set_overlay_text(CONN_TEXT.get(state, ""))
          else:
              self._preview.set_overlay_text("")

      def on_failed(self, message: str) -> None:
          self._badge.set_state(ConnectionState.ERROR)
          self._preview.set_overlay_text(f"錯誤：{message}")

      def closeEvent(self, e: QCloseEvent) -> None:
          e.ignore()
          self.hide()
  ```

- [ ] **7. 建立 `src/ui/widgets/__init__.py`（空檔）**

- [ ] **8. 新增子元件測試到 `tests/test_ui.py`**

  ```python
  from src.types import TimerSnapshot, TimerState

  def test_status_strip_displays_state(qtbot):
      from src.ui.widgets.status_strip import StatusStrip
      strip = StatusStrip()
      qtbot.addWidget(strip)
      snap = TimerSnapshot(
          state=TimerState.WORKING,
          work_elapsed_sec=90.0,
          away_elapsed_sec=0.0,
          remaining_to_reminder_sec=2610.0,
          reminder_active=False,
      )
      strip.update_snapshot(snap, work_threshold_sec=2700.0)
      assert "工作中" in strip._state_label.text()
      assert "01:30" in strip._time_label.text()

  def test_connection_badge_has_text_and_icon(qtbot):
      from src.ui.widgets.connection_badge import ConnectionBadge
      from src.app.connection_state import ConnectionState
      badge = ConnectionBadge()
      qtbot.addWidget(badge)
      badge.set_state(ConnectionState.CONNECTED)
      assert badge._text_label.text() == "已連線"
      assert badge._icon_label.text() != ""  # 有圖示字元

  def test_today_summary_view_empty_state(qtbot):
      from src.ui.widgets.today_summary_view import TodaySummaryView
      from src.logging_store import TodaySummary
      from src.ui.strings import TODAY_EMPTY
      view = TodaySummaryView()
      qtbot.addWidget(view)
      view.set_summary(TodaySummary(0, 0, 0))
      assert TODAY_EMPTY in view._work_label.text()

  def test_preview_view_no_roi_in_non_edit_mode(qtbot):
      from src.ui.widgets.preview_view import PreviewView
      from src.types import BBox
      view = PreviewView()
      qtbot.addWidget(view)
      view.set_edit_mode(False)
      signals = []
      view.roi_committed.connect(signals.append)
      # 模擬拖曳 — 非編輯模式不應發出訊號
      from PySide6.QtCore import QPoint, Qt
      qtbot.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
      qtbot.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
      assert len(signals) == 0
  ```

- [ ] **9. 執行測試確認通過**

  ```bash
  rtk pytest tests/test_ui.py -k "status_strip or connection_badge or today_summary or preview" -v
  ```

- [ ] **10. Commit**

  ```bash
  rtk git add src/ui/widgets/ src/ui/main_window.py tests/test_ui.py
  rtk git commit -m "feat(M10): 重構主視窗，拆出子元件（PreviewView/StatusStrip/Badge等）"
  ```
