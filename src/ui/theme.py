from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


class ColorScheme(Enum):
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class ThemeTokens:
    bg: str
    surface: str
    border: str
    text_primary: str
    text_secondary: str
    accent: str
    success: str
    warning: str
    danger: str
    info: str


LIGHT_TOKENS = ThemeTokens(
    bg="#F5F5F5",
    surface="#FFFFFF",
    border="#E0E0E0",
    text_primary="#1A1A1A",
    text_secondary="#6B6B6B",
    accent="#007AFF",
    success="#34C759",
    warning="#FF9500",
    danger="#FF3B30",
    info="#5AC8FA",
)

DARK_TOKENS = ThemeTokens(
    bg="#1C1C1E",
    surface="#2C2C2E",
    border="#3A3A3C",
    text_primary="#F2F2F7",
    text_secondary="#8E8E93",
    accent="#0A84FF",
    success="#30D158",
    warning="#FF9F0A",
    danger="#FF453A",
    info="#64D2FF",
)


def tokens_for(scheme: ColorScheme) -> ThemeTokens:
    return DARK_TOKENS if scheme == ColorScheme.DARK else LIGHT_TOKENS


def build_qss(tokens: ThemeTokens) -> str:
    return f"""
QWidget {{
    background-color: {tokens.bg};
    color: {tokens.text_primary};
}}
QDialog, QMainWindow {{
    background-color: {tokens.bg};
}}
QLabel[role="secondary"] {{
    color: {tokens.text_secondary};
    font-size: 11px;
}}
QLabel[role="muted"] {{
    color: {tokens.text_secondary};
}}
QLabel[role="danger"] {{
    color: {tokens.danger};
}}
QWidget[role="danger"] {{
    color: {tokens.danger};
}}
QWidget[role="warning"] {{
    color: {tokens.warning};
}}
QWidget[role="success"] {{
    color: {tokens.success};
}}
QWidget[role="info"] {{
    color: {tokens.info};
}}
QListWidget, QStackedWidget {{
    background-color: {tokens.surface};
    border: 1px solid {tokens.border};
}}
QPushButton {{
    background-color: {tokens.accent};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton:hover {{
    background-color: {tokens.accent};
    opacity: 0.85;
}}
QProgressBar {{
    border: 1px solid {tokens.border};
    border-radius: 4px;
    background-color: {tokens.surface};
}}
QProgressBar::chunk {{
    background-color: {tokens.accent};
    border-radius: 3px;
}}
QPushButton:checked {{
    background-color: {tokens.accent};
    border: 2px solid {tokens.border};
    font-weight: bold;
}}
QPushButton[role="danger"] {{
    background-color: {tokens.danger};
    color: #FFFFFF;
}}
QPushButton[role="danger"]:hover {{
    background-color: {tokens.danger};
    opacity: 0.85;
}}
"""


def detect_scheme(app: QApplication) -> ColorScheme:
    try:
        hints = app.styleHints()
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return ColorScheme.DARK
        if scheme == Qt.ColorScheme.Light:
            return ColorScheme.LIGHT
    except Exception:
        pass

    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return ColorScheme.LIGHT if value else ColorScheme.DARK
    except Exception:
        return ColorScheme.LIGHT


class ThemeManager:
    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._scheme = ColorScheme.LIGHT

    def apply(self) -> None:
        self._scheme = detect_scheme(self._app)
        self._app.setStyleSheet(build_qss(tokens_for(self._scheme)))

    def current(self) -> ColorScheme:
        return self._scheme

    def watch_system_changes(self) -> None:
        with suppress(Exception):
            self._app.styleHints().colorSchemeChanged.connect(lambda: self.apply())
