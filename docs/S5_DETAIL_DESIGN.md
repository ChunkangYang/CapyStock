# S5 Detail Design — 進出場信號儀表板（投機）（實作紀錄）

依賴：[SPRINT_05.md](SPRINT_05.md)
完成日：2026-04-25

## 實裝產出
- ✅ `frontend/src/lib/components/KLineChart.svelte`：K 線圖表（lightweight-charts）
  - 日 K，60 日、起始價水平線（藍）、停損線（紅）、近 30 日低點（灰）
- ✅ `frontend/src/lib/components/FlowBarChart.svelte`：法人買賣超堆疊柱狀圖（echarts）
  - 三色：foreign / institution / individual
- ✅ `frontend/src/lib/components/MarginLineChart.svelte`：信用殘線圖
  - 融資 / 融券 + 倍率虛線
- ✅ `frontend/src/lib/components/SignalTimeline.svelte`：訊號時間軸（色碼 alert 標記）
- ✅ `frontend/src/lib/components/ConditionGauge.svelte`：三選二條件儀表（三顆燈 + 計數器）
- ✅ `frontend/src/lib/components/FavoriteToggle.svelte`：收藏按鈕（API 呼叫 + store 更新）
- ✅ `frontend/src/lib/components/DataTable.svelte`：資料表格（篩選 + 排序）
- ✅ `/signals` 列表頁：tab 切換（全市場 / 持倉 / 最愛）+ DataTable + 跳轉詳細頁
- ✅ `/signals/[code]` 詳細頁：
  - 上方 header：code / name / 最新價 / ★ / 加入 watchlist / 加入模擬
  - 左欄 7：K線 + 法人 + 信用残 + 時間軸
  - 右欄 3：條件儀表 + 吃貨訊號 + 停損狀態 + EDINET + notes

## 自動化測試
- `tests/unit/components/KLineChart.test.ts` — 5 個單元測試
- `tests/unit/components/FavoriteToggle.test.ts` — 6 個單元測試
- `tests/e2e/signals.spec.ts` — 11 個 E2E 測試（載入/切換/跳轉/截圖）
- 總計 22 個單元測試全綠
