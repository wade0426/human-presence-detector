# 人體偵測 `detection/detector.py`

> **對應檔案**：`src/detection/detector.py`、`tests/test_detector.py`  
> **前置條件**：[[types]]  
> **相依**：`ultralytics`（YOLOv8）、`torch`（裝置判斷）、`src.types.Frame`、`Detection`、`BBox`

## 任務

- [ ] **D1** 建立 `src/detection/detector.py`，定義 `PersonDetector`：
  ```python
  class PersonDetector:
      def __init__(self, model_path: str, confidence: float, device: str = "auto"): ...
      def detect(self, frame: Frame) -> list[Detection]: ...
      def _infer(self, image) -> list[tuple[float, float, float, float, float]]:
          """回傳 [(x1, y1, x2, y2, conf), ...](像素座標，已過濾 person 類別)"""
  ```

- [ ] **D2** 實作 `_resolve_device(device: str) -> str`（模組層級函數或靜態方法）：
  - `device == 'auto'`：若 `torch.cuda.is_available()` 回 `'cuda'`，否則回 `'cpu'`
  - `device == 'cuda'` / `'cpu'`：直接回傳

- [ ] **D3** 實作 `__init__`：
  - 呼叫 `_resolve_device` 決定裝置
  - `self.model = None`（**延遲載入**，不在 `__init__` 載入模型）

- [ ] **D4** 實作 `_infer(image)`：
  - 延遲載入：若 `self.model is None` 則 `YOLO(model_path).to(device)`
  - `self.model(image, classes=[0], conf=confidence, verbose=False)`
  - 將結果整理為 `[(x1, y1, x2, y2, conf), ...]` 回傳

- [ ] **D5** 實作 `detect(frame: Frame) -> list[Detection]`：
  - 呼叫 `self._infer(frame.image)`
  - 將像素座標正規化為 `BBox(x1/w, y1/h, (x2-x1)/w, (y2-y1)/h)`
  - 回傳 `[Detection(bbox, conf), ...]`

- [ ] **D6** 建立 `tests/test_detector.py`，用 `unittest.mock.patch.object` mock `_infer` 方法測試：
  - mock `_infer` 回固定像素框 `[(100, 50, 300, 400, 0.85)]`，frame 為 500×600 → `detect` 應回傳 `BBox(x=0.2, y=0.0833..., w=0.4, h=0.5833...)` 誤差 < 1e-6
  - mock `_infer` 回空列表 → `detect` 回傳 `[]`
  - `_resolve_device('cpu')` → `'cpu'`；`_resolve_device('auto')` 在無 CUDA 環境 → `'cpu'`

- [ ] **D7** 執行 `rtk pytest tests/test_detector.py -v` 確認全部通過

- [ ] **D8** `git commit -m "feat: add YOLOv8 person detector"`
