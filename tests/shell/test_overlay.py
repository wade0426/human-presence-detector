"""RestCoachOverlay（plan T6）：snapshot 驅動四型態幾何、按鈕訊號、stage3 自隱。

覆蓋層一律由 worker 的 timer_updated snapshot 驅動（無 overlay 專用訊號）：
- REST_PENDING（任何階段）或 REMINDING 且 escalation_stage>=1 → 顯示。
- stage 0→小型角落視窗；1→放大置中；2→半透明全螢幕；3→自行隱藏（鎖屏將至）。
- 取消鈕只在 REST_PENDING 來源顯示（REMINDING 不可取消）；REMINDING 來源
  改顯示「開始休息（請離席）」鈕（quality review #3：全螢幕遮罩擋住 popup
  的善意出口，覆蓋層需自備同語意按鈕）。
- 兩來源的滯留時長一律讀 snapshot.escalation_dwell_sec（quality review #8：
  取代舊的本地時鐘估計，暫停/隱藏後不再有一階寬度誤差）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.core.events import TimerSnapshot, TimerState
from src.shell import strings
from src.shell.overlay import CENTER_SIZE, CORNER_SIZE, RestCoachOverlay

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

STAGE_AFTER_SEC = (60.0, 120.0, 180.0)


def snap(
    state: TimerState,
    *,
    stage: int = 0,
    dwell: float = 0.0,
    overtime: float = 0.0,
) -> TimerSnapshot:
    return TimerSnapshot(
        state=state,
        work_elapsed_sec=0.0,
        away_elapsed_sec=0.0,
        remaining_to_reminder_sec=0.0,
        reminder_active=state is TimerState.REMINDING,
        rest_remaining_sec=0.0,
        rest_elapsed_sec=0.0,
        overtime_sec=overtime,
        pending_dwell_sec=dwell if state is TimerState.REST_PENDING else 0.0,
        escalation_stage=stage,
        escalation_dwell_sec=dwell,
    )


def update(
    overlay: RestCoachOverlay,
    snapshot: TimerSnapshot,
    *,
    lock_enabled: bool = True,
) -> None:
    overlay.update_from_snapshot(snapshot, lock_enabled, STAGE_AFTER_SEC)


@pytest.fixture
def overlay(qtbot: QtBot) -> RestCoachOverlay:
    widget = RestCoachOverlay()
    qtbot.addWidget(widget)
    return widget


# ── 顯示 / 隱藏判定 ──────────────────────────────────────────────────────────


def test_overlay_starts_hidden(overlay: RestCoachOverlay) -> None:
    assert not overlay.isVisible()


@pytest.mark.parametrize(
    "state",
    [
        TimerState.IDLE,
        TimerState.WORKING,
        TimerState.AWAY,
        TimerState.RESTING,
        TimerState.AWAITING_RETURN,
        TimerState.SUSPENDED,
    ],
)
def test_non_trigger_states_hide_overlay(overlay: RestCoachOverlay, state: TimerState) -> None:
    """非觸發狀態一律隱藏——即使 snapshot 仍帶著殘留的 stage 值。"""
    update(overlay, snap(TimerState.REST_PENDING, stage=0))
    assert overlay.isVisible()

    update(overlay, snap(state, stage=1))

    assert not overlay.isVisible()


def test_rest_pending_to_resting_sequence_hides(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REST_PENDING, stage=1, dwell=70.0))
    assert overlay.isVisible()

    update(overlay, snap(TimerState.RESTING, stage=-1))

    assert not overlay.isVisible()


def test_reminding_stage0_stays_hidden(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REMINDING, stage=0))

    assert not overlay.isVisible()


def test_reminding_without_escalation_stays_hidden(overlay: RestCoachOverlay) -> None:
    """apply_to_reminding=false 時 snapshot.escalation_stage == -1，不顯示。"""
    update(overlay, snap(TimerState.REMINDING, stage=-1))

    assert not overlay.isVisible()


# ── 四型態幾何 ───────────────────────────────────────────────────────────────


def test_stage0_shows_small_corner_window(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REST_PENDING, stage=0))

    assert overlay.isVisible()
    assert overlay.size() == CORNER_SIZE
    flags = overlay.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.WindowDoesNotAcceptFocus


def test_stage1_enlarges_and_centers(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REST_PENDING, stage=1, dwell=70.0))

    assert overlay.isVisible()
    assert overlay.size() == CENTER_SIZE
    assert CENTER_SIZE.width() > CORNER_SIZE.width()
    assert CENTER_SIZE.height() > CORNER_SIZE.height()
    screen = QApplication.primaryScreen()
    assert screen is not None
    center = screen.availableGeometry().center()
    got = overlay.frameGeometry().center()
    assert abs(got.x() - center.x()) <= 2
    assert abs(got.y() - center.y()) <= 2


def test_stage2_fullscreen_translucent(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REST_PENDING, stage=2, dwell=125.0))

    assert overlay.isVisible()
    screen = QApplication.primaryScreen()
    assert screen is not None
    assert overlay.geometry() == screen.geometry()
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def test_stage3_hides_itself_before_lock(overlay: RestCoachOverlay) -> None:
    """鎖屏前（stage 3 snapshot）自行隱藏（spec §10：避免解鎖後殘留遮罩）。"""
    update(overlay, snap(TimerState.REST_PENDING, stage=2, dwell=125.0))
    assert overlay.isVisible()

    update(overlay, snap(TimerState.REST_PENDING, stage=3, dwell=185.0))

    assert not overlay.isVisible()


def test_reminding_stage3_hides(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REMINDING, stage=2, overtime=130.0))
    assert overlay.isVisible()

    update(overlay, snap(TimerState.REMINDING, stage=3, overtime=185.0))

    assert not overlay.isVisible()


def test_geometry_returns_to_corner_after_fullscreen(overlay: RestCoachOverlay) -> None:
    """全螢幕後回到 stage 0（取消後重進）必須恢復小視窗尺寸。"""
    update(overlay, snap(TimerState.REST_PENDING, stage=2, dwell=125.0))
    update(overlay, snap(TimerState.REST_PENDING, stage=0))

    assert overlay.size() == CORNER_SIZE


# ── 取消鈕／開始休息鈕（來源互斥）────────────────────────────────────────────


def test_cancel_button_emits_cancel_requested(overlay: RestCoachOverlay, qtbot: QtBot) -> None:
    update(overlay, snap(TimerState.REST_PENDING, stage=0))
    assert overlay.cancel_button.isVisible()
    assert overlay.cancel_button.text() == strings.REST_PENDING_CANCEL

    with qtbot.waitSignal(overlay.cancel_requested, timeout=3000):
        qtbot.mouseClick(overlay.cancel_button, Qt.MouseButton.LeftButton)


def test_reminding_source_has_no_cancel_button(overlay: RestCoachOverlay) -> None:
    """REMINDING 來源沒有 pending 可取消——取消鈕必須隱藏。"""
    update(overlay, snap(TimerState.REMINDING, stage=1, dwell=70.0))

    assert overlay.isVisible()
    assert not overlay.cancel_button.isVisible()


def test_reminding_source_shows_start_rest_button(
    overlay: RestCoachOverlay, qtbot: QtBot
) -> None:
    """REMINDING 來源（含全螢幕型態）必須提供「開始休息（請離席）」善意出口
    （quality review #3：覆蓋層擋住 popup 的開始休息鈕）。"""
    update(overlay, snap(TimerState.REMINDING, stage=2, dwell=125.0))

    assert overlay.isVisible()
    assert overlay.start_button.isVisible()
    assert overlay.start_button.text() == strings.REMIND_START_REST_PRESENCE

    with qtbot.waitSignal(overlay.start_rest_requested, timeout=3000):
        qtbot.mouseClick(overlay.start_button, Qt.MouseButton.LeftButton)


def test_rest_pending_source_hides_start_rest_button(overlay: RestCoachOverlay) -> None:
    """REST_PENDING 來源已在等待離席——只保留取消鈕。"""
    update(overlay, snap(TimerState.REST_PENDING, stage=1, dwell=70.0))

    assert overlay.cancel_button.isVisible()
    assert not overlay.start_button.isVisible()


# ── 文字內容 ─────────────────────────────────────────────────────────────────


def test_static_texts_use_strings_constants(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REST_PENDING, stage=0))

    assert overlay.title_label.text() == strings.REST_PENDING_TITLE
    assert overlay.body_label.text() == strings.REST_PENDING_BODY


def test_dwell_label_formats_pending_dwell(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REST_PENDING, stage=1, dwell=90.0))

    assert overlay.dwell_label.text() == strings.REST_PENDING_DWELL.format(duration="1 分 30 秒")


# ── REMINDING 來源 dwell（snapshot.escalation_dwell_sec）────────────────────
#
# quality review #8：TimerSnapshot 增加通用階梯 dwell 欄位後，兩來源皆直接
# 讀 snapshot，舊的本地時鐘估計（暫停/隱藏後誤差可達一階寬度）整段移除。
# overtime_sec 在「取消回 REMINDING（work 記帳）」與「休息中斷 remind」兩條
# 路徑與階梯 dwell 嚴重偏離，仍不可充當（quality review T6 #1 回歸）。


def test_reminding_dwell_reads_snapshot_escalation_dwell(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REMINDING, stage=1, dwell=70.0))

    assert overlay.dwell_label.text() == strings.REST_PENDING_DWELL.format(duration="1 分 10 秒")


def test_reminding_dwell_ignores_inflated_overtime(overlay: RestCoachOverlay) -> None:
    """取消回 REMINDING（work 記帳）：overtime 含整段 pending 滯留、遠大於 dwell。"""
    update(overlay, snap(TimerState.REMINDING, stage=1, dwell=60.0, overtime=400.0))

    assert overlay.dwell_label.text() == strings.REST_PENDING_DWELL.format(duration="1 分鐘")


def test_reminding_lock_countdown_follows_snapshot_dwell(overlay: RestCoachOverlay) -> None:
    """REMINDING 來源倒數隨 snapshot dwell 遞減。"""
    update(overlay, snap(TimerState.REMINDING, stage=2, dwell=120.0))
    assert overlay.lock_label.text() == strings.LOCK_COUNTDOWN.format(seconds=60)

    update(overlay, snap(TimerState.REMINDING, stage=2, dwell=145.0))
    assert overlay.lock_label.text() == strings.LOCK_COUNTDOWN.format(seconds=35)


def test_reminding_dwell_survives_suspend_resume(overlay: RestCoachOverlay) -> None:
    """暫停（SUSPENDED 隱藏）後恢復：dwell 直接取 snapshot——不再錨回階段下界。"""
    update(overlay, snap(TimerState.REMINDING, stage=1, dwell=70.0))
    update(overlay, snap(TimerState.SUSPENDED, stage=1, dwell=70.0))
    assert not overlay.isVisible()

    update(overlay, snap(TimerState.REMINDING, stage=1, dwell=95.0))

    assert overlay.dwell_label.text() == strings.REST_PENDING_DWELL.format(duration="1 分 35 秒")


def test_rest_pending_after_reminding_uses_pending_dwell(overlay: RestCoachOverlay) -> None:
    """REMINDING→REST_PENDING（按下開始休息）：階梯歸零後 dwell 自 0 重計。"""
    update(overlay, snap(TimerState.REMINDING, stage=1, dwell=70.0))
    update(overlay, snap(TimerState.REST_PENDING, stage=0, dwell=5.0))

    assert overlay.dwell_label.text() == strings.REST_PENDING_DWELL.format(duration="5 秒")


# ── 文字不得裁切（佈局回歸）──────────────────────────────────────────────────
#
# bug 回歸：wordWrap QLabel 以「佈局項對齊」加入 QVBoxLayout 時，Qt 走
# alignedRect 路徑——寬度縮成 sizeHint、高度不問 heightForWidth，副標在三種
# 型態都被配到單行高，兩行文字上下各裁一半（實機截圖重現）。約束：label
# 必須填滿佈局內容寬，且高度足夠容納該寬度下的換行文字。


@pytest.mark.parametrize(("stage", "dwell"), [(0, 5.0), (1, 70.0), (2, 125.0)])
def test_body_label_fills_width_and_height_fits_text(
    overlay: RestCoachOverlay, stage: int, dwell: float
) -> None:
    update(overlay, snap(TimerState.REST_PENDING, stage=stage, dwell=dwell))
    QApplication.processEvents()

    body = overlay.body_label
    layout = overlay.layout()
    assert layout is not None
    margins = layout.contentsMargins()
    expected_width = overlay.width() - margins.left() - margins.right()
    assert body.width() == expected_width
    assert body.height() >= body.heightForWidth(body.width())


# ── 鎖屏倒數 ─────────────────────────────────────────────────────────────────


def test_lock_countdown_visible_at_stage2_when_lock_enabled(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REST_PENDING, stage=2, dwell=130.0), lock_enabled=True)

    assert overlay.lock_label.isVisible()
    assert overlay.lock_label.text() == strings.LOCK_COUNTDOWN.format(seconds=50)


def test_lock_countdown_hidden_when_lock_disabled(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REST_PENDING, stage=2, dwell=130.0), lock_enabled=False)

    assert overlay.isVisible()
    assert not overlay.lock_label.isVisible()


def test_lock_countdown_hidden_below_stage2(overlay: RestCoachOverlay) -> None:
    update(overlay, snap(TimerState.REST_PENDING, stage=1, dwell=70.0), lock_enabled=True)

    assert not overlay.lock_label.isVisible()
