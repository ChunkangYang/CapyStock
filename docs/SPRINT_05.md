# Sprint 5 — 進出場信號儀表板（投機）

依賴：[MILESTONE_03.md](MILESTONE_03.md)

## 路由
- `/signals`：列表頁
- `/signals/[code]`：個股詳細

## `/signals` 列表頁

### 資料源
- 主表：`GET /api/v1/scan/signals`（最新快照）
- 上方切換 tab：
  - **全市場訊號**（scan/signals）
  - **我的持倉**（signals API）
  - **我的最愛**（favorites?tag=speculative → 對每檔取 signals）

### 元件
- 篩選列：`只看吃貨` / `只看出場` / `只看停損` / `min score`
- `DataTable.svelte` 欄位：
  - ★（FavoriteToggle）/ Code / Name / Close / vs 起始 / vs 低點 / C1 / C2 / C3 / 訊號 icon / EDINET 計數 / Score
  - 點 row → 跳 `/signals/{code}`
- 排序：score / est_yield / 漲跌幅 / EDINET 數

## `/signals/[code]` 詳細頁

### 上方 header
- Code / Name / 最新價 / 來源（kabutan/yfinance）/ ★ / 「加入 watchlist」按鈕（pop modal 輸入 start_price）/ 「加入模擬清單」按鈕

### 主視覺（兩欄佈局，左 7 / 右 3）

**左欄（圖表）**：
1. **K 線圖**（KLineChart.svelte，lightweight-charts）
   - 日 K，60 日
   - 疊加：start_price 水平線（藍）、停損線 `start_price * 0.95`（紅）、近 30 日低點線（灰）
   - Marker：alert 出現的日期掛三角（紅=出場、橘=停損、綠=吃貨、紫=EDINET）
2. **法人買賣超 stacked bar**（FlowBarChart.svelte，echarts）
3. **信用残 line**（MarginLineChart.svelte）
4. **訊號時間軸**（SignalTimeline.svelte）

**右欄（指標）**：
- **三選二條件儀表**（ConditionGauge.svelte）：三顆燈 + 是否 ≥2/3
- **吃貨訊號**：是 / 否 + 條件描述
- **停損狀態**：是 / 否
- **EDINET 事件清單**：最近 30 日，含申報人/種類/PDF 連結
- **notes 區塊**：snapshot.notes

### API 呼叫
- `GET /signals/{code}`
- `GET /signals/{code}/price?days=90`
- `GET /signals/{code}/flow?days=60`
- `GET /signals/{code}/margin?weeks=20`
- `GET /signals/{code}/edinet?days=30`

## 驗收（自動化）
- `npm run test:unit` 通過：
  - `KLineChart.test.ts`：series 數量正確（含 start_price / 停損 / 低點三條線）
  - `FavoriteToggle.test.ts`：點擊 emit add/remove 事件且呼叫 API
- `npm run test:e2e` 通過 `e2e/signals.spec.ts`：
  - 列表頁載入後表格列數 = mock 快照 row 數
  - 點 row 跳轉 `/signals/7203`，URL 正確
  - 詳細頁四個圖表容器 DOM 存在
  - 點 ★：斷言 POST `/api/v1/favorites` 被呼叫；reload 後 ★ 仍亮起
  - 截圖回歸：列表頁 + 詳細頁各一張
