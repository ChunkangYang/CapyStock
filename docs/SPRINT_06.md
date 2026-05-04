# Sprint 6 — 金雞高股息儀表板

依賴：[MILESTONE_03.md](MILESTONE_03.md)

## 路由
- `/dividend`：清單
- `/dividend/[code]`：個股詳細

## `/dividend` 列表頁

### 資料源
`GET /api/v1/scan/dividend`（最新 parquet）

### 篩選器
- Overall：multi-check（STRONG / HEALTHY / CAUTION / RISKY）
- 估算殖利率最低值 slider（0–10%）
- 配當無減配年數最低值 slider（0–10）
- 自己資本比率 slider（0–80%）
- 配當性向上限 slider（10–100%）
- Tag：☆ 只看我的最愛

### 表格欄位
- ★ / Code / Name / Overall（標籤色）/ DPS / Yield / 連續無減配 / Payout 平均 / 自己資本比 / EPS 成長 / Pass-Warn-Fail（迷你 stacked bar）

### 排序
預設 est_yield desc；可點 header 切換

## `/dividend/[code]` 個股詳細

### 主視覺
1. **8 指標雷達圖**（RadarChart.svelte）
   - 軸：Sales / EPS / OpMargin / Equity / OpCF / Cash / DPS / Payout
   - 數值 normalize 到 0–100：PASS=100, WARN=60, FAIL=20, N/A=0
2. **配當歷史 bar**（DividendBarChart.svelte）
   - 各年度 DPS（藍）+ EPS（虛線疊加）
3. **配當性向 vs EPS 折線**：雙 y 軸
4. **指標明細 table**：metric / score / note
5. **比較模式按鈕**：選最多 3 檔，跳轉 `/dividend/compare?codes=7203,8058,9984`

### 比較模式
- 路由 `/dividend/compare?codes=...`
- 雷達圖三色疊加；表格並排顯示

## 驗收（自動化）
- `npm run test:unit` 通過 `RadarChart.test.ts`：給定 8 指標分數渲染後軸標籤 + 數值 normalize 正確
- `npm run test:e2e` 通過 `e2e/dividend.spec.ts`：
  - 篩選器：拖 yield slider 後 URL `?min_yield=` 同步、表格 row 全部符合條件
  - 重整 URL → 篩選狀態保留
  - 排序：點 header → 表格第一列改變
  - 個股詳細：雷達圖 SVG/canvas 存在、配當 bar / payout 折線 DOM 存在、metric table row 數 = 8
  - 比較模式：選 3 檔跳 `/dividend/compare?codes=...`，雷達圖三條 series
  - 截圖回歸：列表（預設 + 篩選後） / 詳細 / 比較共 4 張
