# S19 測試證據 — 信用残 ingest 層（多來源）

**實作日期**：2026-04-29
**實作範圍**：M6 Sprint 19 / S19
**實作人員**：Claude (Sonnet)

---

## 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | IngestionResult import | `from capystock.ingest.base import IngestionResult, IngestionSource` | 正常 import | ✅ 通過 | |
| 2 | ManualCsvSource 欄位別名正規化 | 建立含「融資残」欄位的 CSV，呼叫 parse_bytes | 自動對應到 margin_long | ⬜ 未測試 | 需人工執行 |
| 3 | IngestService fallback chain | Mock Yahoo 回 403，確認切換到 Minkabu | result.source == "minkabu" | ⬜ 未測試 | |
| 4 | 全部失敗時 result.ok=False | Mock 兩個 sources 均拋 Exception | ok=False, error 含摘要 | ⬜ 未測試 | |
| 5 | POST /api/v1/ingest/status/{code} | 呼叫 GET | 回傳 3 個 kind 狀態 | ⬜ 未測試 | |
| 6 | POST /api/v1/ingest/upload | 上傳 CSV multipart | 寫入 cache，回 IngestionResult | ⬜ 未測試 | |

## 自動測試（若有）

| # | 測試檔案 | 測試描述 | 測試結果 | 備註 |
|---|---|---|---|---|
| 1 | `tests/unit/test_ingest_service.py` | Manual CSV 5 種欄位別名 | ⬜ 未執行 | 待建立 |

## DoD 驗收清單

- [ ] Yahoo / Minkabu 爬蟲可解析真實頁面
  - **測試結果**：
  - **備註**：需實際網路連線測試
- [ ] ManualCsvSource 多欄位別名 normalize 正確
  - **測試結果**：
  - **備註**：
- [ ] IngestService fallback chain 正確運作
  - **測試結果**：
  - **備註**：
- [ ] 4 個 API endpoints 正常運作
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
