# S16 測試證據 — 比較模式 service + 對比頁

**實作日期**：2026-04-28
**實作範圍**：M5 Sprint 16 / S16
**實作人員**：Claude (Sonnet 4.6)

---

## 自動測試結果

```
correlation matrix tests PASS
API validation tests PASS
```

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | correlation 對角線 = 1.0 | 構造 2 code 價格序列，計算 correlation_matrix | m['A']['A'] == 1.0 | ✅ 通過 | |
| 2 | correlation 對稱 | 同上 | m['A']['B'] == m['B']['A'] | ✅ 通過 | |
| 3 | correlation 值域 [-1,1] | 同上 | -1 ≤ corr ≤ 1 | ✅ 通過 | |
| 4 | codes=[] → 422 | GET /api/v1/compare/signals?codes= | HTTP 422 | ✅ 通過 | |
| 5 | codes 超過 5 檔 → 422 | GET /api/v1/compare/signals?codes=A,B,C,D,E,F | HTTP 422 | ✅ 通過 | |
| 6 | 重複 codes 自動去重 | codes=7203,7203,8058 | 回傳 [7203,8058] | ✅ 通過（dict.fromkeys） | |

## 功能測試（人工驗收用）

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 7 | 投機對比頁 | 瀏覽 /compare，輸入 2 個代碼 | 顯示正規化走勢折線圖 + 相關性矩陣 | ⬜ 未測試 | 需瀏覽器手動測試 |
| 8 | 金雞對比頁 | 瀏覽 /dividend/compare，輸入 2 個代碼 | 顯示雷達圖 + DPS bar | ⬜ 未測試 | 需瀏覽器手動測試 |
| 9 | 移除 chip | 點擊 × 移除一檔 | 圖表自動更新 | ⬜ 未測試 | |

## DoD 驗收清單

- [x] compare_service.py signals_bundle 含 correlation_matrix
- [x] correlation 對角線 = 1.0、對稱、值域 [-1,1]
- [x] codes=[] → 422；codes 超過 5 → 422
- [x] 重複 codes 去重
- [x] radar_normalized 每檔 8 軸 0–100（PASS=100, WARN=50, FAIL=0）
- [x] GET /compare/signals + /compare/dividend endpoint 掛載成功
- [ ] 前端投機對比頁瀏覽器驗收
- [ ] 前端金雞對比頁瀏覽器驗收

## 整體驗收

| 欄位 | 內容 |
|---|---|
| 測試日期 | 2026-04-28 |
| 測試人員 | Claude Sonnet 4.6（自動）/ 待人工驗收 |
| 整體結果 | ✅ 後端通過 / ⬜ 前端待驗收 |
| 主要問題 | 無 |
| 後續行動 | 啟動 dev server 後手動驗收 /compare 頁面 |
