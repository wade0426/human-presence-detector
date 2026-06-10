from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.config import AppConfig, save_config
from src.logging_store import SessionStore


class ClearScope(Enum):
    TODAY = "today"
    ALL = "all"
    ALL_AND_RESET = "all_and_reset"


@dataclass(frozen=True)
class ClearResult:
    deleted: int
    reset_config: bool


class ClearDataService:
    def __init__(self, store: SessionStore, config_path: str) -> None:
        self._store = store
        self._config_path = config_path

    def clear(self, scope: ClearScope) -> ClearResult:
        if scope is ClearScope.TODAY:
            deleted = self._store.clear_today()
            return ClearResult(deleted=deleted, reset_config=False)

        if scope is ClearScope.ALL:
            deleted = self._store.clear_all()
            return ClearResult(deleted=deleted, reset_config=False)

        # ClearScope.ALL_AND_RESET
        deleted = self._store.clear_all()
        save_config(AppConfig(), self._config_path)
        return ClearResult(deleted=deleted, reset_config=True)
