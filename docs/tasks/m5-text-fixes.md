# M5：修正介面文字錯誤

> 對應需求：`docs/proposal.md` 需求五
> 對應設計：`docs/detailed-design.md` §7
> 依賴模塊：無（獨立、純文案）。建議**最先**完成本模塊，為後續新增字串（M2c 的 `CLEAR_*`、M3 的 `FORCE_LOCK_*`、M4 的 tooltip）建立「無雜訊引號」的乾淨基準與防回歸測試。
> 異動檔案：
> - 修改 `src/ui/settings_schema.py`
> - 修改 `src/ui/strings.py`（如掃描後有需修正項目）
> - 擴充 `tests/test_strings.py`

---

## 任務清單

- [ ] **任務 1：修正 `settings_schema.py:153`（`reminder.reminding_display_mode` 的 hint）**

  現況（`src/ui/settings_schema.py` 第 153 行）：

  ```python
  "提醒中要顯示》超時時間「還是》工作時間＋提醒持續時間「。",
  ```

  修正為：

  ```python
  "提醒中要顯示「超時時間」還是「工作時間＋提醒持續時間」。",
  ```

  僅修正引號配對，不改變語意（FR-5.1、FR-5.3）。

  測試（`tests/test_strings.py`）：
  - `test_reminding_display_hint_uses_paired_quotes`：從 `SCHEMA` 找出 `key == "reminder.reminding_display_mode"` 的 `FieldSpec`，斷言其 `hint == "提醒中要顯示「超時時間」還是「工作時間＋提醒持續時間」。"` 且不含 `"》"`。

- [ ] **任務 2：新增防回歸掃描測試**

  - `test_no_stray_angle_quote_in_schema`：遍歷 `src.ui.settings_schema.SCHEMA`，對每個 `FieldSpec` 的 `label`、`hint` 斷言 `"》" not in value`。
  - `test_no_stray_angle_quote_in_strings`：用 `vars(strings)`（`import src.ui.strings as strings`）取出模組層級所有 `str` 型別常數（略過以 `_` 開頭或非字串型別），逐一斷言 `"》" not in value`。

  > 這兩個測試作為「防回歸守門」：之後 M2c／M3／M4 新增的 `CLEAR_*`、`FORCE_LOCK_*`、tooltip 字串若誤用 `》`，測試會立即失敗。

- [ ] **任務 3：全面掃描並修正 `strings.py`、`settings_schema.py` 其餘文字**

  逐一檢視 `src/ui/strings.py`、`src/ui/settings_schema.py`（含所有 `FieldSpec.label`/`hint`）中使用者可見字串，找出並修正：
  - 錯字、缺字、贅字
  - 不成對或誤用的引號（`》`、`「」` 混用）
  - 全形／半形不一致（標點符號、括號、冒號等）

  限制（FR-5.3）：**只修正錯誤呈現，不改變文案語意**。

  > 若任務 1、2 的掃描測試已涵蓋 `》` 問題且全文未發現其他錯誤，本任務可能無新增程式碼變更，但仍需執行掃描並記錄「已檢查、無其他問題」。

---

## 完成定義（Definition of Done）

- [ ] `settings_schema.py:153` 的 hint 已改為成對引號版本，且不含 `》`
- [ ] `test_reminding_display_hint_uses_paired_quotes`、`test_no_stray_angle_quote_in_schema`、`test_no_stray_angle_quote_in_strings` 三測試新增並通過
- [ ] `src/ui/strings.py`、`src/ui/settings_schema.py` 全文掃描完成，無明顯錯字／標點錯誤（或已修正）
- [ ] `rtk pytest tests/test_strings.py tests/test_settings_schema.py` 全數通過
