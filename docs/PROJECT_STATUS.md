# CapyStock — 專案進度

## 最後更新
2026-06-13（兩問題調查完成：① 頁面載入慢 ② 模擬交易「現價」與市場不同步 — 根因已證實、修法已設計，**待實作**，見下節）

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
  - **🔥 最優先：2026-06-13 兩問題修復**（修法已設計到實作粒度，見本文件頂部「2026-06-13 問題調查」節）
    - 問題① 頁面慢：Fix 1-A 掃描禁外網 → 1-B stale-while-revalidate → 1-C dividend 分頁 → 1-D mtime key TTL
    - 問題② 現價不同步：Fix 2-1 標示資料日期 → Fix 2-2 quote 即時報價端點
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
