from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject

from src.app import screen_lock
from src.app.force_lock import ForceLockPolicy
from src.config import ForceLockConfig
from src.types import TimerSnapshot
from src.ui.force_lock_window import ForceLockCountdownWindow


class ForceLockController(QObject):
    def __init__(
        self,
        config: ForceLockConfig,
        *,
        lock_fn: Callable[[], bool] = screen_lock.lock_screen,
        window_factory: Callable[[int, bool], ForceLockCountdownWindow] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._policy = ForceLockPolicy(config)
        self._lock_fn = lock_fn
        self._window_factory = window_factory or ForceLockCountdownWindow
        self._countdown_window: ForceLockCountdownWindow | None = None

    def on_timer_updated(self, snap: TimerSnapshot) -> None:
        if self._policy.observe(snap):
            self._begin_lock_flow()

    def _begin_lock_flow(self) -> None:
        mode = self._config.warning_mode
        if mode == "immediate":
            self._lock_fn()
            return

        cancellable = mode == "countdown_cancel"
        win = self._window_factory(self._config.countdown_sec, cancellable)
        win.expired.connect(self._on_countdown_expired)
        win.cancelled.connect(self._on_countdown_cancelled)
        self._countdown_window = win
        win.start()

    def _on_countdown_expired(self) -> None:
        self._countdown_window = None
        self._lock_fn()

    def _on_countdown_cancelled(self) -> None:
        self._countdown_window = None
