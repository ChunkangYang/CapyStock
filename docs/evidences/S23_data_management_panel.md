# S23 測試證據 — 資料管理面板 + 上傳介面

**實作日期**：2026-04-29
**實作範圍**：M6 Sprint 23 / S23
**實作人員**：Claude (Sonnet)

---

## 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | GET /api/v1/data/overview | 有 watchlist 時呼叫 | 回傳每 code 4 個 kind age_days | ⬜ 未測試 | |
| 2 | 顏色警示：35 日舊 | Mock 一檔 35 日舊 | 顯示紅色 cell | ⬜ 未測試 | 前端測試 |
| 3 | POST /api/v1/data/batch-ingest | codes=3, kinds=1 → 3 tasks | 全部執行，完成後 status=completed | ⬜ 未測試 | |
| 4 | 批量 ingest 1 個失敗仍繼續 | Mock 1 code 失敗 | 其餘繼續，失敗 result ok=False | ⬜ 未測試 | |
| 5 | SSE 進度串流 | 執行 batch-ingest 後連 /stream | 收到 done/total 進度事件 | ⬜ 未測試 | |
| 6 | /data 前端總覽 | 開啟 /data | 表格顯示 watchlist 所有 code | ⬜ 未測試 | |
| 7 | /data/ingest 前端 | 選 codes + kinds → 執行 | 顯示進度條 + 結果表格 | ⬜ 未測試 | |
| 8 | /data/upload 前端 | 拖拉 CSV → 預覽 → 上傳 | Toast 成功 | ⬜ 未測試 | |

## DoD 驗收清單

- [ ] overview 回每 code 4 個 kind，age_days 欄位
  - **測試結果**：
  - **備註**：
- [ ] batch-ingest 1 個失敗仍繼續
  - **測試結果**：
  - **備註**：
- [ ] /data 前端顏色正確
  - **測試結果**：
  - **備註**：
- [ ] /data/upload 拖拉上傳完整流程
  - **測試結果**：
  - **備註**：

## 整體驗收

| 欄位 | 內容 |
|---|---|
| 測試日期 | |
| 測試人員 | |
| 整體結果 | ⬜ 通過 / ⬜ 部分通過 / ⬜ 未通過 |
| 主要問題 | |
| 後續行動 | |
