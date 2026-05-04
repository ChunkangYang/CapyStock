# S20 測試證據 — 投資部門別 ingest（JPX 週報）

**實作日期**：2026-04-29
**實作範圍**：M6 Sprint 20 / S20
**實作人員**：Claude (Sonnet)

---

## 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | JPX flow import | `from capystock.ingest.jpx_flow import JpxFlowSource` | 正常 import | ✅ 通過 | |
| 2 | estimate_stock_flow 比例計算 | 市場=(1000,-500,300)億，個股佔0.5% | 個股=(5,-2.5,1.5)億 | ⬜ 未測試 | |
| 3 | POST /api/v1/ingest/jpx-weekly | 有網路時呼叫 | 下載並寫入 _market_flow.csv | ⬜ 未測試 | 需網路 |
| 4 | GET /api/v1/ingest/market-flow?weeks=12 | 有 _market_flow.csv 時呼叫 | 回傳最近 12 筆 | ⬜ 未測試 | |

## DoD 驗收清單

- [ ] JPX Excel 解析欄位齊全（億日圓單位）
  - **測試結果**：
  - **備註**：
- [ ] 個股 flow 估算 estimated=True 標記
  - **測試結果**：
  - **備註**：
- [ ] market-flow API 回傳正確格式
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
