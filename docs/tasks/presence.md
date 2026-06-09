# 在場判定 `presence.py`

> **對應檔案**：`src/presence.py`、`tests/test_presence.py`  
> **前置條件**：[[types]]  
> **相依**：`src.types.Detection`、`src.types.BBox`（純 Python，不依賴 Qt）

## 任務

- [ ] **P1** 建立 `src/presence.py`，實作 `PresenceEvaluator`，照 `docs/detailed-design.md` §5.4 的介面：
  ```python
  class PresenceEvaluator:
      def __init__(self, roi: BBox, min_box_height_ratio: float, debounce_count: int): ...
      def update(self, detections: list[Detection]) -> bool: ...
      def set_roi(self, roi: BBox) -> None: ...
      @property
      def stable_present(self) -> bool: ...
  ```

- [ ] **P2** 實作 `_qualifies(d: Detection) -> bool` 私有方法：
  - 計算 `d.bbox.center`（`cx, cy`）
  - 判斷 `cx` 在 `[roi.x, roi.x + roi.w]` 內且 `cy` 在 `[roi.y, roi.y + roi.h]` 內
  - 判斷 `d.bbox.h >= min_box_height_ratio`
  - 兩者皆成立才回 `True`

- [ ] **P3** 實作 `update` 去抖動邏輯（照詳細設計虛擬碼）：
  - `raw = any(_qualifies(d) for d in detections)`（空 list → False）
  - 若 `raw == stable`：清除 pending 計數
  - 否則：累計 pending；達 `debounce_count` 次才翻轉 `stable`

- [ ] **P4** 建立 `tests/test_presence.py`，測試以下情境：
  - 連續 `debounce_count - 1` 次反訊號不翻轉；第 `debounce_count` 次才翻轉
  - ROI 邊界：`center` 剛好在左邊界（`cx == roi.x`）→ 在場；剛好超出右邊界 → 不在場
  - 大小門檻：`bbox.h == min_box_height_ratio` → 在場；`bbox.h < min_box_height_ratio` → 不在場
  - 空 `detections` → 原本在場，經去抖後應切換為離開
  - 多偵測：其中一個合格即在場
  - `set_roi` 後以新 ROI 判定（原本在場的偵測可能變為不在場）

- [ ] **P5** 執行 `rtk pytest tests/test_presence.py -v` 確認全部通過

- [ ] **P6** `git commit -m "feat: add presence evaluator with debounce"`
