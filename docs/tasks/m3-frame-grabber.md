# M3 影像擷取

**涉及檔案**：
- 修改：`src/capture/video_source.py`
- 新增：`src/capture/frame_grabber.py`
- 新增：`tests/test_frame_grabber.py`

**相依**：M1（`Frame` 型別）

---

## 任務清單

### FrameProvider Protocol（`src/capture/frame_grabber.py` 或 `src/types.py`）

- [ ] 定義 `class FrameProvider(Protocol)`：
  - `def latest(self) -> Frame | None: ...`
  - `@property def is_opened(self) -> bool: ...`

### RTSPSource 最小緩衝（`src/capture/video_source.py`）

- [ ] 在 `RTSPSource.open()` 開啟攝影機後加 `self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)`

### FrameGrabber 類別（`src/capture/frame_grabber.py`）

- [ ] 定義 `class FrameGrabber` 實作 `FrameProvider`
- [ ] `__init__(self, source: VideoSource, clock=time.monotonic)`：初始化 `_lock`、`_latest = None`、`_running = False`
- [ ] `start()`：建立並啟動背景 `threading.Thread`（daemon=True），執行 `_grab_loop`
- [ ] `_grab_loop()`：迴圈讀取 `source.read()`；以 `with self._lock: self._latest = frame` 原子替換；`source.read()` 回 None 時短暫 sleep 避免空轉
- [ ] `stop()`：設 `_running = False`；`join` 執行緒；呼叫 `source.release()`；清 `_latest = None`
- [ ] `latest()`：以 `with self._lock: return self._latest`（執行緒安全）
- [ ] `is_opened` property：委派給 `source.is_opened`

---

## 單元測試（`tests/test_frame_grabber.py`）

使用 `FakeSource`（回傳預排影格序列，不開實體攝影機）。

- [ ] 測試 1：`start()` 後 `latest()` 回傳最後放入的影格（驗證「保留最新、丟棄舊格」）
- [ ] 測試 2：source 回傳 `None` 時 `latest()` 不拋例外（回傳前一張或 None）；`is_opened` 正確委派
- [ ] 測試 3：`stop()` 後執行緒結束（`thread.is_alive() == False`）、`source.release()` 被呼叫恰好一次、`latest()` 回 None
- [ ] 測試 4：多執行緒同時呼叫 `latest()` 不拋例外（以 `threading.Thread` 並發壓測）

---

## 驗收

- [ ] `rtk pytest tests/test_frame_grabber.py -v` 全通過
- [ ] （手動）RTSP 來源下預覽延遲明顯下降、破圖減少（列入手動驗收）
