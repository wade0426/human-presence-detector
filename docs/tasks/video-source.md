# 影像來源 `capture/video_source.py`

> **對應檔案**：`src/capture/video_source.py`、`tests/test_video_source.py`  
> **前置條件**：[[types]]、[[config]]  
> **相依**：`opencv-python`（`cv2.VideoCapture`）、`src.types.Frame`、`src.config.SourceConfig`

## 任務

- [ ] **VS1** 建立 `src/capture/video_source.py`，定義 `VideoSource` Protocol 介面：
  ```python
  class VideoSource(Protocol):
      def open(self) -> None: ...
      def read(self) -> Optional[Frame]: ...
      def release(self) -> None: ...
      @property
      def is_opened(self) -> bool: ...
  ```

- [ ] **VS2** 實作 `WebcamSource`：
  - `__init__(self, index: int)`，建立但**不開啟** `cv2.VideoCapture`
  - `open()`：`cv2.VideoCapture(index)`
  - `read()`：`cap.read()` 失敗回 `None`；成功回 `Frame(img, width, height, time.monotonic())`
  - `release()`：`cap.release()`
  - `is_opened`：`cap.isOpened()`

- [ ] **VS3** 實作 `RTSPSource`：
  - `__init__(self, url: str)`
  - `open()`：`cv2.VideoCapture(url, cv2.CAP_FFMPEG)`
  - 其餘同 `WebcamSource`

- [ ] **VS4** 實作 `ReconnectingSource`（包裝任一 VideoSource）：
  ```python
  class ReconnectingSource:
      def __init__(self, inner: VideoSource, reconnect_interval_sec: float,
                   clock: Callable[[], float] = time.monotonic): ...
  ```
  - `read()`：inner 未開啟時 → 若距上次嘗試 < interval 回 `None`，否則嘗試 `inner.open()`（失敗靜默）
  - `read()` 回 None → 呼叫 `inner.release()`，標記斷線
  - `open/release/is_opened` 委派給 `inner`

- [ ] **VS5** 實作 `create_source(cfg: SourceConfig, clock=time.monotonic) -> VideoSource`：
  - `cfg.type == 'webcam'` → `WebcamSource(cfg.webcam_index)`
  - `cfg.type == 'rtsp'` → `RTSPSource(cfg.rtsp_url)`
  - 外層皆包 `ReconnectingSource(inner, cfg.reconnect_interval_sec, clock)`

- [ ] **VS6** 建立 `tests/test_video_source.py`，使用**假 inner source**（不碰真實攝影機），測試：
  - inner 未開啟 → 第一次 `read` 觸發 `open`
  - `open` 失敗（引發例外）→ 回 `None`，且重試間隔受 `reconnect_interval_sec` 限制（不超頻）
  - `inner.read()` 回 `None` → 呼叫 `inner.release()`（下次重連）
  - `create_source` `type='webcam'` → 外層為 `ReconnectingSource`，inner 為 `WebcamSource`
  - `create_source` `type='rtsp'` → inner 為 `RTSPSource`

- [ ] **VS7** 執行 `rtk pytest tests/test_video_source.py -v` 確認全部通過

- [ ] **VS8** `git commit -m "feat: add video source with auto-reconnect"`
