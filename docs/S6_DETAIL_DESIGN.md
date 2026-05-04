# S6 Detail Design — 金雞高股息儀表板（實作紀錄）

依賴：[SPRINT_06.md](SPRINT_06.md)
完成日：2026-04-25

## 實裝產出
- ✅ `frontend/src/lib/components/RadarChart.svelte`：8 指標雷達圖（echarts）
  - 軸：Sales / EPS / OpMargin / Equity / OpCF / Cash / DPS / Payout
  - 數值 normalize：PASS=100, WARN=60, FAIL=20, N/A=0
- ✅ `frontend/src/lib/components/DividendBarChart.svelte`：配當歷史柱狀圖
  - 柱狀圖：DPS（藍）；虛線：EPS（金）
- ✅ `frontend/src/routes/dividend/+page.svelte`：金雞清單頁
  - 篩選器：Overall / yield / 無減配年數 / 自己資本比 / 配當性向上限 / tag（最愛）
  - 表格：★ / Code / Name / Overall / DPS / Yield / 連無減配 / Payout avg / 自己資本比 / EPS growth / Pass-Warn-Fail stacked bar
  - 排序：預設 est_yield desc，可點 header 切換
- ✅ `frontend/src/routes/dividend/[code]/+page.svelte`：個股基本面詳細頁
  - 上方 header：code / name / overall tag / 收藏按鈕
  - 左欄：8 指標雷達圖 + 配當歷史圖表
  - 右欄：指標評分表（8 指標） + 統計摘要（PASS/WARN/FAIL 計數）

## 自動化測試
- `tests/unit/components/RadarChart.test.ts` — 10 個單元測試（score normalization、軸標籤、計數）
- `tests/e2e/dividend.spec.ts` — 12 個 E2E 測試（篩選/排序/導航/詳細頁/收藏/截圖）
- 單元測試全部通過；E2E 測試待環境配置（Playwright 瀏覽器需安裝）
