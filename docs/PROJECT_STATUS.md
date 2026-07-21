# CapyStock — 專案進度

## 最後更新
2026-07-21（自動模擬交易：GitHub Actions 每日下單 + /auto-trade 圖表頁 + Telegram 日報）

## 2026-07-21 自動模擬交易（零 LLM，每日 Actions 執行）

- 需求：依三盤策略每天自動做模擬交易、留 log（已結算盈虧 + 未結算暫定收益）、
  系統內看得到圖表、每天 Telegram 收日報。
- ✅ **策略腳本化**：進場＝當日三盤口袋名單（drop_pct 排序、每筆 30 萬、單日≤3 檔、
  同時≤10 檔、停損出場後 20 日冷卻、股價/折價/資料新鮮度防呆）；出場＝既有棘輪移動停損。
  純 config 門檻，決策可重現。核心純函式 `auto_trade_service.select_new_trades`。
- ✅ **單一寫入者**：帳本 `data/ledgers/auto-pocket.json`（`owner="bot"`）只由
  [paper-trade.yml](../.github/workflows/paper-trade.yml)（JST 17:00）寫；本地 `advance_all()`
  預設跳過 bot 帳本、API 寫入端點 403 → 不會與 Actions 雙寫衝突。
- ✅ **每日 log**：`data/auto_trade_log/YYYY-MM-DD.json`（進場/出場/被跳過原因/當日權益）。
- ✅ **圖表頁** `/auto-trade`：資金曲線（權益/現金/持倉市值 + 起始資金基準線）、
  持倉暫定損益、已結算明細、每日 log 展開、單筆交易走勢 modal。
- ✅ **Telegram 日報**：`format_report()` → workflow curl 送出（token/chat_id 缺就跳過）。
- ✅ **同步**：雲端同步順手拉 Actions 產出的帳本與 log（PaaS 部署也會更新）。
- ✅ **測試**：`test_auto_trade.py` 14 passed；全套 255 passed（2 紅為既有 indicator mock /
  favorites，非本次）。前端 `vite build` 綠 + Docker 重建後實機截圖
  [docs/EVIDENCES/auto-trade-page-replay.png](EVIDENCES/auto-trade-page-replay.png)。
- ⏳ 待人工：GitHub Secrets 確認 + 手動 dispatch 一次 → [HUMAN_TODO.md](HUMAN_TODO.md)。
- 細節與重放結果見 [AUTO_PAPER_TRADE_PLAN.md](AUTO_PAPER_TRADE_PLAN.md)。

## 2026-06-20 同步推進模擬交易 + 單筆交易價格折線圖

- 需求：每日開啟時的雲端同步，同步行情時也把模擬交易推到最新價；點進交易能看
  「進場日 → 至今」的價格折線圖，沒同步/非交易日那天留白即可。
- ✅ **同步順手推進帳本**：[data_sync_service.py](../api/services/data_sync_service.py)
  `run_cloud_sync` 在 rescan 階段後呼叫 `ledger_service.advance_all()`（棘輪移動停損
  更新、觸線者出場），結果帶回 `ledger_advance`。與 rescan 綁定（Dashboard 同步、
  price_sync 排程皆 rescan=True）→ 按一次雲端同步＝行情/訊號/模擬交易一次到最新。
  rescan=False（測試/純價格套用）不動帳本，避免誤改真實模擬交易。
- ✅ **單筆交易價格序列 API**：[ledger_service.py](../api/services/ledger_service.py)
  `build_trade_price_series` / `trade_price_series` + [ledger.py](../api/routers/ledger.py)
  `GET /ledgers/{id}/trades/{tid}/price`：回「日曆軸」dates/closes，當日 cache 無收盤
  （週末、未同步那天）→ close=None（前端留白）；已出場交易軸到出場日為止。
- ✅ **前端折線圖**：新增 [TradePriceChart.svelte](../frontend/src/lib/components/TradePriceChart.svelte)
  （echarts，`connectNulls:false` 缺資料留白 + 進場價/停損線 markLine + 出場點 markPoint）；
  [ledger/[id]/+page.svelte](../frontend/src/routes/ledger/[id]/+page.svelte) 每列加「📈 圖」鈕
  → modal 顯示。SyncGate 詢問文案補上「並把模擬交易推進到最新收盤」。
- ✅ **測試**：`test_ledger_price_series.py`（3）+ `test_data_sync_service.py` 新增 2 —
  全套 184 passed（唯一紅＝既有 indicator mock，非本次）；前端 `vite build` 綠。
- ✅ **驗證**：TestClient 打端點 200 / 缺交易 404；7203 真實 cache 進場 2026-05-25→至今
  軸 27 天、15 交易日有值、12 留白（含週末與 cache 截止後）。

## 2026-06-17 外網訪問（雲端 PaaS 部署 + Google 登入）

## 2026-06-17 外網訪問（雲端 PaaS 部署 + Google 登入）

- 需求：把本地 Docker(localhost:8000) 改成外網可連、只有使用者 Google 帳號能登入。
- 資料同步確認：`run_cloud_sync` 本來就直接打 GitHub Contents API 抓 cloud-cache，**不依賴本地 .git**；
  repo public → 免 token。外網主機開機後雲端同步即有資料。
- ✅ **Google 登入閘門**：新增 [api/auth.py](../api/auth.py)（Authlib + Starlette Session）：
  `/auth/login|callback|logout|me` + email 白名單 + 純 ASGI `AuthGateMiddleware`（不干擾 SSE）。
  三項齊全（CLIENT_ID/SECRET/ALLOWED_EMAILS）才啟用；未設＝停用（本地零回歸）。
- ✅ **main.py**：掛 SessionMiddleware + 條件式 AuthGate；CORS 改 `CAPYSTOCK_CORS_ORIGINS` 可加。
- ✅ **Dockerfile**：CMD 吃 `$PORT` + `--proxy-headers`；`COPY data/`（種子資料）；
  新增 [.dockerignore](../.dockerignore) 排除 56MB cloud-cache（開機後雲端同步拉）。
- ✅ **data_sync_service.py**：加 `GITHUB_TOKEN` header（private repo / rate limit 防呆）。
- ✅ **部署設定**：[render.yaml](../render.yaml) 藍圖 + requirements(authlib/itsdangerous) + docker-compose env 註解。
- ✅ **測試**：[test_auth.py](../tests/unit/test_auth.py) 10 passed；全套 179 passed（唯一紅是既有 indicator mock，非本次）。
- ✅ **驗證**：本地 TestClient（auth 關/開）+ 實 Docker 容器（PORT=9123/9124，auth 關→200、auth 開→
  health 200 / 受保護 API 401 / 頁面 302→Google）全綠。
- ⏳ 待人工：建 Google OAuth client、Render 部署填 secret、拿到網址回填 redirect/BASE_URL —
  見 [HUMAN_TODO.md](HUMAN_TODO.md) 與 [EXTERNAL_ACCESS.md](EXTERNAL_ACCESS.md)。

## 2026-06-13 修復實作完成（Fix 1 / Fix 2 / Fix 3）

- ✅ **Fix 1-A 掃描禁外網**：`scraper.fetch_margin(cache_only=)`、`signal_service.analyze_one(offline=)`、`run_signals_scan` 全走 offline（margin 只讀快取、name 不爬 kabutan）。測試 `test_signal_service.py::TestOfflineScan`。
- ✅ **Fix 1-B stale-while-revalidate**：`scan.py _get_or_compute_live_signals` 有舊資料立即回 + daemon thread 背景重算；response 加 `computed_at`/`refreshing`。
- ✅ **Fix 1-C dividend 分頁**：`/scan/dividend` 加 `limit/offset`（預設 50）+ `to_dict("records")`；Dashboard `limit=5`、/dividend `limit=200`。
- ✅ **Fix 1-D mtime key TTL**：`_inputs_mtime_key` 60 秒 module-level 快取，省每請求 11k 檔 stat。
- ✅ **Fix 2-1 price_date 誠實標示**：`gate2_cost` 回傳 `price_date`；pocket 前端表格小字 + popup 文案 + >3 日紅字警示。測試 `test_pocket_filter.py`。
- ✅ **Fix 2-2 quote 即時報價**：`api/services/quote_service.py`（in-memory TTL 5 分，不落地）+ `api/routers/quote.py` `GET /quote/{code}`；`portfolio_service._current_price` 改先打 quote fallback CSV；pocket/signals[code]/portfolio 前端接 quote。測試 `test_quote.py`。
- ✅ **Fix 3-1 price bulk**：`cloud_fetch.py fetch_price_bulk_cloud` + `--price-bulk`（yf.download 批次、增量合併 trim 260 列）。測試 `test_cloud_fetch_price_bulk.py`。
- ✅ **Fix 3-2 price-fetch.yml**：收盤後 JST 15:40 獨立抓價 workflow；cloud-fetch.yml 排程預設改 `margin`。
- ✅ **Fix 3-3 price_sync**：`api/services/data_sync_service.py run_cloud_sync(kinds=)`（router 與排程共用）+ scheduler `price_sync` job（JST 17:00）。測試 `test_data_sync_service.py`、`test_scheduler_service.py`。
- ⏳ 待人工：price-fetch.yml 手動 dispatch、前端畫面截圖 → 見 [HUMAN_TODO.md](HUMAN_TODO.md)。

## 2026-06-13 問題調查：① 頁面載入慢 ② 「現價」與市場不同步（修法已設計，待實作）

> 接手須知：以下兩個問題的根因都已用實際代碼路徑 + 檔案時間戳證實，修法已寫到「改哪個檔、哪個函式、加什麼參數、測試怎麼寫、驗收標準」的粒度。照順序實作即可，不需要重新調查。

### 問題 ②：模擬交易加入時顯示的「現價」與真實市價不符 — 根因（已證實）

價格的完整資料流（單一路徑，四層 stale 疊加）：

```
GitHub Actions cloud_fetch.py（yfinance 日線 period=6mo，每次覆寫）
  → data/cloud-cache/{code}_price.csv            ← Actions 排程寫入
  →（使用者「手動」按 Dashboard 雲端同步才複製）   ← ★ 最大斷點
  → data/cache/{code}_price.csv                  ← 後端唯一讀取層
  →（POST /api/v1/pocket 手動掃描時取最後一筆 close）
  → data/scan_snapshots/pocket_YYYY-MM-DD.json 的 gate2.latest_price
  →（前端 popup 開啟時）simEntryPrice = r.gate2.latest_price ← UI 卻標示「現價」
```

實測證據（2026-06-13 當天查）：
- `data/cache/7203_price.csv` 最後一筆 = **2026-05-26** close 3013（mtime 05-26 20:46）
- `data/cloud-cache/7203_price.csv` 最後一筆 = 2026-06-05 close 2853.5
- → 兩層相差 **18 天、價差 -5.3%**。使用者在 popup 看到的「現價」就是這個 18 天前的舊收盤。
- 即使全部同步到位，yfinance 日線最後一筆＝最近一個收盤，盤中也永遠不是即時價。

四層 stale 來源：
1. yfinance 日線只有收盤價（無盤中報價）
2. Actions cloud_fetch 的排程時間差
3. **cloud-cache → cache 需手動雲端同步**（實測 18 天沒同步，最大宗）
4. pocket 快照固定在「掃描當下」的值，之後不再變

對應代碼位置：
- `capystock/scraper.py` `fetch_price()`（scraper.py:227）：**cache-first 無 TTL** — CSV 存在且 ≥5 列就直接回，永遠不更新
- `capystock/pocket_filter.py` `gate2_cost()`（~:125）：`latest_price` = price CSV 最後一筆 close
- `frontend/src/routes/pocket/+page.svelte:90`：`simEntryPrice = r.gate2.latest_price ?? 0`，UI 文案「購入時價（預設現價，可改）」
- 同病的其他端點：`api/services/portfolio_service.py` `_current_price()`、`api/routers/watchlist.py` `_resolve_start_price()` — 都是 cache CSV 最後收盤
- 注意：已寫入帳本的交易 `entry_price` 是原樣存下的 stale 值（`api/services/ledger_service.py:158`），系統無法回填，使用者需自行校正歷史交易

### 問題 ② 修法（兩段，可分開 commit）

**Fix 2-1（短期：誠實標示資料日期，半天內可完成）**
1. `capystock/pocket_filter.py` `gate2_cost()` 回傳 dict 加一個 key `price_date`：值 = `str(pdf.iloc[-1]["date"])[:10]`（YYYY-MM-DD）。無 price_df 時為 None。
2. 快照與 API 不用改 schema：pocket router 直接回 dict（無 pydantic model 擋），gate2 dict 多一個 key 自然帶到前端。
3. `frontend/src/routes/pocket/+page.svelte`：
   - `Gate2` interface 加 `price_date: string | null`
   - popup 文案「購入時價（預設現價，可改）」改為「購入時價（最後收盤 {price_date}，可改）」
   - 表格現價欄位 hover/小字顯示 price_date
   - 若 `price_date` 距今 > 3 個日曆日 → popup 內紅字警示「⚠ 價格資料已是 {price_date}，請先回 Dashboard 雲端同步再加入」
4. 測試：`tests/unit/test_pocket_filter.py` 加 case — price_df 最後列 date=2026-06-05 → `gate2["price_date"] == "2026-06-05"`；price_df=None → None。
5. 注意：既有快照（pocket_2026-06-12.json 等）沒有 price_date，前端要容忍 undefined（顯示「日期不明」）。

**Fix 2-2（中期：加入交易當下抓即時報價）**
1. 新增 `api/routers/quote.py`：`GET /api/v1/quote/{code}` → `{code, price, price_time, source}`
   - 實作：`yf.Ticker(f"{code}.T").fast_info` 取 `last_price`（東證延遲約 20 分）；module-level dict 做 in-memory TTL 5 分鐘快取 `{code: (ts, price)}`；yfinance 失敗或回 None → HTTP 404
   - **不落地寫檔**：intraday 報價不能混進日線 price CSV（會讓 analyzer 把盤中價當收盤算訊號），所以不經過 fetch_price、不增加任何持久快取層
   - `api/main.py` include_router
2. `frontend/src/routes/pocket/+page.svelte`：popup 開啟時打 `/quote/{code}`，成功 → 預設購入價改用即時價，顯示「即時報價（延遲約20分）HH:MM」；失敗 → fallback 現行 snapshot 值 + Fix 2-1 的日期標示。
3. `/signals/[code]` 的進場 popup、`/portfolio` 新增持倉表單同樣接 quote（同一 fallback 邏輯）。
4. `api/services/portfolio_service.py` `_current_price()` 改為先打 quote helper（共用 TTL cache），失敗 fallback 現行 cache CSV 最後收盤。
5. 測試：`tests/unit/test_quote.py` — mock `yfinance.Ticker`：(a) 正常回價 (b) TTL 內第二次呼叫不再建 Ticker（assert mock 只被叫一次）(c) 失敗回 404、portfolio fallback 走 CSV。前端部分手動驗證，步驟與截圖存 `docs/EVIDENCES/`。

**架構 4 問（CLAUDE.md 架構紀律 §6）**：
1. 情境：source of truth 不單一 + invalidation 鏈斷（cloud-cache→cache 是手動斷點）。
2. Fix 2-1 純改現有函式；Fix 2-2 新增 quote 端點 — 不能改 fetch_price 的理由：fetch_price 是「日線歷史落地 CSV」路徑，intraday 報價是不同資料型態，混入會汙染 analyzer 輸入。quote 不落地。
3. 根因 =「現價」其實是多層快照盡頭的舊收盤。Fix 2-1 治「標示誤導」、Fix 2-2 治「值本身」；cloud→cache 手動斷點的根治屬 P1「單一原子同步鏈」（DEV_PROCESS_IMPROVEMENTS 已列，不在本次範圍）。
4. 修完 source of truth 數量不變（quote 是 in-memory TTL，非持久層）。

### 問題 ①：每個畫面載入都要等很久 — 根因（與 Chrome cache/cookie 無關）

前端 localStorage 快取只在同 session 內有效，延遲全部來自後端同步工作；cookie 對 localhost API 無影響，**清 Chrome 快取不會改善**。依嚴重度排序：

**主因 A：`GET /scan/signals` 在請求內全市場重算，且會退化成數千次即時爬蟲**
- `api/routers/scan.py` `_get_or_compute_live_signals()`：cache key = `data/cache` 全部 CSV 的最新 mtime；key 一變就**抱著 `_live_signals_lock` 在請求內跑 `run_signals_scan`（3700+ 檔）**
- `run_signals_scan` → `analyze_one`（`api/services/signal_service.py:129`）→ `scraper.fetch_margin(code)`：margin CSV 最新週 **> 8 天就即時爬 irbank**（scraper.py:343；docstring 寫 14 天、實作是 8 天，本身就是個不一致）
- 爬蟲有**全域** `_throttle()` 2 秒（scraper.py:24，整個 process 序列化）→ 當 margin 快取全面過期（目前 cache 已 18 天沒同步＝全面過期），一次「live 重算」= 數千次 × ≥2 秒的 irbank 請求，理論上限數小時
- 重算期間鎖被佔住 → Dashboard 與投機訊號頁的 /scan/signals 全部排隊等它 → 體感「每個畫面都卡」
- ping-pong：fetch_margin 成功會寫 CSV → mtime key 又變 → 下一個請求又觸發重算

**次因 B：`/signals/[code]` 詳情頁每次 live 爬外網**
- `signal_service.py:117` `fetch_name` 必爬 kabutan（完全沒快取）；`:123` `fetch_margin` 過期就爬 irbank → 每開一檔詳情 ≥4 秒（2 個 HTTP × 全域 2 秒 throttle），且寫 CSV 又觸發主因 A 的 invalidation

**次因 C：`/scan/dividend` 無分頁 + iterrows**
- `scan.py:130-177`：全表（~3700 列）每請求 `iterrows()` → pydantic 物件，回傳數 MB JSON；Dashboard 只顯示前 5 筆也得吞全表

**小因 D：mtime key 每請求 stat 11,258 個檔案 ≈ 0.34 秒**（實測值）

### 問題 ① 修法（4 個獨立小修，按 A→D 順序各自 commit）

**Fix 1-A：掃描路徑禁止外網（最關鍵，先做）**
1. `capystock/scraper.py` `fetch_margin(code, cache_only: bool = False)`：cache_only=True 時不爬 irbank、不寫檔 — 有 cached（不管多舊）直接回，沒有就回 None。
2. `api/services/signal_service.py` `analyze_one(..., offline: bool = False)`：offline=True → `fetch_margin(code, cache_only=True)`，且 name 為空時不爬 kabutan（直接用 ""，全市場掃描本來就從 universe.csv 帶 name）。
3. `api/services/scan_service.py` `run_signals_scan` 內改呼叫 `analyze_one(offline=True)`。設計意圖本來就是「single source of truth = data/cache，資料新鮮度由 cloud-sync 負責」，掃描永不打外網。
4. 順手把 fetch_margin docstring 的「14 天」改成與實作一致的 8 天（或反過來，擇一對齊）。
5. 測試：mock `_fetch_margin_irbank`，assert 走 `run_signals_scan` 路徑時它不被呼叫、且不產生 CSV 寫入。
6. 驗收：margin 快取全面過期狀態下，`GET /scan/signals` 首次回應 < 30 秒（純本地重算，不再有任何外部 HTTP）。

**Fix 1-B：stale-while-revalidate（重算不擋請求）**
1. `scan.py` `_get_or_compute_live_signals()` 改邏輯：
   - state 有舊 rows（即使 key 不符）→ **立即回舊資料**；若無 in-flight 重算則起 daemon thread 背景跑 `run_signals_scan`，算完 swap state
   - state 完全沒 rows（冷啟動）→ 維持現行同步算一次
   - `_live_signals_lock` 只包 state 讀寫，**不包** `run_signals_scan`（掃描互斥已有 scan_service 的 `_scan_lock`）
2. response 加 `computed_at`、`refreshing: bool` 欄位；前端投機訊號頁重用既有「🔄 自動更新中」指標：refreshing=true 顯示並 10 秒後重打一次。
3. 測試：預塞舊 state + 觸發 key 變動 → assert 呼叫立即回舊資料（< 1 秒）、背景算完後 state 已更新。

**Fix 1-C：`/scan/dividend` 分頁**
1. `scan.py` `get_dividend_snapshot` 加 `limit: int = 50, offset: int = 0` query 參數；篩選排序後 `df = df.iloc[offset:offset+limit]` 再轉 rows；轉換用 `df.to_dict("records")` 迴圈取代 `iterrows()`。回傳形狀維持 list（相容現有前端，本次不改成 dict 包裝）。
2. Dashboard `+page.svelte` 的 `/scan/dividend?...` 呼叫加 `&limit=5`；`/dividend` 頁加 `limit=200` 或仿投機訊號頁實作分頁。
3. 驗收：Dashboard 的 /scan/dividend 回應 payload < 50KB。

**Fix 1-D：mtime key 加 TTL**
1. `scan.py` `_inputs_mtime_key()` 結果用 module-level `(computed_ts, key)` 暫存，60 秒內直接重用，省掉每請求 0.34 秒的 11k 檔 stat。
2. 副作用：CSV 變動最晚 60 秒後才反映 — 可接受（Fix 1-B 之後重算已非阻塞）。

**整體驗收**：margin/price 快取過期 + 後端冷啟動的最差條件下，依序開 Dashboard / 投機訊號 / 金雞 / 口袋四頁，每頁首屏 API < 5 秒（唯一例外：冷啟動首次 /scan/signals 本地重算 < 30 秒，僅一次）；連開 3 檔個股詳情後回列表頁，不得再觸發 > 5 秒的等待。

### Fix 3：價格獨立掃描鏈（2026-06-13 使用者決策：價格與其他資料分開掃，收盤後抓價）

**需求**：margin/EDINET 等「大方向」資料不需即時，維持現有每日慢速鏈；**價格獨立出來**，每天東證收盤（15:30 JST）後立刻抓，並自動同步到本地，不再依賴手動雲端同步。

**現況問題**：[cloud-fetch.yml](.github/workflows/cloud-fetch.yml) 排程 UTC 08:00（JST 17:00）把 `kinds=margin,price` 綁在同一條批次鏈（160 檔/批、1100 秒 soft stop、resume 串接），全市場跑完要 ~23 個 chained run（數小時），價格新鮮度被 irbank 慢爬蟲拖累；抓完還要等使用者手動按雲端同步才進 `data/cache`。

**Fix 3-1：`scripts/cloud_fetch.py` 加價格 bulk 模式**
1. 新增函式 `fetch_price_bulk_cloud(codes: list[str]) -> list[dict]`：
   - `yf.download([f"{c}.T" for c in batch], period="7d", auto_adjust=False, group_by="ticker", threads=True, progress=False)`，每批 100 檔，批間 `time.sleep(1.0)`（參考 `capystock/scraper.py` `fetch_price_bulk` 的 MultiIndex 拆法，但**輸出格式不同**，見下）
   - 每檔 reshape 成與既有 cloud-cache 檔**完全相同的 header**：`date,open,high,low,close,adj close,volume,dividends,stock splits`（已實查 [data/cloud-cache/7203_price.csv](../data/cloud-cache/7203_price.csv) 確認此 9 欄；缺 dividends/stock splits 就補 0.0；date 切前 10 字元）
   - **增量合併**：既有 CSV 讀入 → concat → `drop_duplicates(subset=["date"], keep="last")` → sort → **trim 只留最後 260 列**（~1 年；讓每日 git diff 只有 1-2 行，避免 6mo 全檔覆寫造成 repo 膨脹）。檔案不存在 → 該檔改用 `period="6mo"` 單獨初始化。
   - 回傳與現有 `fetch_price` 相同形狀的 result dict list（ok/source/rows/code/kind），併入 `_fetch_report.json`
2. CLI 加 `--price-bulk` flag：啟用時 price 從主 per-code 迴圈移除、改走批次函式；margin 迴圈照舊不動。
3. 效能預估：3700 檔 ÷ 100/批 = 37 批 × 數秒 ≈ 5–10 分鐘，單一 Actions run 跑完全市場，**不需要 batch chaining**。

**Fix 3-2：新 workflow `.github/workflows/price-fetch.yml`**
1. 排程 `cron: "40 6 * * 1-5"`（UTC）= **JST 15:40**，東證 15:30 收盤後（Actions cron 常延遲 5–30 分，實際起跑 ~15:45–16:10，仍遠早於本地同步時間）。另加 `workflow_dispatch` 手動觸發。
2. steps（照抄 cloud-fetch.yml 的 checkout/python/pip/Telegram 模式）：
   - `python scripts/cloud_fetch.py --all --kinds price --price-bulk`
   - commit 限定 `git add data/cloud-cache/*_price.csv data/cloud-cache/_fetch_report.json` → `git pull --rebase` → push（rebase 解掉與 margin 鏈的 push race）
   - `concurrency: group: price-fetch`（與 cloud-fetch 分開，互不取消）
   - timeout-minutes: 25
3. **同步修改既有 cloud-fetch.yml**：排程觸發的預設 `kinds` 由 `margin,price` 改為 `margin`（價格改由新 workflow 全權負責，避免兩邊重複抓同一檔 + commit 衝突）。手動 dispatch 仍保留 price 選項當備援。

**Fix 3-3：本地自動同步價格（接起「手動雲端同步」這個斷點）**
1. 把 [api/routers/data.py](../api/routers/data.py) `cloud_sync()` 內的下載+複製+重算邏輯**搬**到新檔 `api/services/data_sync_service.py` 的 `run_cloud_sync(pull=True, kinds=None, rescan=True) -> dict`（是搬移不是複製 — router 與排程器共用同一實作，不留兩條會 diverge 的 path）：
   - 寫成**同步**函式（`httpx.Client`，並行下載用 `ThreadPoolExecutor`）；router 端改 `def`（FastAPI 自動丟 threadpool）或 `await asyncio.to_thread(...)` 包
   - `kinds` 參數：`None` = 現行為（全部 CSV + edinet_reports.json）；`["price"]` = GitHub 檔案列表與本地複製都只處理 `*_price.csv`（下載 11k 檔 → 3.7k 檔）
2. `CloudSyncRequest` 加 `kinds: Optional[list[str]] = None`，Dashboard 既有「雲端同步」按鈕行為不變（全量）。
3. `api/services/scheduler_service.py` 預設 jobs 加一筆：
   - `id="price_sync"`、`cron="0 17 * * 1-5"`（排程器 DEFAULT_TIMEZONE 已是 **Asia/Tokyo**，即 JST 17:00 — Actions 15:40 起跑 + ~10 分抓取 + commit，留 ~1 小時 buffer）
   - handler `_handler_price_sync` → `run_cloud_sync(pull=True, kinds=["price"], rescan=True)`；rescan 會重算訊號 + `prime_live_signals_cache` → 使用者晚上開頁面直接看到**當日收盤**，零等待
4. 與既有 jobs 的順序關係：margin 慢速鏈 JST 17:00 起跑（抓到深夜）、`daily_pipeline` 隔天 JST 08:00 全量處理 — price_sync 插在 17:00 只拉價格，互不干擾。

**效果**：每個交易日收盤後 ~1.5 小時內，當日收盤價自動進 `data/cache` 並完成訊號重算；pocket popup 的價格最差=當日收盤（配 Fix 2-1 的日期標示可直接驗證）。盤中真即時價仍由 Fix 2-2（quote 端點）負責，兩者互補不重疊。

**測試**：
- `tests/unit/test_cloud_fetch_price_bulk.py`（mock `yf.download`）：(a) 輸出 header 與既有檔逐字一致 (b) 增量合併 dedupe by date (c) trim 260 列 (d) 檔案不存在走 6mo 初始化 (e) 批次失敗不中斷其他批
- `tests/unit/test_data_sync_service.py`：tmp dir 放 `X_price.csv` + `X_margin.csv`，`kinds=["price"]` 只複製 price、`kinds=None` 全複製；rescan=False 不觸發掃描
- scheduler 測試：預設 jobs 含 `price_sync` 且 cron/handler 正確
- workflow 本地測不了 → 寫入 `docs/HUMAN_TODO.md`：手動 dispatch price-fetch.yml 一次，確認 (1) commit 只含 `*_price.csv` (2) 全程 < 20 分鐘 (3) 隔個交易日 JST 17:05 檢查本地 `data/cache/7203_price.csv` 最後一筆=當日日期

**實作順序建議**：Fix 3 可與 Fix 1-A/1-B 並行（不衝突）；3-1 → 3-2（先讓雲端有新鮮價格）→ 3-3（再接本地）。3-3 依賴的 rescan 體驗在 Fix 1-B 完成後最佳，但不互相 block。

## 2026-06-07 每日三盤濾網選股（舅舅心法第二篇）
- 三盤（三關全過進口袋名單），全用「真實個股資料」（非全市場攤平 flow）：
  - 第一盤 連續性：同一 EDINET 申報人窗口內重複申報 ≥ N 次（`pocket_filter.gate1_continuity`）
  - 第二盤 成本：主力成本＝申報日鄰近收盤均價，現價 ≤ +5%（`gate2_cost`）
  - 第三盤 籌碼集中：信用残 margin_long 連續 N 週下降（`gate3_margin`）
- 新增（全為新檔，未動既有掃描/快照/analyzer）：
  - `capystock/pocket_filter.py`（純函式三盤 + `evaluate_stock`）
  - `api/services/pocket_service.py`（讀 EDINET daily + 個股 CSV，全市場掃描 + JSON 快照）
  - `api/routers/pocket.py`（GET/POST `/api/v1/pocket`）
  - `frontend/src/routes/pocket/+page.svelte`（漏斗 + 口袋名單 + 差一關觀察名單）
  - `tests/unit/test_pocket_filter.py`（12 passed）
- 掃描結果（2026-06-07 快照）：候選 638 → 第一盤 172 → +第二盤 132 → 口袋名單 24 檔。
- 對映決策與不確定（EDINET「連續」近似、主力成本近似、極端負溢價待查、daily 快取窗口）見 [NOTES.md](NOTES.md)。

## 2026-06-06 全市場訊號修復（三件）
- 背景：抓最新資料後全市場看不到任何吃貨/出貨/停損訊號。根因見
  [SIGNAL_NO_HIT_AUDIT.md](SIGNAL_NO_HIT_AUDIT.md) / [SIGNAL_NO_HIT_RETRO.md](SIGNAL_NO_HIT_RETRO.md)
- ✅ **#3 快照硬化**：`write_snapshot(guard=True)` degraded 防呆（完整掃描但 has_exit 全 0 且既有快照有訊號 → 拒絕覆寫、存 `_rejected_`）+ `_scan_lock` 掃描序列化。所有最終 signals 寫入點都開 guard。
- ✅ **#2 停損分層**：`analyzer.analyze(holdings_context=)`，全市場掃描跳過持倉專屬訊號（移動/價格/最後一階/時間停損）；前端 `DataTable showStopLoss` 全市場隱藏停損欄。
- ✅ **#1 吃貨重定義**：原依賴的 flow 資料是「全市場數字蓋到每檔」（estimated=True、各檔相同）→ 改用真實個股資料：信用残(融資)連 3 週下降 + 股價撐住 + 量能維持。`_check_accumulation`。
- 結果：2026-06-06 快照 exit=291 / 吃貨=116 / 停損=0（各檔吃貨不同，真實個股訊號）。
- 流程改善建議見 [DEV_PROCESS_IMPROVEMENTS.md](DEV_PROCESS_IMPROVEMENTS.md)（P0 每日不變式健康檢查待做）。
- 既有紅測試（與本次無關，baseline 0096dfe5 即紅）：backtest 日期 off-by-one ×3、favorites tags、indicator mock spec — 待另案處理。

## 2026-06-07 模擬交易大改（IMP-002，已完成）
- 移除回測：`backtest_engine` / `simulation_service` / `strategy_sweep_service` / `routers.simulation` / `routers.sweep` / `schemas.simulation` / `schemas.sweep` / `workers.paper_worker` / 前端 `routes/simulation` 全部以 `DELETE_` prefix 移除。
- 新跟單帳本：`api/services/ledger_service.py`（帳本=資料夾、交易為主體）+ `routers/ledger.py`（`/ledgers` CRUD + 加入交易 + 推進）+ 前端 `/ledger`（列表/詳情）。
- 出場：棘輪式移動停損（只升不降，以進場後最高收盤為錨；當日收盤跌破停損線出場）。`advance_trade` 7 tests passed。
- 加入交易：`/pocket` 點「模擬交易」→ popup（選/建帳本 + 購入價預設現價可改 + 股數必填 + 移動停損 N%）；`/signals/[code]` 進場也改接帳本。
- 排程 `paper_advance` → `ledger_advance`（每日 7:00 推進）。詳見 [IMPROVE.md](IMPROVE.md) IMP-002。

## 目前待做（下一步）
- ✅ **Milestone 3：Web UI（FastAPI + SvelteKit）** — 全部完成（S1–S8）— 詳見 [MILESTONE_03.md](MILESTONE_03.md)
- ✅ **Milestone 4：自動化、排程、通知** — 全部完成（S9–S13）— 詳見 [MILESTONE_04.md](MILESTONE_04.md)
- ✅ **Milestone 5：技術指標與分析增強**（S14–S18）— 全部完成 — 詳見 [MILESTONE_05.md](MILESTONE_05.md)
- ✅ **Milestone 6：資料源擴展 + 進階分析**（S19–S23）— 全部完成 — 詳見 [MILESTONE_06.md](MILESTONE_06.md)
  - ✅ S19：信用残自動抓取（多來源 ingest 層）
  - ✅ S20：JPX 投資部門別週報 ingest
  - ✅ S21：異常偵測 + 事件研究
  - ✅ S22：策略參數 Sweep（網格回測）
  - ✅ S23：資料管理面板 + 上傳介面
- ✅ **Milestone 7：基本面評分增強**（S24）— 全部完成 — 詳見 [S24_DETAIL_DESIGN.md](S24_DETAIL_DESIGN.md)
  - ✅ S24：IR Bank 橫向表格解析 + Partial Data 支援（3543 コメダHD 成功評分）
- ✅ **Milestone 8：持倉管理**（S25）— 全部完成 — 詳見 [SPRINT_25.md](SPRINT_25.md)
  - ✅ S25：CLI portfolio / API /portfolio / Dashboard 4 區塊分離 / /portfolio 管理頁
- **2026-05-10 新增：實時掃描進度**
  - ✅ `api/services/scan_service.py`：run_signals_scan + run_dividend_scan 皆加入 snapshot_callback
    - 每掃 50 檔更新一次 parquet 快照，讓前端即時看到新增股票
  - ✅ `frontend/src/routes/signals/+page.svelte`：自動重新整理邏輯
    - onMount 檢查 localStorage scan_state，掃描中自動啟動 10 秒定時器
    - 定時清除市場頁 cache 並重新整理，自動顯示 "🔄 自動更新中..." 指標
    - 掃描完成時自動停止定時器
  - 驗證：掃描全市場 → 即時看到進度 (51/3747 → 100/3747 → ...)
- **2026-05-11 新增：投機訊號頁四個群組分離**
  - ✅ 我的最愛：從 `/favorites?tag=speculative` 取得星號收藏的股票
  - ✅ 我的持倉：從 `/portfolio` 取得投資組合中的股票
  - ✅ 追蹤清單：從 `/watchlist` 取得追蹤清單中的股票
  - ✅ 保留全市場訊號：從 `/scan/signals` 快照
- **2026-05-11 新增：投機訊號頁 bug 修復**
  - ✅ Bug 1：我的最愛快取保持（refreshAll 只清除當前 tab 快取，不影響其他 tab）
  - ✅ Bug 2：全部更新按鈕箭頭旋轉（分離 icon 和文字，只旋轉 icon）
- **2026-05-11 新增：投機訊號頁分頁實作**
  - ✅ 50 筆/頁分頁顯示，共 73 頁（3645 筆股票）
  - ✅ localStorage 快取每頁資料 + totalCount 持久化
  - ✅ 第一頁先載入，後續點擊按需載入 + 智能 page number 運算（1–3 + ... + 71–73）
  - ✅ refreshRow 時正確更新快取結構（{ rows, total }）
  - ✅ 驗證：點擊頁 1 → 73 → 1，資料正確變更且快取有效
- **下一步**：
  - ✅ SvelteKit SPA 路由 + 金雞/投機頁面 bug 修復（2026-05-04）
  - ✅ IMP-001：/watchlist 前端追蹤清單管理頁（2026-05-05）
  - ✅ 實時掃描進度（2026-05-10）
  - ✅ 投機訊號頁四個群組（2026-05-11）
  - ✅ 投機訊號頁 bug 修復（2026-05-11）
  - ✅ 投機訊號頁分頁實作（2026-05-11）
  - ✅ 全市場三訊號修復 #1/#2/#3（2026-06-06）
  - ✅ **2026-06-13 兩問題 + Fix 3 全部實作完成**（見本文件頂部「2026-06-13 修復實作完成」節）
    - 問題① 頁面慢：Fix 1-A 掃描禁外網 / 1-B stale-while-revalidate / 1-C dividend 分頁 / 1-D mtime key TTL ✅
    - 問題② 現價不同步：Fix 2-1 標示資料日期 / Fix 2-2 quote 即時報價端點 ✅
    - Fix 3 價格獨立掃描鏈：3-1 cloud_fetch bulk / 3-2 price-fetch.yml / 3-3 price_sync 排程 ✅
  - **🔜 P0 每日不變式健康檢查**（見 [DEV_PROCESS_IMPROVEMENTS.md](DEV_PROCESS_IMPROVEMENTS.md) 第三節）
    - 斷言：完整全市場掃描 `rows>=3000` 時 `has_exit` 不可為 0；訊號旗標不可全市場同值；latest_price 覆蓋率 >95%；cache 最新交易日距今 < N 營業日
    - 違反就用既有通知通道告警（Email/LINE）→ 終結「壞掉沒人發現」
    - 之後接 P1：資料新鮮度可見化 + 單一原子同步鏈
  - 修復 BUG-001（toast 動畫 + channel dot 更新）
  - 既有紅測試另案：backtest 日期 off-by-one ×3 / favorites tags / indicator mock spec
  - 清理：`DELETE_baseline_check/`（對照用 worktree leftover，可手動刪）

## 已完成 Sprint（詳細實作紀錄請見對應 detail design）

| Sprint | 主題 | 完成日 | 詳細紀錄 |
|---|---|---|---|
| S1 | Backend API 骨架 + service 化 | 2026-04-25 | [S1_DETAIL_DESIGN.md](S1_DETAIL_DESIGN.md) |
| S2 | 全市場掃描 worker + 每日快照 | 2026-04-25 | [S2_DETAIL_DESIGN.md](S2_DETAIL_DESIGN.md) |
| S3 | Favorites API | 2026-04-25 | [S3_DETAIL_DESIGN.md](S3_DETAIL_DESIGN.md) |
| S4 | SvelteKit 前端骨架 | 2026-04-25 | [S4_DETAIL_DESIGN.md](S4_DETAIL_DESIGN.md) |
| S5 | 進出場信號儀表板（投機） | 2026-04-25 | [S5_DETAIL_DESIGN.md](S5_DETAIL_DESIGN.md) |
| S6 | 金雞高股息儀表板 | 2026-04-25 | [S6_DETAIL_DESIGN.md](S6_DETAIL_DESIGN.md) |
| S7 | 模擬交易引擎 | 2026-04-25 | [S7_DETAIL_DESIGN.md](S7_DETAIL_DESIGN.md) |
| S8 | 模擬交易 UI | 2026-04-25 | [S8_DETAIL_DESIGN.md](S8_DETAIL_DESIGN.md) |
| S9 | 通知通道抽象 + Email/LINE | 2026-04-25 | [S9_DETAIL_DESIGN.md](S9_DETAIL_DESIGN.md) |
| S10 | 通知規則 + digest / realtime | 2026-04-25 | [S10_DETAIL_DESIGN.md](S10_DETAIL_DESIGN.md) |
| S11 | APScheduler 排程器 + daily_pipeline | 2026-04-27 | [S11_DETAIL_DESIGN.md](S11_DETAIL_DESIGN.md) |
| S12 | 通知/排程設定 UI + 健康監控頁 | 2026-04-27 | [S12_DETAIL_DESIGN.md](S12_DETAIL_DESIGN.md) |
| S13 | 部署整合（Docker / NSSM） + 文件 | 2026-04-27 | [SPRINT_13.md](SPRINT_13.md) |
| S14 | 技術指標計算引擎（RSI/MACD/BB/SMA/EMA/ATR/KD） | 2026-04-28 | [SPRINT_14.md](SPRINT_14.md) |
| S15 | 指標 API + scan score 融合 | 2026-04-28 | [SPRINT_15.md](SPRINT_15.md) |
| S16 | 比較模式 service + 對比頁（投機 + 金雞） | 2026-04-28 | [SPRINT_16.md](SPRINT_16.md) |
| S17 | 前端技術指標元件 + signals 頁指標 toolbar | 2026-04-28 | [SPRINT_17.md](SPRINT_17.md) |
| S18 | 技術指標接入回測引擎 + 報告增強 | 2026-04-28 | [SPRINT_18.md](SPRINT_18.md) |
| S19 | 信用残 ingest 層（base + yahoo + minkabu + manual） | 2026-04-29 | [SPRINT_19.md](SPRINT_19.md) |
| S20 | JPX 投資部門別 ingest + 個股估算 | 2026-04-29 | [SPRINT_20.md](SPRINT_20.md) |
| S21 | 異常偵測 + 事件研究 | 2026-04-29 | [SPRINT_21.md](SPRINT_21.md) |
| S22 | 策略參數 Sweep（網格回測 + 熱圖 UI） | 2026-04-29 | [SPRINT_22.md](SPRINT_22.md) |
| S23 | 資料管理面板（/data /data/ingest /data/upload） | 2026-04-29 | [SPRINT_23.md](SPRINT_23.md) |
| S24 | IR Bank 橫向表格解析 + Partial Data 支援 | 2026-05-03 | [S24_DETAIL_DESIGN.md](S24_DETAIL_DESIGN.md) |
| S25 | 持倉管理（Portfolio CLI + API + Frontend） | 2026-05-04 | [SPRINT_25.md](SPRINT_25.md) |

## Milestone 5 新增（S16–S18）

### 比較模式（S16）
- ✅ `api/schemas/compare.py`：CompareSignalsBundle / CompareDividendBundle
- ✅ `api/services/compare_service.py`：signals_bundle（Pearson corr）/ dividend_bundle
- ✅ `api/routers/compare.py`：GET /compare/signals + /compare/dividend
- ✅ `frontend/src/routes/compare/+page.svelte`：投機對比頁
- ✅ `frontend/src/routes/dividend/compare/+page.svelte`：金雞對比頁
- ✅ `frontend/src/lib/components/ComparePanel.svelte`：相關性熱圖

### 技術指標 UI（S17）
- ✅ `frontend/src/lib/components/IndicatorOverlay.svelte`
- ✅ `frontend/src/lib/components/RSIPanel.svelte`
- ✅ `frontend/src/lib/components/MACDPanel.svelte`
- ✅ `/signals/[code]` 頁：toolbar + RSI/MACD 子圖 + 指標訊號卡片

### 回測整合（S18）
- ✅ `api/schemas/simulation.py`：IndicatorCondition + EntryRule/ExitRule 擴充
- ✅ `api/services/backtest_engine.py`：check_indicator_condition()、indicator_exit 出場
- ✅ `api/services/simulation_service.py`：exit_reason_breakdown + strategy_type
- ✅ `frontend/src/lib/types.ts`：型別同步更新
- ✅ simulation/new：Step 3 技術指標條件 UI
- ✅ simulation/[id]：策略類型 badge + 出場原因分布

## Milestone 6 新增（S19–S23）

### 信用残 ingest（S19）
- ✅ `capystock/ingest/base.py`：IngestionSource ABC + IngestionResult
- ✅ `capystock/ingest/yahoo_jp_margin.py`：Yahoo Finance Japan 爬蟲
- ✅ `capystock/ingest/minkabu_margin.py`：Minkabu fallback 爬蟲
- ✅ `capystock/ingest/manual_csv.py`：多欄位別名 normalize + 單位自動轉換
- ✅ `api/schemas/ingest.py`：IngestionResult + CacheStatus + IngestStatusResponse
- ✅ `api/services/ingest_service.py`：fallback chain + cache 管理
- ✅ `api/routers/ingest.py`：POST /ingest/margin/{code}, /flow/{code}, /upload, GET /status/{code}

### JPX flow ingest（S20）
- ✅ `capystock/ingest/jpx_flow.py`：JPX Excel 下載 + 解析 + 個股估算
- ✅ `api/routers/ingest.py`：POST /ingest/jpx-weekly, GET /ingest/market-flow

### 異常偵測 + 事件研究（S21）
- ✅ `api/schemas/analytics.py`：AnomalyEvent + EventStudyResult
- ✅ `api/services/anomaly_service.py`：volume_spike / price_jump / gap_up / gap_down
- ✅ `api/services/event_study_service.py`：AR / AAR / CAR 計算
- ✅ `api/routers/analytics.py`：GET /analytics/anomaly/{code}, POST /analytics/event-study/{code}

### 策略參數 Sweep（S22）
- ✅ `api/schemas/sweep.py`：ParamGrid / SweepRequest / SweepResult / SweepRow
- ✅ `api/services/strategy_sweep_service.py`：笛卡兒積 + 並行 ProcessPoolExecutor
- ✅ `api/routers/sweep.py`：POST /sweep/run, GET /{job_id}, GET /{job_id}/stream, DELETE /{job_id}
- ✅ `frontend/src/routes/simulation/sweep/+page.svelte`：熱圖 + 排行榜

### 資料管理面板（S23）
- ✅ `api/routers/data.py`：GET /data/overview, POST /data/batch-ingest, SSE stream
- ✅ `frontend/src/routes/data/+page.svelte`：cache 狀態總覽（顏色警示）
- ✅ `frontend/src/routes/data/ingest/+page.svelte`：批量抓取 + SSE 進度
- ✅ `frontend/src/routes/data/upload/+page.svelte`：拖拉上傳 + 預覽

## 核心 / EDINET / 基本面（pre-S1）

### 核心功能
- ✅ `add` / `remove` / `list`：追蹤清單管理（`storage.py`）
- ✅ `check`：股價爬取（kabutan 主 + yfinance 備援）、持倉出場三選二判斷、停損偵測、吃貨訊號，整合 EDINET 申報（`scraper.py` + `analyzer.py`）
- ✅ `log`：歷史警示讀取（`data/log.csv`）

### EDINET 整合（2026-04-24 新增）
- ✅ `edinet`：金融廳官方 API，自動抓大量保有報告書（350）與変更報告書（360）
  - edinetCode → 証券コード 對照表：自動下載官方 `Edinetcode.zip`（3,697 家），快取 `data/cache/edinet/`
  - `check` 預設回掃 3 日；`--edinet-days N` 可調、`--no-edinet` 可關
  - key 設定：`data/.env` → `EDINET_API_KEY=...`

### 基本面分析
- ✅ `fundamental`：IR Bank 8 指標評分（`fundamental.py`）
  - 指標：Sales / EPS / Op. Margin / Equity Ratio / Operating CF / Cash / DPS / Payout Ratio
  - 評等：STRONG / HEALTHY / CAUTION / RISKY
  - 快取：`data/cache/{CODE}_fundamental.csv`（TTL 24h）

## CLI 操作
```bash
python -m capystock.main add 7203 2500
python -m capystock.main remove 7203
python -m capystock.main check [--code CODE] [--edinet-days N] [--no-edinet]
python -m capystock.main edinet [--days 7] [--all]
python -m capystock.main log [--days 30]
python -m capystock.main list
python -m capystock.main fundamental 7203
```
