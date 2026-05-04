# S21 測試證據 — 異常偵測 + 事件研究

**實作日期**：2026-04-29
**實作範圍**：M6 Sprint 21 / S21
**實作人員**：Claude (Sonnet)

---

## 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | AnomalyService import | `from api.services.anomaly_service import AnomalyService` | 正常 import | ✅ 通過 | |
| 2 | volume_spike 偵測 | 構造 20 日均量=100，第 21 日=400 | 觸發 volume_spike，value=4.0 | ⬜ 未測試 | |
| 3 | 缺資料天不誤報 | 傳入含 None 的序列 | 不 raise，不誤報 | ⬜ 未測試 | |
| 4 | EventStudyService CAR 計算 | 構造已知 AR 序列 | CAR = cumsum(AAR) 逐 offset 相符 | ⬜ 未測試 | |
| 5 | 0 events → 空陣列 | events=[] | n_events=0，aar/car=[] | ⬜ 未測試 | |
| 6 | GET /api/v1/analytics/anomaly/{code} | 呼叫有資料的 code | 回傳 AnomalyEvent 列表 | ⬜ 未測試 | |
| 7 | POST /api/v1/analytics/event-study/{code} | 錯誤日期格式 | 422 | ⬜ 未測試 | |

## DoD 驗收清單

- [ ] volume_spike / price_jump / gap_up / gap_down 四種類型均正確觸發
  - **測試結果**：
  - **備註**：
- [ ] EventStudy CAR 計算數學正確
  - **測試結果**：
  - **備註**：
- [ ] API 422 輸入驗證正確
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
