# S22 測試證據 — 策略參數 Sweep（網格回測）

**實作日期**：2026-04-29
**實作範圍**：M6 Sprint 22 / S22
**實作人員**：Claude (Sonnet)

---

## 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | 網格笛卡兒積展開 | stop_loss=[0.03,0.05] × take_profit=[0.10,0.15] | 4 組合 | ✅ 通過（程式驗證 combos=4） | |
| 2 | 超過上限拒絕 | 構造 300 組合請求 | 422 錯誤 | ⬜ 未測試 | |
| 3 | 排序正確 | metric=total_return，rows 長度 = top_n | 第 1 列 ≥ 第 2 列 total_return | ⬜ 未測試 | |
| 4 | POST /api/v1/sweep/run | 有股票 cache 時執行 | 回 job_id + status=completed | ⬜ 未測試 | |
| 5 | DELETE /api/v1/sweep/{job_id} | 呼叫 cancel | status=cancelled | ⬜ 未測試 | |
| 6 | 前端 Sweep 頁面估算 N | 填入 stop_loss=3 值, take_profit=3 值 | 顯示 9 組合 | ⬜ 未測試 | |
| 7 | 熱圖顯示 | 2D sweep 後 | 熱圖格子 = stop_loss × take_profit | ⬜ 未測試 | |

## DoD 驗收清單

- [ ] 網格展開 4 組合 → rows 4 列
  - **測試結果**：✅（邏輯驗證通過）
  - **備註**：
- [ ] 排序 metric=total_return desc
  - **測試結果**：
  - **備註**：
- [ ] 500 組合 → 422
  - **測試結果**：
  - **備註**：
- [ ] 前端熱圖 + 排行榜頁面可正常載入
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
