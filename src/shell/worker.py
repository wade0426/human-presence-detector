"""偵測執行緒 worker（shell 層）：capture→detect→presence→core.tick→signal。

以舊 ``src/app/worker.py`` 為移植基底，全數保留：
- §4.2 影格新鮮度判定（timestamp 未前進＝凍結 → 走健康檢查分支、不餵偵測）；
- StreamHealthMonitor 接線（含低 FPS no-signal 寬限期）；
- FR-1.6 CUDA device fallback 通知（至多一次）；
- §4.8 logging_enabled、暫停 sleep 迴圈、request_* 指令佇列（執行緒安全）。

核心由 TimerEngine 換為 RestFlowMachine＋SessionTranslator＋RecordStore：
- 持久化：``translate(event)`` 結果非 None 才寫入；``logging_enabled=False``
  時 SessionRecord 與 LedgerEvent 都不寫。
- 雙時鐘設計：``clock``（預設 ``time.monotonic``）只推進狀態機——單調、
  不受 NTP 校時回撥影響（machine.tick 對時間倒退會 raise）；``wall_clock``
  （預設 ``time.time``）只用於落盤——RecordStore 的「今日」查詢以牆鐘
  epoch 篩選，monotonic 域時間戳永遠對不上（舊 worker 以 ``datetime.now()``
  落盤的行為等價移植）。
- 事件→訊號對映集中於單一 :meth:`DetectionWorker._emit_for`；
  REMINDER_REPEATED 會以最新工作時長重發 ``reminder_show``（FR-3）。
"""

from __future__ import annotations

import dataclasses
import threading
import time
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal

from src.capture.frame_grabber import FrameProvider
from src.capture.stream_health import (
    DEFAULT_NO_SIGNAL_GRACE_SEC,
    StreamHealth,
    StreamHealthMonitor,
)
from src.core.accounting import SessionTranslator
from src.core.events import Command, TimerEvent, TimerEventType
from src.shell.reminders.context import ReminderContext
from src.types import BBox

_STREAM_STATUS_MAP: dict[StreamHealth, str] = {
    StreamHealth.OK: "connected",
    StreamHealth.NO_SIGNAL: "no_signal",
    StreamHealth.TIMEOUT: "stream_error",
    StreamHealth.DISCONNECTED: "reconnecting",
}


class DetectionWorker(QObject):
    presence_changed = Signal(bool)
    timer_updated = Signal(object)      # TimerSnapshot
    reminder_show = Signal(object)      # ReminderContext
    reminder_repeat = Signal()
    return_prompt = Signal()
    lock_requested = Signal()
    # spec §5 stage 0：進入等待離席時播提示音一次的觸發源（quality review #1/#6）。
    rest_pending_entered = Signal()
    connection_status = Signal(str)
    failed = Signal(str)
    # FR-1.6：偵測端裝置 fallback（CUDA→CPU）發生時通知一次，參數為改用的裝置。
    device_fallback = Signal(str)

    def __init__(
        self,
        frames: FrameProvider,
        detector: Any,
        presence_evaluator: Any,
        machine: Any,
        store: Any,
        detection_interval_sec: float,
        reminder_context: ReminderContext,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        stream_health_monitor: StreamHealthMonitor | None = None,
        logging_enabled: bool = True,
    ) -> None:
        super().__init__()
        self._frames = frames
        self._detector = detector
        self._presence_evaluator = presence_evaluator
        self._machine = machine
        self._translator = SessionTranslator()
        self._store = store
        self._detection_interval_sec = detection_interval_sec
        self._reminder_context = reminder_context
        self._clock = clock
        self._wall_clock = wall_clock
        # §4.2：預設健康監視器帶 no-signal 寬限期——來源影格週期長於偵測輪詢
        # 間隔（低 FPS 子碼流）的健康串流，不得被間歇誤判為無訊號。
        self._stream_health = stream_health_monitor or StreamHealthMonitor(
            clock=clock,
            no_signal_after_sec=max(
                DEFAULT_NO_SIGNAL_GRACE_SEC, 2.0 * detection_interval_sec
            ),
        )
        self._logging_enabled = logging_enabled
        # §4.2: timestamp of the last frame actually processed; lets us tell a
        # fresh frame apart from a stale one left in the grabber after the
        # stream froze or disconnected.
        self._last_frame_ts: float | None = None
        # FR-1.6: device fallback is reported to the UI at most once.
        self._device_fallback_notified = False
        self._stop = False
        self._paused = False
        self._command_lock = threading.Lock()
        self._pending_start_rest = False
        self._pending_cancel_pending = False
        self._pending_confirm_return = False
        self._pending_pause = False
        self._pending_resume = False
        self._pending_notify_unlocked = False
        self._pending_roi: BBox | None = None

    # ── 主迴圈 ───────────────────────────────────────────────────────────────

    def run(self) -> None:
        try:
            self._store.init_schema()
            self.connection_status.emit("connecting")
            while not self._stop:
                self._drain_pending_commands()
                if self._paused:
                    time.sleep(0.1)
                    continue

                loop_start = self._clock()
                frame = self._frames.latest()
                now = self._clock()
                # §4.2: a frame is only "fresh" if its timestamp advanced past
                # the last processed one. A stale (frozen) frame must go down
                # the health-check branch — never into detection — so that a
                # broken stream cannot keep the presence state alive forever.
                if frame is None or frame.timestamp == self._last_frame_ts:
                    is_opened = self._frames.is_opened
                    health = self._stream_health.update(
                        has_frame=False, is_opened=is_opened, now=now
                    )
                    self.connection_status.emit(_STREAM_STATUS_MAP[health])
                    time.sleep(0.2)
                    continue

                self._last_frame_ts = frame.timestamp
                health = self._stream_health.update(
                    has_frame=True, is_opened=True, now=now
                )
                self.connection_status.emit(_STREAM_STATUS_MAP[health])
                detections = self._detector.detect(frame)
                self._notify_device_fallback_once()
                present = self._presence_evaluator.update(detections)
                self.presence_changed.emit(present)

                for event in self._machine.tick(present, self._clock()):
                    self._dispatch(event)

                self.timer_updated.emit(self._machine.snapshot(self._clock()))

                elapsed = self._clock() - loop_start
                if elapsed < self._detection_interval_sec:
                    time.sleep(self._detection_interval_sec - elapsed)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            close = getattr(self._store, "close", None)
            if callable(close):
                close()
            self._stop = True

    def stop(self) -> None:
        self._stop = True

    def _notify_device_fallback_once(self) -> None:
        """FR-1.6：偵測啟動後若發生裝置 fallback（CUDA→CPU），通知 UI 一次。"""
        if self._device_fallback_notified:
            return
        if getattr(self._detector, "device_fallback", False):
            self._device_fallback_notified = True
            self.device_fallback.emit("cpu")

    # ── 指令槽（任意執行緒呼叫；於 run 迴圈內生效）──────────────────────────

    def request_pause(self) -> None:
        with self._command_lock:
            self._pending_pause = True
            self._pending_resume = False

    def request_resume(self) -> None:
        with self._command_lock:
            self._pending_resume = True
            self._pending_pause = False

    def request_start_rest(self) -> None:
        with self._command_lock:
            self._pending_start_rest = True

    def request_cancel_pending(self) -> None:
        with self._command_lock:
            self._pending_cancel_pending = True

    def request_confirm_return(self) -> None:
        with self._command_lock:
            self._pending_confirm_return = True

    def request_notify_unlocked(self) -> None:
        """spec §5「鎖屏後回來」：工作階段解鎖 → 階梯歸零重計。"""
        with self._command_lock:
            self._pending_notify_unlocked = True

    def request_set_roi(self, roi: BBox) -> None:
        with self._command_lock:
            self._pending_roi = roi

    # ── 指令實作（worker 執行緒）─────────────────────────────────────────────

    def pause(self) -> None:
        now = self._clock()
        self._paused = True
        self._machine.pause(now)
        self.timer_updated.emit(self._machine.snapshot(now))

    def resume(self) -> None:
        now = self._clock()
        self._machine.resume(now)
        self._paused = False

    def start_rest(self) -> None:
        self._run_command(Command.START_REST)

    def cancel_pending(self) -> None:
        self._run_command(Command.CANCEL_PENDING)

    def confirm_return(self) -> None:
        self._run_command(Command.CONFIRM_RETURN)

    def notify_unlocked(self) -> None:
        """階梯歸零（core 保證鎖屏仍單一工作週期至多一次），並立即重發
        snapshot——覆蓋層隨之在 stage 0 重現、重新爬階。"""
        now = self._clock()
        self._machine.notify_unlocked(now)
        self.timer_updated.emit(self._machine.snapshot(now))

    def set_roi(self, roi: BBox) -> None:
        self._presence_evaluator.set_roi(roi)

    def _run_command(self, cmd: Command) -> None:
        now = self._clock()
        for event in self._machine.command(cmd, now):
            self._dispatch(event)
        self.timer_updated.emit(self._machine.snapshot(now))

    def _drain_pending_commands(self) -> None:
        with self._command_lock:
            pending_pause = self._pending_pause
            pending_resume = self._pending_resume
            pending_start_rest = self._pending_start_rest
            pending_cancel_pending = self._pending_cancel_pending
            pending_confirm_return = self._pending_confirm_return
            pending_notify_unlocked = self._pending_notify_unlocked
            pending_roi = self._pending_roi
            self._pending_pause = False
            self._pending_resume = False
            self._pending_start_rest = False
            self._pending_cancel_pending = False
            self._pending_confirm_return = False
            self._pending_notify_unlocked = False
            self._pending_roi = None

        if pending_roi is not None:
            self.set_roi(pending_roi)
        if pending_pause:
            self.pause()
        if pending_resume:
            self.resume()
            self.timer_updated.emit(self._machine.snapshot(self._clock()))
        if pending_start_rest:
            self.start_rest()
        if pending_cancel_pending:
            self.cancel_pending()
        if pending_confirm_return:
            self.confirm_return()
        if pending_notify_unlocked:
            self.notify_unlocked()

    # ── 事件處理：持久化＋訊號 ──────────────────────────────────────────────

    def _dispatch(self, event: TimerEvent) -> None:
        self._persist(event)
        self._emit_for(event)

    def _persist(self, event: TimerEvent) -> None:
        """§4.8：translate 結果非 None 才寫入；logging 停用即兩者都不寫。

        時鐘域轉換：``event.at`` 屬機器時鐘域（monotonic），translator 輸出
        的時間戳不能直接落盤——RecordStore 以牆鐘 epoch 篩「今日」。落盤
        前一律改以牆鐘錨定：end＝牆鐘現在、start＝現在−時長（事件於產生
        當下即 dispatch，誤差為單次迴圈內的毫秒級）。
        """
        if not self._logging_enabled:
            return
        record, ledger = self._translator.translate(event)
        if record is None and ledger is None:
            return
        wall_now = self._wall_clock()
        if record is not None:
            self._store.log_session(
                dataclasses.replace(
                    record,
                    start_ts=wall_now - record.duration_sec,
                    end_ts=wall_now,
                )
            )
        if ledger is not None:
            self._store.log_event(dataclasses.replace(ledger, ts=wall_now))

    def _emit_for(self, event: TimerEvent) -> None:
        """事件→訊號的單點對映（計畫 T8 鎖定介面）。

        FR-3：REMINDER_TRIGGERED 與 REMINDER_REPEATED 都注入「當下實際
        連續工作秒數」重發 ``reminder_show``——重複提醒不得重播首次觸發
        時快取的舊時長（舊 worker 於 REPEATED 重發 reminder_show 的行為
        等價移植）；REPEATED 另發無參數 ``reminder_repeat()``（鎖定介面）
        供重複專屬行為使用。

        REST_PENDING_ENTERED → ``rest_pending_entered()``：spec §5 stage 0
        的提示音觸發源。ESCALATED 刻意不設專屬訊號——覆蓋層幾何與階梯
        重複音效（EscalationSoundController）一律由 ``timer_updated`` 的
        snapshot（state＋escalation_stage）驅動，暫停/恢復與解鎖歸零都能
        自然收斂，毋須事件重放。
        """
        if event.type in (
            TimerEventType.REMINDER_TRIGGERED,
            TimerEventType.REMINDER_REPEATED,
        ):
            snap = self._machine.snapshot(self._clock())
            ctx = dataclasses.replace(
                self._reminder_context, work_elapsed_sec=snap.work_elapsed_sec
            )
            self.reminder_show.emit(ctx)
            if event.type is TimerEventType.REMINDER_REPEATED:
                self.reminder_repeat.emit()
        elif event.type is TimerEventType.REST_PENDING_ENTERED:
            self.rest_pending_entered.emit()
        elif event.type is TimerEventType.RETURN_PROMPT:
            self.return_prompt.emit()
        elif event.type is TimerEventType.LOCK_REQUESTED:
            self.lock_requested.emit()
