# M4：強化提示說明（tooltip／設定頁清除按鈕）

> 對應需求：`docs/proposal.md` 需求四（FR-4.x）、需求二（FR-2.4 設定頁入口）
> 對應設計：`docs/detailed-design.md` §6
> 依賴模塊：[[m0-config]]（`ReturnSoundConfig`/`ForceLockConfig` 欄位名稱）、[[m2c-clear-data-dialog]]（`CLEAR_DATA_BUTTON`、`run_clear_data_flow` 由 [[int-integration]] 接線）、[[m5-text-fixes]]（`reminder.reminding_display_mode` 的修正版 hint，本模塊在其基礎上補 tooltip）
> 異動檔案：
> - 修改 `src/ui/settings_schema.py`（`FieldSpec.tooltip`、`tooltip_for`、新欄位、新分類、既有欄位 hint/tooltip）
> - 修改 `src/ui/settings.py`（套用 tooltip、「紀錄」頁清除鈕、`clear_data_requested` 訊號）
> - 新增/擴充 `tests/test_settings_schema.py`
> - 擴充 `tests/test_ui.py`

> FR-4 行為要點：本模塊**為純文案／UI 屬性調整，不改變設定讀寫邏輯**（`get_value`/`set_value`/`validate` 不變）。

---

## 任務清單

- [ ] **任務 1：`FieldSpec` 擴充 `tooltip` 欄位與 `tooltip_for()`**

  於 `src/ui/settings_schema.py` 修改 `FieldSpec`（在既有欄位最後新增，向後相容——所有既有 `FieldSpec(...)` 呼叫均為位置＋關鍵字混用且不超過 10 個既有欄位，新增的 `tooltip` 一律走關鍵字）：

  ```python
  @dataclass(frozen=True)
  class FieldSpec:
      key: str
      label: str
      hint: str
      widget: WidgetKind
      category: str
      minimum: float | None = None
      maximum: float | None = None
      step: float | None = None
      decimals: int | None = None
      choices: tuple[str, ...] | None = None
      tooltip: str | None = None
  ```

  並新增輔助函式（放在 `fields_for()` 之前或之後皆可，建議與其他工具函式相鄰）：

  ```python
  def tooltip_for(spec: FieldSpec) -> str:
      return spec.tooltip or spec.hint
  ```

- [ ] **任務 2：新增分類「強制休息」與 `force_lock.*` / `reminder.return_sound.*` 欄位**

  `CATEGORIES` 追加新分類：

  ```python
  CATEGORIES: tuple[str, ...] = ("基本", "偵測", "提醒", "紀錄", "進階", "強制休息")
  ```

  在 `SCHEMA` 中新增以下 `FieldSpec`（位置：`reminder.*` 區塊內加入 `return_sound` 兩筆；`SCHEMA` 結尾加入 `force_lock` 五筆）：

  ```python
  # --- 加入「提醒」分類既有欄位之後 ---
  FieldSpec(
      "reminder.return_sound.enabled",
      "回來提示音效",
      "離開後返回時，是否在「歡迎回來」視窗播放提示音效。",
      WidgetKind.BOOL,
      "提醒",
      tooltip="開啟後，系統判定你回到座位並彈出「歡迎回來」視窗時，"
      "會循環播放下方音效檔，直到按下確認鈕為止。",
  ),
  FieldSpec(
      "reminder.return_sound.sound_path",
      "回來提示音效檔",
      "「歡迎回來」視窗播放的音效檔路徑。",
      WidgetKind.PATH,
      "提醒",
      tooltip="留空或檔案不存在時會自動靜音，不會造成錯誤或當機。",
  ),
  ```

  ```python
  # --- 加入 SCHEMA 結尾，新分類「強制休息」 ---
  FieldSpec(
      "force_lock.enabled",
      "啟用強制休息鎖定",
      "是否在達到設定條件時自動鎖定螢幕，強制使用者離開休息。",
      WidgetKind.BOOL,
      "強制休息",
      tooltip="預設關閉。開啟後請依下列欄位設定觸發時機與警示方式。",
  ),
  FieldSpec(
      "force_lock.trigger",
      "觸發時機",
      "overtime＝工作超時達門檻時鎖定；on_rest＝一進入休息狀態就鎖定。",
      WidgetKind.CHOICE,
      "強制休息",
      choices=("overtime", "on_rest"),
      tooltip="overtime＝提醒後持續超時超過下方「超時門檻」才鎖定；"
      "on_rest＝只要進入休息狀態就立刻鎖定，督促確實離開座位。",
  ),
  FieldSpec(
      "force_lock.warning_mode",
      "鎖定前警示方式",
      "immediate＝立即鎖定；countdown_cancel＝倒數並可取消；countdown_only＝倒數但不可取消。",
      WidgetKind.CHOICE,
      "強制休息",
      choices=("immediate", "countdown_cancel", "countdown_only"),
      tooltip="immediate＝直接鎖定螢幕，不另行警示；"
      "countdown_cancel＝顯示倒數視窗，期間可按「取消本次鎖定」中止；"
      "countdown_only＝顯示倒數視窗但無法取消，倒數結束必定鎖定。",
  ),
  FieldSpec(
      "force_lock.overtime_threshold_min",
      "超時門檻（分鐘）",
      "觸發時機為 overtime 時，超過工作門檻多久後觸發鎖定。",
      WidgetKind.FLOAT,
      "強制休息",
      minimum=MINUTE_MIN,
      maximum=MINUTE_MAX,
      step=0.1,
      decimals=1,
      tooltip="僅當「觸發時機」為 overtime 時生效；"
      "計算起點為進入提醒狀態之後累積的超時秒數。",
  ),
  FieldSpec(
      "force_lock.countdown_sec",
      "鎖定倒數秒數",
      "鎖定前警示方式為倒數模式時，鎖定前的倒數秒數。",
      WidgetKind.INT,
      "強制休息",
      minimum=1,
      tooltip="僅當「鎖定前警示方式」為 countdown_cancel 或 countdown_only 時生效。",
  ),
  ```

  > `reminder.return_sound.*` 為三層 key（`reminder.return_sound.enabled`），`force_lock.*` 為兩層 key；`get_value`/`set_value` 已支援，無需修改。完成後執行 [[m5-text-fixes]] 的掃描測試確認新增的 `label`/`hint`/`tooltip` 未含 `》`。

- [ ] **任務 3：強化既有欄位的 hint／補 tooltip（FR-4.2 / FR-4.4）**

  修改下列既有 `FieldSpec`，補上 `tooltip=`（`hint` 維持不變，`reminder.reminding_display_mode` 的 `hint` 採用 [[m5-text-fixes]] 修正後的版本）：

  ```python
  FieldSpec(
      "reminder.method",
      "提醒方式",
      "提醒呈現方式：彈出視窗、系統通知、置頂懸浮倒數。",
      WidgetKind.CHOICE,
      "提醒",
      choices=("popup", "toast", "floating"),
      tooltip="popup＝畫面中央彈出視窗；toast＝右下角系統通知；"
      "floating＝畫面角落的小型置頂倒數視窗。",
  ),
  ```

  ```python
  FieldSpec(
      "timer.rest_count_mode",
      "休息計算方式",
      "presence＝必須離座才算休息；fixed＝固定倒數。",
      WidgetKind.CHOICE,
      "基本",
      choices=("presence", "fixed"),
      tooltip="presence＝必須離開鏡頭前方才算休息，回來即結束休息；"
      "fixed＝休息時間到就結束，不論是否仍在鏡頭前。",
  ),
  ```

  ```python
  FieldSpec(
      "reminder.reminding_display_mode",
      "提醒中顯示",
      "提醒中要顯示「超時時間」還是「工作時間＋提醒持續時間」。",
      WidgetKind.CHOICE,
      "提醒",
      choices=("overtime", "work_and_reminder"),
      tooltip="overtime＝只顯示超過工作門檻多久；"
      "work_and_reminder＝同時顯示本次工作時間與提醒已持續時間。",
  ),
  ```

  ```python
  FieldSpec(
      "presence.debounce_count",
      "去抖動次數",
      "連續幾次判定一致才改變在場狀態，避免閃爍誤判。",
      WidgetKind.INT,
      "偵測",
      minimum=1,
      tooltip="例如設為 3，需連續 3 次偵測結果相同才會切換在場／離開狀態，"
      "數值越大越穩定但反應越慢。",
  ),
  ```

  ```python
  FieldSpec(
      "detection.confidence",
      "偵測把握度",
      "人體偵測的最低把握度，越高越嚴格、誤判越少但可能漏抓。",
      WidgetKind.FLOAT,
      "偵測",
      minimum=0.05,
      maximum=1.0,
      step=0.05,
      decimals=2,
      tooltip="例如設為 0.5 表示模型信心需達 50% 以上才視為偵測到人；"
      "調高可減少誤判，調低可減少漏判。",
  ),
  ```

  ```python
  FieldSpec(
      "presence.min_box_height_ratio",
      "最小人體高度比例",
      "人體框需占畫面高度的最小比例，用來濾掉遠處的人。",
      WidgetKind.FLOAT,
      "偵測",
      minimum=0.05,
      maximum=1.0,
      step=0.05,
      decimals=2,
      tooltip="例如設為 0.3 表示偵測框高度需達畫面高度的 30% 以上，"
      "可過濾掉遠處或誤判的小框。",
  ),
  ```

  ```python
  FieldSpec(
      "detection.device",
      "運算裝置",
      "運算裝置：自動 / CPU / GPU（CUDA）。",
      WidgetKind.CHOICE,
      "進階",
      choices=("auto", "cpu", "cuda"),
      tooltip="auto＝自動偵測並優先使用 GPU；"
      "cpu＝強制使用 CPU（較慢但相容性最佳）；"
      "cuda＝強制使用 NVIDIA GPU（需安裝對應 CUDA 驅動）。",
  ),
  ```

- [ ] **任務 4：`SettingsWindow` 套用 tooltip（`_build_category_page`）**

  修改 `src/ui/settings.py`：
  1. 從 `src.ui.settings_schema` 的匯入新增 `tooltip_for`。
  2. 在 `_build_category_page()` 迴圈中，為輸入元件與該列標籤套用 tooltip：

  ```python
  for spec in fields_for(category):
      widget = self._make_widget(spec)
      self._widgets[spec.key] = widget

      tooltip = tooltip_for(spec)
      if isinstance(widget, QWidget):
          widget.setToolTip(tooltip)

      hint = QLabel(spec.hint)
      hint.setProperty("role", "secondary")
      hint.setWordWrap(True)
      self._hint_labels[spec.key] = hint
      self._hint_texts[spec.key] = spec.hint

      field_layout = QVBoxLayout()
      field_layout.setSpacing(2)
      if isinstance(widget, QWidget):
          field_layout.addWidget(widget)
      field_layout.addWidget(hint)

      field_container = QWidget()
      field_container.setLayout(field_layout)

      label = QLabel(spec.label)
      label.setToolTip(tooltip)
      form.addRow(label, field_container)
  ```

  > `PathField` 是 `QWidget` 子類別，`setToolTip` 對其有效（顯示於整個瀏覽列）。`form.addRow(spec.label, ...)` 由字串改為 `QLabel` 物件，`QFormLayout.addRow(QWidget, QWidget)` 簽章相容，行為不變。

- [ ] **任務 5：`SettingsWindow` 新增「清除資料」按鈕與 `clear_data_requested` 訊號**

  修改 `src/ui/settings.py`：
  1. 新增匯入：`from PySide6.QtCore import Signal`。
  2. 在 `SettingsWindow` 類別新增訊號：

  ```python
  class SettingsWindow(QDialog):
      clear_data_requested = Signal()
  ```

  3. 在 `_build_category_page()` 中，當 `category == "紀錄"` 時，於表單最後加入清除按鈕（沿用 [[m2c-clear-data-dialog]] 的 `strings.CLEAR_DATA_BUTTON`）：

  ```python
      for spec in fields_for(category):
          ...  # 同任務 4

      if category == "紀錄":
          clear_button = QPushButton(strings.CLEAR_DATA_BUTTON)
          clear_button.clicked.connect(self.clear_data_requested.emit)
          form.addRow(clear_button)

      scroll.setWidget(container)
      return scroll
  ```

  > 本模塊只負責「設定頁」的按鈕與訊號發送；訂閱 `clear_data_requested` 並呼叫 [[m2c-clear-data-dialog]] 的 `run_clear_data_flow` 屬於 [[int-integration]]。

- [ ] **任務 6：撰寫測試**

  `tests/test_settings_schema.py`（新增或擴充，純 Python 無 Qt）：

  ```python
  from src.ui.settings_schema import SCHEMA, tooltip_for


  def test_every_field_has_hint() -> None:
      for spec in SCHEMA:
          assert spec.hint.strip() != ""


  def test_tooltip_for_falls_back_to_hint() -> None:
      sample = next(spec for spec in SCHEMA if spec.tooltip is None)
      assert tooltip_for(sample) == sample.hint


  def test_method_tooltip_mentions_floating() -> None:
      spec = next(spec for spec in SCHEMA if spec.key == "reminder.method")
      tooltip = tooltip_for(spec)
      assert "floating" in tooltip
      assert "角落" in tooltip
  ```

  `tests/test_ui.py`（擴充，qt）：

  ```python
  def test_settings_widgets_have_tooltip(qtbot: pytest.QtBot, tmp_path: object) -> None:
      from src.ui.settings import SettingsWindow

      window = SettingsWindow(AppConfig(), config_path=str(tmp_path / "config.yaml"))
      qtbot.addWidget(window)

      for key in ("reminder.method", "force_lock.enabled", "timer.rest_count_mode"):
          widget = window._widgets[key]
          assert widget.toolTip() != ""


  def test_settings_has_clear_button(qtbot: pytest.QtBot, tmp_path: object) -> None:
      from src.ui.settings import SettingsWindow
      from src.ui.settings_schema import CATEGORIES
      from src.ui.strings import CLEAR_DATA_BUTTON

      window = SettingsWindow(AppConfig(), config_path=str(tmp_path / "config.yaml"))
      qtbot.addWidget(window)

      record_index = CATEGORIES.index("紀錄")
      page = window._stack.widget(record_index)
      button = page.findChild(QPushButton, None)
      buttons = [
          b for b in page.findChildren(QPushButton) if b.text() == CLEAR_DATA_BUTTON
      ]
      assert len(buttons) == 1

      with qtbot.waitSignal(window.clear_data_requested, timeout=1000):
          qtbot.mouseClick(buttons[0], Qt.MouseButton.LeftButton)
  ```

  > `test_settings_has_clear_button` 需於檔案頂部匯入 `QPushButton`（`from PySide6.QtWidgets import QPushButton`）；若該檔已匯入則略過。`record_index`/`button` 為示例變數，可依現有檔案風格調整，但須保留「找到唯一一個文字為 `CLEAR_DATA_BUTTON` 的按鈕並點擊後 emit `clear_data_requested`」的斷言。

---

## 完成定義（Definition of Done）

- [ ] `FieldSpec.tooltip`、`tooltip_for()` 新增，所有既有 `FieldSpec(...)` 呼叫不需改動即可通過型別檢查
- [ ] `CATEGORIES` 含「強制休息」；`SCHEMA` 新增 `reminder.return_sound.*`（2 筆）與 `force_lock.*`（5 筆）
- [ ] 任務 3 列出的 7 個既有欄位皆補上 `tooltip`
- [ ] `SettingsWindow` 所有欄位元件與標籤皆有 `toolTip()`；「紀錄」頁有「清除資料」按鈕並能 emit `clear_data_requested`
- [ ] 5 個測試新增並通過（3 個 schema 測試 + 2 個 qt 測試）
- [ ] `rtk pytest tests/test_settings_schema.py tests/test_ui.py` 全數通過
- [ ] `rtk pytest tests/test_strings.py` 仍通過（含 [[m5-text-fixes]] 的掃描測試，新字串不含 `》`）
- [ ] `rtk ruff check src/ui/settings_schema.py src/ui/settings.py` 無錯誤
- [ ] `rtk mypy src/ui/settings_schema.py src/ui/settings.py` 無新增錯誤
