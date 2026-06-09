# 總體進度

> 建議執行順序：純邏輯層 → I/O 介面卡 → Qt 層 → 組裝

## 環境與基礎

- [x] [[environment]] 開發環境與專案骨架
- [x] [[types]] 共用資料契約

## 核心純邏輯層（可純單元測試）

- [x] [[config]] 設定載入 / 驗證 / 儲存
- [x] [[presence]] 在場判定（ROI + 大小 + 去抖動）
- [x] [[timer-engine]] 工作 / 休息計時狀態機 ⭐⭐

## I/O 介面卡層

- [x] [[video-source]] 影像來源（RTSP / webcam / 重連）
- [x] [[detector]] 人體偵測（YOLOv8 封裝）
- [x] [[logging-store]] 工作 / 休息記錄寫入 SQLite

## Qt 層

- [x] [[worker]] 背景偵測工作執行緒
- [x] [[reminder]] 提醒元件（彈窗 / Toast / 懸浮）
- [x] [[ui]] 主視窗 / 設定對話框 / 系統匣

## 組裝

- [ ] [[main]] 進入點組裝 + 端到端驗收 (已完成組裝，待手動驗收)
