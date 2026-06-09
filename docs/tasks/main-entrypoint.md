# 模塊任務：`src/main.py`（修改）

> **對應需求**：FR-5（主執行緒 DB 連線關閉）、FR-6（StreamHealthMonitor 注入）  
> **詳細設計**：`docs/detailed-design.md` §4.12  
> **測試檔**：`tests/test_worker.py`（擴充）

---

## 任務清單

### 1. Worker 建立時注入或初始化 `StreamHealthMonitor`

- [ ] 確認 `StreamHealthMonitor` 在 worker 建立時可用（可在 worker 內部建立，或由 `main.py` 注入）
- [ ] 預設 `timeout_sec=10.0`（`DEFAULT_STREAM_TIMEOUT_SEC`）
- [ ] 確認 worker run loop 會使用此 monitor（見 `connection-state` 任務）

### 2. 修改 `aboutToQuit` 收尾程序

- [ ] 在 `_on_about_to_quit()` 中，worker 執行緒停止後，補上主執行緒關閉自己的 DB 連線：
  ```python
  def _on_about_to_quit() -> None:
      preview_timer.stop()
      grabber.stop()
      _shutdown_worker_thread(worker, thread)   # worker 執行緒 finally 會關自己的連線
      store.close()                              # ★ 主執行緒關自己的連線（FR-5）
  ```
- [ ] 確認順序：**先**停止 worker thread，**再**關主執行緒連線

### 3. 確認降噪函式已在啟動早期呼叫

- [ ] 確認 `logging_setup.suppress_decoder_noise()`（或等效函式）在 `main()` 的前幾行被呼叫
- [ ] 若已在第一行呼叫，標記此項為已完成，不需修改

### 4. 擴充單元測試（`tests/test_worker.py`）

- [ ] 使用假 store，驗證 worker run/stop 全流程不出現跨執行緒 `ProgrammingError`
- [ ] 假 store 記錄「哪個執行緒呼叫了 `close()`」，確認 worker 執行緒關自己、主執行緒關自己
- [ ] 執行 `rtk pytest tests/test_worker.py` 確認通過

---

## 驗收標準

- 程式正常關閉時，主執行緒與 worker 執行緒各自關閉自己的 DB 連線（AC-5.3）
- 背景不出現未處理例外（NFR-1）
- `StreamHealthMonitor` 已正確注入 worker（為 FR-6 完整整合的最後一步）
