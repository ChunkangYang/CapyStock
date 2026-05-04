# S17 測試證據 — 前端技術指標 + 對比頁 UI

**實作日期**：2026-04-28
**實作範圍**：M5 Sprint 17 / S17
**實作人員**：Claude (Sonnet 4.6)

---

## 自動測試結果

svelte-kit sync 執行成功，.svelte-kit/ 生成完畢，`$app/stores` 型別解析正常。

## 元件清單

| 元件 | 路徑 | 狀態 |
|---|---|---|
| IndicatorOverlay.svelte | frontend/src/lib/components/ | ✅ 建立 |
| RSIPanel.svelte | frontend/src/lib/components/ | ✅ 建立 |
| MACDPanel.svelte | frontend/src/lib/components/ | ✅ 建立 |
| ComparePanel.svelte | frontend/src/lib/components/ | ✅ 建立 |
| /signals/[code] 擴充 | frontend/src/routes/signals/[code]/ | ✅ 更新 |
| /compare | frontend/src/routes/compare/ | ✅ 建立 |
| /dividend/compare | frontend/src/routes/dividend/compare/ | ✅ 建立 |

## 功能測試（人工驗收用）

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | SMA toolbar | /signals/7203 → 勾選 SMA 20 | K 線圖出現藍色 SMA 線 | ⬜ 未測試 | |
| 2 | 布林通道 | 同頁面勾選 BB | K 線圖出現上下軌（灰色） | ⬜ 未測試 | |
| 3 | RSI 子圖 | 勾選 RSI → 子圖出現 | 出現 RSI(14) 折線 + 30/70 水平線 | ⬜ 未測試 | |
| 4 | MACD 子圖 | 勾選 MACD | 出現 MACD line + signal + histogram | ⬜ 未測試 | |
| 5 | 指標訊號卡片 | 右欄指標訊號 | 列出近 30 日訊號（日期+名稱+強度） | ⬜ 未測試 | |
| 6 | 投機對比正規化 | /compare?codes=7203,8058 | 兩條不同色折線（期初=100） | ⬜ 未測試 | |
| 7 | 相關性矩陣 | 同上 | 2×2 heatmap，對角線深綠 | ⬜ 未測試 | |
| 8 | 金雞雷達圖 | /dividend/compare?codes=7203,8058 | 2 色 polygon overlay | ⬜ 未測試 | |
| 9 | DPS bar 並排 | 同上 | 每年兩個不同色 bar | ⬜ 未測試 | |

## DoD 驗收清單

- [x] IndicatorOverlay.svelte：SMA/EMA/BB toggle 動態加/移除 line series
- [x] RSIPanel.svelte：RSI(14) + 30/70 水平線
- [x] MACDPanel.svelte：line × 2 + histogram（正負雙色）
- [x] /signals/[code]：toolbar + 子圖摺疊 + 指標訊號卡片
- [x] /compare：chip bar + 正規化折線 SVG + 相關性矩陣 + 訊號清單
- [x] /dividend/compare：雷達圖 + DPS bar + 指標明細表
- [x] nav 加入「投機對比」「金雞對比」連結
- [ ] 瀏覽器手動驗收 9 項

## 整體驗收

| 欄位 | 內容 |
|---|---|
| 測試日期 | 2026-04-28 |
| 測試人員 | Claude（建構驗證）/ 待人工 |
| 整體結果 | ✅ 程式碼完整 / ⬜ 前端待瀏覽器驗收 |
| 主要問題 | lightweight-charts 在 SSR 環境需確認 onMount 是否正確延遲 |
| 後續行動 | npm run dev → 逐項測試 |
