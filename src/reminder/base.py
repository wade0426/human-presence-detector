from __future__ import annotations

from typing import Protocol

from src.types import ReminderContext


class Reminder(Protocol):
    def show(self, ctx: ReminderContext) -> None: ...
    def hide(self) -> None: ...
