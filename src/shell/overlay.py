"""RestCoachOverlay — 休息教練覆蓋層（spec §5/§9/§10、plan T6）。

一律由 worker 的 ``timer_updated`` snapshot 驅動（不設 overlay 專用訊號）：

- 顯示條件：``state==REST_PENDING``（任何階段）或 ``REMINDING`` 且
  ``escalation_stage >= 1``；其他狀態（含 SUSPENDED）一律隱藏。
- 幾何型態：stage 0→小型角落視窗；1→放大置中；2→半透明全螢幕（主螢幕）；
  stage 3→自行隱藏——鎖屏將至，避免解鎖後殘留全螢幕遮罩（spec §10）。
- 按鈕依來源互斥：REST_PENDING 來源顯示「取消休息」（發 ``cancel_requested``）；
  REMINDING 來源沒有 pending 可取消，改顯示「開始休息（請離席）」（發
  ``start_rest_requested``）——全螢幕遮罩會擋住 popup 的開始休息鈕，覆蓋層
  必須自備同語意的善意出口（spec §5：按下即進 REST_PENDING、階梯歸零）。
- 滯留時長：兩來源皆直接讀 ``snapshot.escalation_dwell_sec``（REST_PENDING
  滯留與 REMINDING 超時共用同一計算、暫停凍結），不做本地估計。
- 鎖屏倒數：``lock_enabled`` 且 stage>=2 時顯示，剩餘 =
  ``stage_after_sec[2] - dwell``（無條件進位、不為負）。

視覺刻意固定深色、不隨 ThemeManager 明暗切換：全螢幕型態本就是黑色
半透明遮罩＋淺字，角落／置中卡片沿用同一深色面板，維持三型態一致的
教練視覺與對比（spec 決策 #9「沿用現有深色風格」）。背景由 ``paintEvent``
自繪（卡片／全螢幕遮罩），子標籤強制透明底——避免全域 QSS 的
``QWidget { background-color }`` 在半透明視窗裡畫出色塊。
"""

from __future__ import annotations

import math
from enum import Enum, auto

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from src.core.events import TimerSnapshot, TimerState
from src.duration_format import format_duration_zh
from src.shell import strings
from src.shell.theme import DARK_TOKENS

CORNER_SIZE = QSize(340, 190)
CENTER_SIZE = QSize(560, 300)

_LOCK_STAGE = 3
_LOCK_COUNTDOWN_STAGE = 2
_CORNER_MARGIN = 24
_QWIDGETSIZE_MAX = 16777215
_FALLBACK_GEOMETRY = QRect(0, 0, 800, 600)
_FULL_BACKDROP = QColor(0, 0, 0, 200)
_CARD_RADIUS = 12.0


class _Mode(Enum):
    CORNER = auto()
    CENTER = auto()
    FULL = auto()


# (title_pt, body_pt) — 型態越大字越大，全螢幕教練層用大字
_FONT_SIZES: dict[_Mode, tuple[int, int]] = {
    _Mode.CORNER: (13, 10),
    _Mode.CENTER: (18, 12),
    _Mode.FULL: (26, 15),
}


class RestCoachOverlay(QWidget):
    cancel_requested = Signal()
    start_rest_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # 刻意固定深色 tokens（不隨 ThemeManager 切換）——理由見模組 docstring
        self.setStyleSheet(
            f"QLabel {{ background: transparent; color: {DARK_TOKENS.text_primary}; }}"
        )

        self._mode: _Mode | None = None

        self.title_label = QLabel(strings.REST_PENDING_TITLE, self)
        self.body_label = QLabel(strings.REST_PENDING_BODY, self)
        self.body_label.setWordWrap(True)
        self.dwell_label = QLabel("", self)
        self.lock_label = QLabel("", self)
        self.cancel_button = QPushButton(strings.REST_PENDING_CANCEL, self)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.start_button = QPushButton(strings.REMIND_START_REST_PRESENCE, self)
        self.start_button.clicked.connect(self._on_start_rest_clicked)

        layout = QVBoxLayout(self)
        layout.addStretch(1)
        # label 不可用「佈局項對齊」加入：帶對齊的項走 Qt 的 alignedRect 路徑
        # ——寬度縮成 sizeHint、高度不問 heightForWidth，wordWrap 的副標會被
        # 配到單行高而上下裁切。改為填滿佈局寬、以 label 內部對齊置中。
        for label in (self.title_label, self.body_label, self.dwell_label, self.lock_label):
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(label)
        layout.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.start_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    # ── snapshot 驅動 ────────────────────────────────────────────────────────

    def update_from_snapshot(
        self,
        snapshot: TimerSnapshot,
        lock_enabled: bool,
        stage_after_sec: tuple[float, float, float],
    ) -> None:
        stage = snapshot.escalation_stage
        pending_source = snapshot.state is TimerState.REST_PENDING
        triggered = pending_source or (
            snapshot.state is TimerState.REMINDING and stage >= 1
        )
        if not triggered or stage >= _LOCK_STAGE:
            # 非觸發狀態，或鎖屏將至（stage 3）——先行隱藏，
            # 避免解鎖後殘留遮罩（spec §10）
            self._dismiss()
            return
        dwell = snapshot.escalation_dwell_sec

        self.cancel_button.setVisible(pending_source)
        self.start_button.setVisible(not pending_source)
        self.dwell_label.setText(
            strings.REST_PENDING_DWELL.format(duration=format_duration_zh(dwell))
        )
        show_lock = lock_enabled and stage >= _LOCK_COUNTDOWN_STAGE
        if show_lock:
            remaining = max(0, math.ceil(stage_after_sec[2] - dwell))
            self.lock_label.setText(strings.LOCK_COUNTDOWN.format(seconds=remaining))
        self.lock_label.setVisible(show_lock)

        self._apply_mode(self._mode_for_stage(stage))
        if not self.isVisible():
            self.show()
        self.raise_()
        self.update()

    # ── 內部 ─────────────────────────────────────────────────────────────────

    def _on_cancel_clicked(self) -> None:
        self.cancel_requested.emit()

    def _on_start_rest_clicked(self) -> None:
        self.start_rest_requested.emit()

    def _dismiss(self) -> None:
        self._mode = None
        self.hide()

    @staticmethod
    def _mode_for_stage(stage: int) -> _Mode:
        if stage >= 2:
            return _Mode.FULL
        if stage == 1:
            return _Mode.CENTER
        return _Mode.CORNER

    def _apply_mode(self, mode: _Mode) -> None:
        if mode is self._mode:
            return
        self._mode = mode
        screen = QApplication.primaryScreen()
        screen_geo = screen.geometry() if screen is not None else _FALLBACK_GEOMETRY
        available = screen.availableGeometry() if screen is not None else _FALLBACK_GEOMETRY
        self.setMinimumSize(0, 0)
        self.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
        if mode is _Mode.FULL:
            self.setGeometry(screen_geo)
        elif mode is _Mode.CENTER:
            self.setFixedSize(CENTER_SIZE)
            self.move(
                available.center().x() - CENTER_SIZE.width() // 2,
                available.center().y() - CENTER_SIZE.height() // 2,
            )
        else:
            self.setFixedSize(CORNER_SIZE)
            self.move(
                available.right() - CORNER_SIZE.width() - _CORNER_MARGIN,
                available.bottom() - CORNER_SIZE.height() - _CORNER_MARGIN,
            )
        self._apply_fonts(mode)

    def _apply_fonts(self, mode: _Mode) -> None:
        title_pt, body_pt = _FONT_SIZES[mode]
        title_font = self.title_label.font()
        title_font.setPointSize(title_pt)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        for label in (self.body_label, self.dwell_label, self.lock_label):
            font = label.font()
            font.setPointSize(body_pt)
            label.setFont(font)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if self._mode is _Mode.FULL:
            painter.fillRect(self.rect(), _FULL_BACKDROP)
        else:
            painter.setBrush(QColor(DARK_TOKENS.surface))
            painter.drawRoundedRect(self.rect(), _CARD_RADIUS, _CARD_RADIUS)
