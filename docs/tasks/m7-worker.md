# M7 `src/app/worker.py` — 豐富連線狀態

**目標**：擴充 `connection_status` 的詞彙，加入 `"connecting"` 與 `"no_signal"` 兩個新狀態。

**涉及檔案**：
- 修改：`src/app/worker.py`
- 修改：`tests/test_worker.py`

**相依**：既有相依不變；M4 `from_status()` 由 UI 端使用，worker 只發字串。

> **嚴禁**：不更動偵測 / 在場 / 計時任何邏輯與呼叫。

---

## 任務清單

- [ ] **1. 在 `worker.run()` 開頭加入 `"connecting"` 發射**

  在 `run()` 的 `try:` 區塊最前面，`self._store.init_schema()` **之後**加入：
  ```python
  self.connection_status.emit("connecting")
  ```

- [ ] **2. 更新讀格時的狀態映射**

  找到目前的讀格結果判斷區塊（`frame is None` 時 emit `"reconnecting"`），改為：
  ```python
  frame = self._source.read()
  if frame is None:
      is_opened = getattr(self._source, "is_opened", False)
      if is_opened:
          self.connection_status.emit("no_signal")
      else:
          self.connection_status.emit("reconnecting")
      time.sleep(0.2)
      continue
  ```

  > `ReconnectingSource` 既有 `is_opened` 屬性；此處用 `getattr` 加預設值以相容假件。

- [ ] **3. 新增測試到 `tests/test_worker.py`**

  參考既有假件風格，新增：
  ```python
  def test_worker_emits_connecting_at_start(qtbot):
      """run() 開始後立刻發出 connecting 狀態。"""
      statuses = []
      source = FakeSource(frames=[None])      # 立即無幀以結束迴圈
      source.is_opened = False
      worker = make_worker(source)
      worker.connection_status.connect(statuses.append)
      # 執行一個迴圈迭代
      _run_one_iteration(worker)
      assert statuses[0] == "connecting"

  def test_worker_emits_no_signal_when_source_open_but_no_frame(qtbot):
      """source 已開啟但 read() 回傳 None → 發 no_signal。"""
      statuses = []
      source = FakeSource(frames=[None])
      source.is_opened = True
      worker = make_worker(source)
      worker.connection_status.connect(statuses.append)
      _run_one_iteration(worker)
      assert "no_signal" in statuses

  def test_worker_emits_reconnecting_when_source_closed(qtbot):
      """source 未開啟且 read() 回傳 None → 發 reconnecting。"""
      statuses = []
      source = FakeSource(frames=[None])
      source.is_opened = False
      worker = make_worker(source)
      worker.connection_status.connect(statuses.append)
      _run_one_iteration(worker)
      assert "reconnecting" in statuses
  ```

  > `FakeSource`、`make_worker`、`_run_one_iteration` 請依既有 `test_worker.py` 的假件模式調整；若不存在則需建立簡單假件。

- [ ] **4. 確認既有 `test_worker.py` 測試全部通過**

  ```bash
  rtk pytest tests/test_worker.py -v
  ```

- [ ] **5. Commit**

  ```bash
  rtk git add src/app/worker.py tests/test_worker.py
  rtk git commit -m "feat(M7): worker 新增 connecting/no_signal 連線狀態"
  ```
