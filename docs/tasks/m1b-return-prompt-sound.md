# M1b：「歡迎回來」對話框音效

> 對應需求：`docs/proposal.md` 需求一（FR-1.1～FR-1.6）
> 對應設計：`docs/detailed-design.md` §3.2
> 依賴模塊：[[m0-config]]（`ReturnSoundConfig`）、[[m1a-sound-player]]（`LoopingSoundPlayer`/`QtLoopingSoundPlayer`）
> 異動檔案：
> - 修改 `src/reminder/return_prompt.py`
> - 新增/擴充 `tests/test_return_sound.py`

---

## 任務清單

- [ ] **任務 1：擴充 `ReturnPromptDialog.__init__` 簽章（向後相容）**

  目前簽章（`src/reminder/return_prompt.py`）：

  ```python
  def __init__(self, parent: object = None) -> None:
  ```

  改為：

  ```python
  def __init__(
      self,
      *,
      return_sound: ReturnSoundConfig | None = None,
      player: LoopingSoundPlayer | None = None,
      parent: object = None,
  ) -> None:
      super().__init__()
      ...（既有 UI 建構不變）...
      self._return_sound = return_sound
      self._player: LoopingSoundPlayer = player if player is not None else QtLoopingSoundPlayer(self)
  ```

  新增 import：

  ```python
  from src.config import ReturnSoundConfig
  from src.reminder.sound import LoopingSoundPlayer, QtLoopingSoundPlayer
  ```

  **關鍵約束**：`ReturnPromptDialog()`（無任何參數）必須仍可建構成功——所有新參數皆為關鍵字參數且有預設值。`tests/test_reminder.py` 中既有的 `ReturnPromptDialog()` 呼叫不可破壞。

- [ ] **任務 2：`show_prompt()` 啟用時開始循環播放**

  在既有 `self.show()` 之後新增：

  ```python
  if self._return_sound is not None and self._return_sound.enabled:
      self._player.play(self._return_sound.sound_path)
  ```

- [ ] **任務 3：`_on_confirmed()` 停止播放**

  在 `confirmed.emit()` / `accept()` 之前（或之後皆可，但需確保一定執行到）新增：

  ```python
  self._player.stop()
  ```

- [ ] **任務 4：確認 `closeEvent()` 行為不變**

  `closeEvent()` 維持 `event.ignore()`，**不**呼叫 `player.stop()`（FR-1.3：對話框被忽略/失焦時音效不停止）。本任務僅需確認現有程式碼不需改動，並在任務 5 補上對應測試即可。

- [ ] **任務 5：撰寫測試（`tests/test_return_sound.py`，qt）**

  先建立測試用 `FakePlayer`（實作 `LoopingSoundPlayer` Protocol，記錄呼叫）：

  ```python
  class FakePlayer:
      def __init__(self) -> None:
          self.play_calls: list[str] = []
          self.stop_calls: int = 0

      def play(self, sound_path: str) -> None:
          self.play_calls.append(sound_path)

      def stop(self) -> None:
          self.stop_calls += 1
  ```

  測試案例：
  - `test_dialog_plays_when_enabled`：`ReturnSoundConfig(enabled=True, sound_path="x.mp3")` + `FakePlayer()` → `show_prompt()` 後 `fake.play_calls == ["x.mp3"]`。
  - `test_dialog_silent_when_disabled`：`ReturnSoundConfig(enabled=False, ...)`（或 `return_sound=None`）+ `FakePlayer()` → `show_prompt()` 後 `fake.play_calls == []`。
  - `test_dialog_stops_on_confirm`：建構帶 `enabled=True` 的 dialog，呼叫 `show_prompt()` 後觸發確認鈕（`qtbot.mouseClick` 或直接呼叫 `_on_confirmed()`），用 `qtbot.waitSignal(dialog.confirmed)` 確認訊號發出，並斷言 `fake.stop_calls >= 1`。
  - `test_dialog_close_does_not_stop`：`show_prompt()` 後呼叫 `dialog.close()`，斷言 `dialog.isVisible()` 仍為 `True` 且 `fake.stop_calls == 0`。
  - `test_dialog_backward_compatible_no_args`：`ReturnPromptDialog()`（無任何參數）可成功建構並呼叫 `show_prompt()`。

---

## 完成定義（Definition of Done）

- [ ] `ReturnPromptDialog` 新增 `return_sound`/`player` 關鍵字參數，預設值使既有無參數呼叫方式仍可用
- [ ] `show_prompt()`/`_on_confirmed()`/`closeEvent()` 行為符合 FR-1.1～FR-1.3
- [ ] 5 個新測試（含 `FakePlayer`）新增並通過
- [ ] `rtk pytest tests/test_return_sound.py tests/test_reminder.py` 全數通過（既有 `ReturnPromptDialog` 測試不受影響）
- [ ] `rtk pytest tests/test_main.py -k return_prompt` 通過（`tests/test_main.py:192` 既有的 `ReturnPromptDialog()` 用法）
- [ ] `rtk ruff check src/reminder/return_prompt.py` 無錯誤
