# M1a：循環音效播放器

> 對應需求：`docs/proposal.md` 需求一（FR-1.2、FR-1.6）
> 對應設計：`docs/detailed-design.md` §3.1
> 依賴模塊：無（M1b 依賴本模塊）
> 異動檔案：
> - 新增 `src/reminder/sound.py`
> - 新增 `tests/test_return_sound.py`

---

## 任務清單

- [ ] **任務 1：建立 `LoopingSoundPlayer` Protocol 與 `QtLoopingSoundPlayer` 實作**

  新增 `src/reminder/sound.py`：

  ```python
  from __future__ import annotations

  from typing import Protocol

  from PySide6.QtCore import QObject
  from PySide6.QtMultimedia import QSoundEffect

  from src.reminder.media import safe_sound_url


  class LoopingSoundPlayer(Protocol):
      def play(self, sound_path: str) -> None: ...   # 啟動循環播放；路徑無效則安靜略過
      def stop(self) -> None: ...                     # 停止播放（可重複呼叫）


  class QtLoopingSoundPlayer:
      def __init__(self, parent: QObject | None = None) -> None:
          self._effect = QSoundEffect(parent)
          self._effect.setLoopCount(QSoundEffect.Infinite)

      def play(self, sound_path: str) -> None:
          url = safe_sound_url(sound_path)
          if url is None:
              return
          self._effect.setSource(url)
          self._effect.play()

      def stop(self) -> None:
          self._effect.stop()
  ```

  說明：
  - `QSoundEffect` 用法與 `src/reminder/popup.py` 既有的 `self._sound_effect = QSoundEffect(self)` 一致。
  - `safe_sound_url()`（`src/reminder/media.py`）對不存在/空路徑回傳 `None`，由 `play()` 接手做容錯（FR-1.6：路徑無效時不播放、不崩潰）。
  - `stop()` 任何狀態下皆可安全呼叫（`QSoundEffect.stop()` 對未播放狀態是 no-op）。

- [ ] **任務 2：容錯測試**

  新增 `tests/test_return_sound.py`（`@pytest.mark.qt`，沿用 `tests/conftest.py` 的 `QT_QPA_PLATFORM=offscreen`）：

  - `test_qt_player_play_missing_path_no_crash`：對不存在路徑（如 `"not/exist.mp3"`）呼叫 `QtLoopingSoundPlayer().play(...)`，斷言不丟例外。
  - `test_qt_player_stop_before_play_no_crash`：未呼叫 `play()` 即呼叫 `stop()`，斷言不丟例外。

  > 不對「是否真的發聲」做斷言（offscreen / CI 無音訊裝置）。本檔後續會在 M1b 任務中繼續擴充（對話框邏輯改用 fake player）。

---

## 完成定義（Definition of Done）

- [ ] `src/reminder/sound.py` 新增，`LoopingSoundPlayer`／`QtLoopingSoundPlayer` 介面與簽章與設計文件一致
- [ ] 兩個容錯測試新增並通過
- [ ] `rtk pytest tests/test_return_sound.py` 通過
- [ ] `rtk ruff check src/reminder/sound.py` 無錯誤
- [ ] `rtk mypy src/reminder/sound.py` 無錯誤
