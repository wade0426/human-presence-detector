# 模塊任務：連線狀態（FR-6）

> **對應需求**：FR-6（RTSP 串流穩定性與狀態呈現）  
> **詳細設計**：`docs/detailed-design.md` §4.8  
> **涉及檔案**：`src/app/connection_state.py`、`src/ui/widgets/connection_badge.py`、`src/ui/strings.py`、`src/ui/main_window.py`  
> **測試檔**：連線相關測試（擴充）

---

## 任務清單

### 1. 修改 `src/app/connection_state.py`

- [ ] 在 `ConnectionState` 枚舉新增：
  ```python
  STREAM_ERROR = "stream_error"   # 影像異常（解碼失敗或逾時）
  ```
- [ ] 新增映射：`_STATUS_MAP["stream_error"] = ConnectionState.STREAM_ERROR`
- [ ] 新增嚴重度：`_SEVERITY[ConnectionState.STREAM_ERROR] = "warning"`
- [ ] 新增圖示鍵：`_ICON_KEY[ConnectionState.STREAM_ERROR] = "conn-stream-error"`

### 2. 修改 `src/ui/widgets/connection_badge.py`

- [ ] 新增圖示字符：`_ICON_CHARS["conn-stream-error"] = "⚠"`（或等效警示符號）
- [ ] 確認 `set_state(ConnectionState.STREAM_ERROR)` 不丟例外，圖示與文字正確顯示

### 3. 修改 `src/ui/strings.py`

- [ ] 新增（此行依賴任務 1 完成）：
  ```python
  CONN_TEXT[ConnectionState.STREAM_ERROR] = "影像異常"
  ```
- [ ] 確認 `CONN_STREAM_ERROR = "影像異常，畫面可能延遲或中斷。"` 也已新增（見 `reminder-dispatch` 任務中的 strings 修改）

### 4. 修改 `src/ui/main_window.py`

- [ ] 在 `on_connection_status` 的「顯示覆蓋文字」分支，將 `STREAM_ERROR` 納入：
  ```python
  if state in (NO_SIGNAL, RECONNECTING, CONNECTING, STREAM_ERROR):
      self._preview.set_overlay_text(CONN_TEXT.get(state, ""))
      self._presence_badge.set_present(False)
  ```

### 5. 確認 `StreamHealthMonitor` 整合至 Worker（`src/app/worker.py`）

- [ ] Worker run loop 中建立或注入 `StreamHealthMonitor`（timeout 取預設 10s）
- [ ] 每次偵測迴圈呼叫 `monitor.update(has_frame, is_opened, now)`
- [ ] 依回傳的 `StreamHealth` 映射並 emit 對應連線狀態字串：

  | StreamHealth | emit 字串 | ConnectionState |
  |---|---|---|
  | OK | `"connected"` | CONNECTED |
  | NO_SIGNAL | `"no_signal"` | NO_SIGNAL |
  | TIMEOUT | `"stream_error"` | STREAM_ERROR |
  | DISCONNECTED | `"reconnecting"` | RECONNECTING |

### 6. 確認降噪已生效

- [ ] 確認 `logging_setup.suppress_decoder_noise()` 在 `main()` 啟動早期被呼叫（如已在第一行則標記此項為已完成）
- [ ] 不需另外解析 ffmpeg 訊息

### 7. 擴充單元測試

- [ ] `from_status("stream_error") == ConnectionState.STREAM_ERROR`
- [ ] `severity / icon_key / CONN_TEXT` 均有對應值，不丟例外
- [ ] `ConnectionBadge.set_state(STREAM_ERROR)` 後圖示、文字正確
- [ ] 執行 `rtk pytest tests/` 確認連線相關測試通過

---

## 驗收標準

- 串流逾時時，UI 連線狀態切換為「影像異常」，不再只在背景輸出（AC-6.1）
- 串流恢復後，連線狀態自動回到「已連線」（AC-6.2）
- 背景錯誤訊息收斂，系統不崩潰（AC-6.3）
