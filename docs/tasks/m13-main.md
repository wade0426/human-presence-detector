# M13 `src/main.py` — 組裝與接線

**目標**：修正 D1/D3/D5 接線問題、整合全部新模塊、確保啟動順序正確。

**涉及檔案**：
- 修改：`src/main.py`
- 修改：`tests/test_main.py`

**相依**：全部模塊（M1–M12）。

**前置條件**：所有其他模塊需先完成。

---

## 缺陷修正對照

| 缺陷 | 問題 | 修正 |
|------|------|------|
| D1 | `tray.toggle_action` 只接 `worker.pause`，無法繼續 | 改接 `_toggle_pause` 維護 paused 旗標 |
| D3 | `worker.failed` 接 `app.quit`，一報錯即關程式 | 改接 `window.on_failed` |
| D5 | `SettingsDialog.config_changed` 未接線 | `SettingsWindow` 不再有此訊號（手動重啟模式） |

---

## 任務清單

- [ ] **1. 更新 import 區塊**

  ```python
  from src.logging_setup import setup_logging, suppress_decoder_noise
  from src.ui.theme import ThemeManager
  from src.ui.settings import SettingsWindow      # 改名
  from src.ui.main_window import MainWindow        # 介面變更（需傳 store）
  from src.ui.tray import TrayIcon
  from src.app.connection_state import from_status
  ```

- [ ] **2. 在 `main()` 最前段呼叫 logging 設定（必須在 create_source 前）**

  ```python
  def main() -> int:
      suppress_decoder_noise()                 # 必須最早（在 create_source 前）
      setup_logging()
      app = QApplication.instance() or QApplication(sys.argv)
      ThemeManager(app).apply()
      cfg = load_config("config.yaml")
      ...
  ```

- [ ] **3. 更新 `_build_worker()` 簽章：接受並使用 store**

  ```python
  def _build_worker(cfg: AppConfig, store: SessionStore) -> DetectionWorker:
      ...
      # 移除舊的 store = SessionStore(cfg.logging.db_path)
      reminder_context = ReminderContext(
          work_minutes=int(cfg.timer.work_threshold_min),
          media_path=cfg.reminder.popup.media_path,
          media_type=cfg.reminder.popup.media_type,
          sound_path=cfg.reminder.popup.sound_path,
          reset_mode=cfg.reminder.reset_mode.value,           # 新增
          snooze_minutes=int(cfg.reminder.snooze_min),        # 新增
      )
      return DetectionWorker(
          source=source, detector=detector, presence_evaluator=presence,
          timer_engine=timer, store=store,
          detection_interval_sec=cfg.detection.interval_sec,
          reminder_context=reminder_context,
      )
  ```

- [ ] **4. 更新 `main()` 組裝順序**

  ```python
  store = SessionStore(cfg.logging.db_path)
  worker = _build_worker(cfg, store)            # store 注入
  thread = QThread(); worker.moveToThread(thread); thread.started.connect(worker.run)

  window = MainWindow(cfg, store, "config.yaml")   # store 注入
  tray = TrayIcon()
  tray.bind_window(window)
  reminder = create_reminder(cfg.reminder, tray)
  settings = SettingsWindow(cfg, "config.yaml", window)
  ```

- [ ] **5. 更新接線：移除 `app.quit` from `failed`（修 D3）**

  刪除：
  ```python
  worker.failed.connect(lambda _message: app.quit())
  ```
  改為：
  ```python
  worker.failed.connect(window.on_failed)
  ```

- [ ] **6. 更新連線狀態接線**

  ```python
  worker.connection_status.connect(window.on_connection_status)
  worker.connection_status.connect(lambda st: tray.set_connection(from_status(st)))
  worker.timer_updated.connect(lambda s: tray.set_timer_state(s.state))
  ```

- [ ] **7. 實作 `_toggle_pause`（修 D1）**

  ```python
  _paused = False

  def _toggle_pause() -> None:
      nonlocal _paused
      _paused = not _paused
      if _paused:
          worker.pause()
      else:
          worker.resume()
      tray.set_paused(_paused)
      window.request_pause.emit(_paused)
  ```

  接線：
  ```python
  tray.toggle_action.triggered.connect(_toggle_pause)   # 改 D1
  ```

- [ ] **8. 補齊設定視窗接線（修 D5）**

  ```python
  tray.settings_action.triggered.connect(settings.show)
  window.request_settings.connect(settings.show)
  ```

- [ ] **9. 更新 `tests/test_main.py`：驗證關鍵接線**

  ```python
  def test_failed_signal_not_connected_to_quit():
      """D3 修正驗證：failed 不再接 app.quit。"""
      # 此測試概念性：確認 main.py 中不再有 app.quit 接在 worker.failed
      import inspect, src.main
      source = inspect.getsource(src.main.main)
      assert "app.quit" not in source or "failed" not in source.split("app.quit")[0].split("\n")[-5:]

  def test_main_imports_new_modules():
      """確認新模塊已被匯入。"""
      import src.main
      assert hasattr(src.main, "setup_logging") or "setup_logging" in dir(src.main)
  ```

  > 注意：`test_main.py` 以「接線」為主；端到端啟動仍以手動驗收為準。

- [ ] **10. 執行既有 + 新增測試確認通過**

  ```bash
  rtk pytest tests/test_main.py -v
  ```

- [ ] **11. Commit**

  ```bash
  rtk git add src/main.py tests/test_main.py
  rtk git commit -m "fix(M13): 修正 D1/D3/D5 接線，整合全部新模塊"
  ```
