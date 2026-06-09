# M8 `src/ui/theme.py` — 主題管理

**目標**：偵測 Windows 系統深 / 淺色、提供兩套語意 token 與 QSS、套用到 `QApplication`。

**涉及檔案**：
- 新增：`src/ui/theme.py`
- 新增：`tests/test_theme.py`

**相依**：`PySide6`（`QApplication`、`QStyleHints`）；登錄檔退路用標準庫 `winreg`。`ThemeTokens`/`build_qss` 部分為純邏輯。

---

## 任務清單

- [ ] **1. 建立 `src/ui/theme.py`，定義 `ColorScheme` 與 `ThemeTokens`**

  ```python
  from __future__ import annotations
  from dataclasses import dataclass
  from enum import Enum

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
  ```

- [ ] **2. 定義 `LIGHT_TOKENS` 與 `DARK_TOKENS`**

  ```python
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
  ```

- [ ] **3. 實作 `tokens_for()` 與 `build_qss()`**

  ```python
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
  """
  ```

- [ ] **4. 實作 `detect_scheme()`**

  ```python
  from PySide6.QtWidgets import QApplication
  from PySide6.QtCore import Qt

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
      # 退路：讀 Windows 登錄檔
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
  ```

- [ ] **5. 實作 `ThemeManager`**

  ```python
  class ThemeManager:
      def __init__(self, app: QApplication) -> None:
          self._app = app
          self._scheme: ColorScheme = ColorScheme.LIGHT

      def apply(self) -> None:
          self._scheme = detect_scheme(self._app)
          tokens = tokens_for(self._scheme)
          self._app.setStyleSheet(build_qss(tokens))

      def current(self) -> ColorScheme:
          return self._scheme

      def watch_system_changes(self) -> None:
          try:
              self._app.styleHints().colorSchemeChanged.connect(
                  lambda: self.apply()
              )
          except Exception:
              pass
  ```

- [ ] **6. 新增 `tests/test_theme.py`（純邏輯部分）**

  ```python
  from src.ui.theme import (
      ColorScheme, ThemeTokens, LIGHT_TOKENS, DARK_TOKENS,
      tokens_for, build_qss,
  )

  def test_tokens_for_returns_different_tokens():
      light = tokens_for(ColorScheme.LIGHT)
      dark = tokens_for(ColorScheme.DARK)
      assert light != dark
      assert light == LIGHT_TOKENS
      assert dark == DARK_TOKENS

  def test_build_qss_contains_token_colors():
      tokens = LIGHT_TOKENS
      qss = build_qss(tokens)
      assert tokens.bg in qss
      assert tokens.text_primary in qss
      assert tokens.accent in qss

  def test_build_qss_contains_role_selectors():
      qss = build_qss(LIGHT_TOKENS)
      assert '[role="danger"]' in qss
      assert '[role="secondary"]' in qss
  ```

- [ ] **7. 執行測試（純邏輯部分不需 Qt）**

  ```bash
  rtk pytest tests/test_theme.py -v
  ```

- [ ] **8. Commit**

  ```bash
  rtk git add src/ui/theme.py tests/test_theme.py
  rtk git commit -m "feat(M8): 新增主題管理模塊 theme.py（深/淺色 token + QSS）"
  ```
