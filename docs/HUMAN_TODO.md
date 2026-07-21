# Human TODO — 需要人工介入的任務

## 自動模擬交易上線（2026-07-21）

程式碼與本地驗證已完成（見 [AUTO_PAPER_TRADE_PLAN.md](AUTO_PAPER_TRADE_PLAN.md)）。以下要你操作：

> ✅ 1、2 已於 2026-07-21 由 Claude 執行完畢（secrets 三項齊全；dry-run + 正式跑各一次，
> 正式跑進場 3 檔並 commit `46746dacd`，Telegram 日報確認送達）。剩下第 3 項要你隔天看。

1. **GitHub Secrets 確認**（Settings → Secrets and variables → Actions）
   - `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`：日報要送到你的 Telegram，缺這兩個就只寫 log 不通知
   - `EDINET_API_KEY`：第一盤（EDINET 申報）的資料源，缺了口袋名單會嚴重縮水
2. **手動 dispatch 一次**：Actions →「Paper Trade」→ Run workflow
   - 第一次建議先 `dry_run = true`：只跑不寫檔、不 commit，看 log 輸出正不正常
   - 再跑一次 `dry_run = false`：確認 commit 只含 `data/ledgers/auto-pocket.json`、
     `data/auto_trade_log/`、`data/scan_snapshots/pocket_*.json`、`data/cloud-cache/edinet/daily/`
   - 確認 Telegram 收到日報
3. **隔個交易日 JST 17:30 後**：檢查 Actions 排程有自動跑、`/auto-trade` 頁資金曲線多一個點
   - 本機/雲端主機要看到最新結果：按 Dashboard「雲端同步」（會順手拉帳本與每日 log）或 `git pull`

> 注意：GitHub 排程 workflow 只在**預設分支**跑；本 repo 預設分支＝`feature/s25-portfolio`，已相符。

## 外網部署（雲端 PaaS + Google 登入，2026-06-17）

程式碼/Dockerfile/測試已完成並本地驗證（見 [EXTERNAL_ACCESS.md](EXTERNAL_ACCESS.md)）。
以下三步需要你的帳號/網址才能完成，我無法代做：

1. **建立 Google OAuth Client**（Google Cloud Console）
   - OAuth consent screen → External，Test users 加入你的 Google 帳號
   - Credentials → OAuth client ID → Web application
   - Authorized redirect URI：`https://<部署網址>/auth/callback`
   - 取得 Client ID + Client Secret
2. **在 Render（或 Fly/Railway）部署**
   - New → Blueprint 連此 repo（讀 [render.yaml](../render.yaml)）；或 New → Web Service → Docker
   - 填環境變數：`GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`、`CAPYSTOCK_ALLOWED_EMAILS=cky1983@gmail.com`、
     `CAPYSTOCK_PUBLIC_BASE_URL=https://<部署網址>`、`EDINET_API_KEY`（選用）
   - **plan 建議 standard（2GB）**：free（512MB）全市場掃描會 OOM
3. **拿到網址後回填**
   - Google Console 的 redirect URI 改成實際網址 + `/auth/callback`
   - `CAPYSTOCK_PUBLIC_BASE_URL` 填實際網址
   - 進站登入後，`/data` 頁按「☁ 從雲端同步」拉首批資料

> 驗收：用白名單 email 登入 → 可進站；用其他 Google 帳號 → 被擋 403。

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
