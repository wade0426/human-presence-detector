# 總體進度

| 模塊 | 說明 | 完成 |
|---|---|---|
| M1 | Domain 型別（types.py / config.py 列舉） | - [x] |
| M2 | 計時/狀態機（timer_engine.py） | - [x] |
| M3 | 影像擷取（video_source.py + frame_grabber.py） | - [x] |
| M4 | 協調器（worker.py） | - [x] |
| M5 | 主視窗與狀態顯示（main_window / status_strip / presence_badge） | - [x] |
| M6 | 動作列與 ROI 編輯（action_bar / preview_view / theme） | - [x] |
| M7 | 提醒/休息流程 UI（popup / return_prompt） | - [x] |
| M8 | 設定與結構（config / settings_schema / settings） | - [x] |
| M9 | 應用組裝（main.py） | - [x] |

> 依相依順序建議實作：M1 → M2 → M3 → M8 → M4 → M5 → M6 → M7 → M9
