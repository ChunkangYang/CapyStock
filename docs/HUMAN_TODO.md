# Human TODO — 需要人工介入的任務

## Fix 3：價格獨立掃描鏈（2026-06-13）

### price-fetch.yml 手動 dispatch 驗證
- **狀態**：待人工執行（GitHub Actions 本地測不了）
- **步驟**：
  1. GitHub Actions → 「Price Fetch」→ Run workflow（手動 dispatch）一次
  2. 確認 commit 只含 `data/cloud-cache/*_price.csv` 與 `_fetch_report.json`
  3. 確認全程 < 20 分鐘
  4. 隔個交易日 JST 17:05 後，檢查本地 `data/cache/7203_price.csv` 最後一筆 = 當日日期
     （price_sync 排程於 JST 17:00 自動拉價 + 重算）
- **備註**：cloud-fetch.yml 排程預設已改為只抓 `margin`，價格全權交給 price-fetch.yml。

### Fix 2 / Fix 1 前端畫面確認
- **狀態**：待人工確認（瀏覽器）
- **步驟**：
  1. `/pocket` 開「模擬交易」popup → 購入價標示「即時報價（延遲約20分）HH:MM」或「最後收盤 YYYY-MM-DD」
  2. 價格資料 > 3 日 → popup 紅字警示「請先回 Dashboard 雲端同步」
  3. `/signals/[code]` 進場 popup、`/portfolio` 新增表單（輸入代號後）帶入即時報價
  4. 投機訊號頁掃描中顯示「🔄 自動更新中」（refreshing=true，stale-while-revalidate）
  5. 證據截圖存 `docs/EVIDENCES/`

## Sprint 25：持倉管理（S25）

### T25-07/08 Dashboard 前端畫面確認
- **狀態**：待人工確認
- **理由**：需瀏覽器確認 Dashboard 4 區塊（持倉/追蹤清單/訊號/金雞）正確顯示
- **步驟**：
  1. 啟動 `npm run dev`（frontend dev server）
  2. 開啟 `http://localhost:5173`
  3. 確認「持倉狀態」顯示 portfolio 資料（買入股票）
  4. 確認「追蹤清單」顯示 watchlist 資料（關注股票）
  5. 兩者已明確分開
  6. 前往 `/portfolio` 確認持倉管理頁可正常新增/平倉

## Sprint 6：金雞高股息儀表板

### E2E 測試 Playwright 瀏覽器安裝
- **狀態**：待執行
- **理由**：Playwright 瀏覽器未安裝，需要運行 `npx playwright install`
- **命令**：
  ```bash
  cd frontend && npx playwright install
  npm run test:e2e
  ```
- **預期結果**：20 個 E2E 測試全綠
  - dashboard.spec.ts：7 個測試
  - dividend.spec.ts：10 個測試
  - signals.spec.ts：11 個測試
- **優先級**：High（完整驗收必須）

### 後端測試
- **狀態**：待確認
- **預期**：Sprint 1-3 的後端 API 應已完成，dividend 相關 endpoints 應存在
- **測試命令**：
  ```bash
  pytest tests/api/test_dividend_router.py -v
  ```
