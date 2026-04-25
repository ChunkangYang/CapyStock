# CapyStock — 專案進度

## 最後更新
2026-04-25（第十次工作：Milestone 3 Sprint 7 完成）

## 目前待做（下一步）
- [ ] **Milestone 3：Web UI（FastAPI + SvelteKit）** — 詳細設計見 `docs/MILESTONE_3_SPRINT_PLAN.md`
  - [x] S1 Backend API 骨架 + service 化
  - [x] S2 全市場掃描 worker + 每日快照
  - [x] S3 Favorites API
  - [x] S4 SvelteKit 前端骨架
  - [x] S5 進出場信號儀表板（投機）
  - [x] S6 金雞高股息儀表板
  - [x] S7 模擬交易引擎（backtest + paper）
  - [ ] S8 模擬交易 UI
- [ ] 自動寄發 email / LINE 通知
- [ ] 週末自動排程 cron
- [ ] 技術指標（RSI、MACD）輔助
- [ ] 信用残自動抓取（目前限免費來源，暫無穩定管道）

## 已完成功能

### Sprint 7：模擬交易引擎（2026-04-25 完成）
- ✅ `api/schemas/simulation.py`：完整的 Pydantic models
  - Simulation、SimulationConfig、SimulationState、Position、ClosedTrade 等
  - EntryRule、ExitRule、PositionSizing、CostModel 配置模型
  - SimulationReport 報告指標模型
- ✅ `api/services/backtest_engine.py`：核心演算法（無時間依賴）
  - `run_one_day()`：每日邏輯處理（進場→出場→mark-to-market）
  - `run_backtest()`：完整回測執行（start_date 走到 end_date）
  - `calculate_report_metrics()`：報告指標計算（報酬、年化、MDD、勝率等）
  - 支援三種進場規則（signal_close / next_open / user_specified）
  - 支援停損、止盈、最大持有天數、出場訊號等多重條件
- ✅ `api/services/simulation_service.py`：服務層（持久化 + CRUD）
  - `create()` / `get()` / `list_all()` / `delete()` — 基本 CRUD
  - `update_config()` / `add_candidate()` — 模擬設定修改（draft 專用）
  - `run_backtest()` / `advance_paper()` — 執行邏輯
  - `close_position()` — 手動平倉
  - `get_report()` — 報告生成
  - 原子寫入 JSON 確保並發安全
- ✅ `api/routers/simulation.py`：8 個 API endpoints
  - `POST /api/v1/simulation` — 建立
  - `GET /api/v1/simulation` — 列表
  - `GET /api/v1/simulation/{id}` — 詳情
  - `PATCH /api/v1/simulation/{id}` — 更新（draft）
  - `POST /api/v1/simulation/{id}/add-candidate` — 新增候選
  - `POST /api/v1/simulation/{id}/run` — 執行（backtest/paper）
  - `POST /api/v1/simulation/{id}/advance` — 推進（paper）
  - `POST /api/v1/simulation/{id}/close-position` — 手動平倉
  - `GET /api/v1/simulation/{id}/report` — 報告
  - `DELETE /api/v1/simulation/{id}` — 刪除
- ✅ `api/workers/paper_worker.py`：背景 worker
  - `python -m api.workers.paper_worker` — 推進所有執行中的 paper 模擬
- ✅ 自動化測試：
  - `tests/unit/test_backtest_engine.py` — 12 個單元測試（9 種確定性情境）
    - 停損 2 日連續觸發、end_of_sim、take_profit、max_hold、entry 缺資料 skip、多檔 cash 不足、進場價 3 模式
    - 邊界情況和指標計算
  - `tests/unit/test_simulation_service.py` — 20 個單元測試（CRUD、持久化、候選管理）
  - `tests/api/test_simulation_router.py` — 13 個 API 測試（endpoints、完整流程、錯誤處理）
  - 總計 45+ 單元測試全綠，覆蓋率 ≥ 80%

### Sprint 6：金雞高股息儀表板（2026-04-25 完成）
- ✅ `frontend/src/lib/components/RadarChart.svelte`：8 指標雷達圖（echarts）
  - 軸：Sales / EPS / OpMargin / Equity / OpCF / Cash / DPS / Payout
  - 數值 normalize：PASS=100, WARN=60, FAIL=20, N/A=0
- ✅ `frontend/src/lib/components/DividendBarChart.svelte`：配當歷史柱狀圖
  - 柱狀圖：DPS（藍）
  - 虛線：EPS（金）
- ✅ `frontend/src/routes/dividend/+page.svelte`：金雞清單頁
  - 篩選器：Overall / yield 最低 / 無減配年數 / 自己資本比 / 配當性向上限 / tag（最愛）
  - 表格：★ / Code / Name / Overall / DPS / Yield / 連無減配 / Payout avg / 自己資本比 / EPS growth / Pass-Warn-Fail stacked bar
  - 排序：預設 est_yield desc，可點 header 切換
- ✅ `frontend/src/routes/dividend/[code]/+page.svelte`：個股基本面詳細頁
  - 上方 header：code / name / overall tag / 收藏按鈕
  - 左欄：8 指標雷達圖 + 配當歷史圖表
  - 右欄：指標評分表（8 指標） + 統計摘要（PASS/WARN/FAIL 計數）
- ✅ 自動化測試：
  - `tests/unit/components/RadarChart.test.ts` — 10 個單元測試（score normalization、軸標籤、計數）
  - `tests/e2e/dividend.spec.ts` — 12 個 E2E 測試（篩選/排序/導航/詳細頁/收藏/截圖）
  - 單元測試全部通過；E2E 測試待環境配置（Playwright 瀏覽器需安裝）

### Sprint 5：進出場信號儀表板（投機）（2026-04-25 完成）
- ✅ `frontend/src/lib/components/KLineChart.svelte`：K 線圖表（lightweight-charts）
  - 日 K，60 日、起始價水平線（藍）、停損線（紅）、近 30 日低點（灰）
- ✅ `frontend/src/lib/components/FlowBarChart.svelte`：法人買賣超堆疊柱狀圖（echarts）
  - 三色：foreign / institution / individual
- ✅ `frontend/src/lib/components/MarginLineChart.svelte`：信用殘線圖
  - 融資 / 融券 + 倍率虛線
- ✅ `frontend/src/lib/components/SignalTimeline.svelte`：訊號時間軸
  - 色碼 alert 標記
- ✅ `frontend/src/lib/components/ConditionGauge.svelte`：三選二條件儀表
  - 三顆燈 + 計數器
- ✅ `frontend/src/lib/components/FavoriteToggle.svelte`：收藏按鈕
  - API 呼叫 + store 更新
- ✅ `frontend/src/lib/components/DataTable.svelte`：資料表格
  - 篩選（吃貨/出場/停損/min score）+ 排序（score/price/EDINET）
- ✅ `/signals` 列表頁：
  - tab 切換（全市場訊號 / 我的持倉 / 我的最愛）
  - DataTable 顯示資料
  - 點 row 跳轉詳細頁
- ✅ `/signals/[code]` 詳細頁：
  - 上方 header：code / name / 最新價 / ★ / 加入 watchlist / 加入模擬
  - 左欄 7：K線 + 法人 + 信用残 + 時間軸
  - 右欄 3：條件儀表 + 吃貨訊號 + 停損狀態 + EDINET + notes
- ✅ 自動化測試：
  - `tests/unit/components/KLineChart.test.ts` — 5 個單元測試
  - `tests/unit/components/FavoriteToggle.test.ts` — 6 個單元測試
  - `tests/e2e/signals.spec.ts` — 11 個 E2E 測試（載入/切換/跳轉/截圖）
  - 總計 22 個單元測試全綠

### Sprint 4：SvelteKit 前端骨架（2026-04-25 完成）
- ✅ `frontend/package.json`：SvelteKit + Vite + Vitest + Playwright
- ✅ `frontend/src/lib/api.ts`：fetch wrapper + ApiError 類別
- ✅ `frontend/src/lib/types.ts`：TypeScript 型別定義
- ✅ `frontend/src/lib/stores/favorites.ts`：最愛清單 store（load/add/remove/updateNote）
- ✅ `frontend/src/routes/+layout.svelte`：左側導覽（5 個主要頁面連結）
- ✅ `frontend/src/routes/+page.svelte`：Dashboard（三張卡片 + 資料載入）
- ✅ 骨架路由：
  - `/signals` 及 `[code]`
  - `/dividend` 及 `[code]`
  - `/favorites`
  - `/simulation`
- ✅ 自動化測試：
  - `tests/unit/api.test.ts` — 4 個單元測試（成功回應、4xx、5xx、RequestInit）
  - `tests/unit/stores/favorites.test.ts` — 7 個單元測試（load/add/remove/update/tag merge）
  - `tests/e2e/dashboard.spec.ts` — Playwright E2E 測試（導航、DOM 驗證、截圖回歸）
  - 總計 11 個單元測試全綠

### Sprint 3：Favorites API（2026-04-25 完成）
- ✅ `data/favorites.json`：我的最愛清單（分離於 watchlist）
- ✅ `api/schemas/favorites.py`：FavoriteEntry、FavoriteAddRequest、FavoriteUpdateRequest Pydantic models
- ✅ `api/services/favorite_service.py`：最愛服務
  - `load()` — 載入 favorites.json
  - `add(code, tag, name)` — 加入最愛（合併 tag、去重、固定排序）
  - `remove(code, tag=None)` — 移除最愛（可指定 tag）
  - `set_note(code, note)` — 設定備註
  - `list_favorites(tag=None)` — 列表（可選 tag 過濾）
  - 原子寫入（tempfile + replace）確保並發安全
- ✅ `api/routers/favorites.py`：4 個 favorites endpoints
  - `GET /api/v1/favorites?tag=...` — 列表（可選 tag 過濾）
  - `POST /api/v1/favorites` — 新增（body: code, tag, note?）
  - `PATCH /api/v1/favorites/{code}` — 更新（body: tags?, note?）
  - `DELETE /api/v1/favorites/{code}?tag=...` — 移除（可指定 tag）
- ✅ 自動化測試：
  - `tests/unit/test_favorite_service.py` — 15 個單元測試（add/remove/list/tag 管理、並發安全）
  - `tests/api/test_favorites_router.py` — 13 個 API 測試（全 4 個 endpoints）
  - 總計 28 個測試全綠，覆蓋率 97%

### Sprint 2：全市場掃描 worker + 每日快照（2026-04-25 完成）
- ✅ `data/universe.csv`：TOPIX Core30 約 30 檔股票清單
- ✅ `api/schemas/scan.py`：SignalScanRow、DividendScanRow、SnapshotMeta、JobStatus Pydantic models
- ✅ `api/services/scan_service.py`：掃描服務
  - `run_signals_scan(universe)` — 訊號掃描（score 計算）
  - `run_dividend_scan(universe)` — 配息掃描（殖利率計算）
  - `write_snapshot(kind, rows, date_str)` — 寫 parquet 快照
  - `load_latest_snapshot(kind, date_str)` — 讀快照
  - `list_snapshots(kind)` — 列出所有快照
  - `load_universe(path)` — 讀 universe.csv
- ✅ `api/routers/scan.py`：5 個 scan endpoints
  - `GET /api/v1/scan/signals?date=...` — 訊號快照
  - `GET /api/v1/scan/dividend?date=...&min_yield=...&overall=...&order_by=...&desc=...` — 配息快照（含篩選排序）
  - `GET /api/v1/scan/snapshots` — 列出快照日期
  - `POST /api/v1/scan/run` — 觸發掃描（同步/非同步）
  - `GET /api/v1/scan/jobs/{job_id}` — 查 job 狀態
- ✅ `api/workers/scan_worker.py`：CLI worker
  - `python -m api.workers.scan_worker --kind signals [--limit N]`
  - `python -m api.workers.scan_worker --kind dividend [--limit N]`
- ✅ 自動化測試：
  - `tests/unit/test_scan_service.py` — 10 個單元測試（確定性、覆寫、失敗容忍）
  - `tests/api/test_scan_router.py` — 9 個 API 測試（endpoints、篩選排序、job 管理）
  - 總計 19 個測試全綠，與 S1 合併覆蓋率 85.58% ≥ 80%

### Sprint 1：Backend API 骨架 + service 化（2026-04-25 完成）
- ✅ `api/main.py`：FastAPI app 入口，自動化路由註冊
- ✅ `api/services/signal_service.py`：純函式無副作用，供 API 複用
  - `analyze_one(code, start_price)` — 單檔訊號分析
  - `analyze_watchlist()` — 整清單分析
  - `get_price_history(code, days)` — K 線資料
  - `get_flow_history(code, days)` — 投資部門別
  - `get_margin_history(code, weeks)` — 信用殘
  - `get_edinet_events(code, days)` — EDINET 申報
- ✅ `api/services/dividend_service.py`：基本面分析服務
  - `get_fundamental_report(code)` — 8 指標報告
  - `get_dividend_history(code)` — 配當時序
- ✅ API endpoints（15 個）：
  - `/api/v1/health` — 健檢
  - `/api/v1/watchlist` — GET/POST/DELETE
  - `/api/v1/signals` — 列表 + 單檔分析
  - `/api/v1/signals/{code}/{price,flow,margin,edinet}` — 各類歷史資料
  - `/api/v1/dividend/{code}` — 基本面報告 + 時序
- ✅ 自動化測試：
  - `tests/unit/test_signal_service.py` — 8 個單元測試
  - `tests/unit/test_dividend_service.py` — 4 個單元測試
  - `tests/api/test_watchlist_router.py` — 5 個 API 測試
  - `tests/api/test_signals_router.py` — 7 個 API 測試
  - `tests/api/test_dividend_router.py` — 3 個 API 測試
  - 總計 27 個測試全綠，覆蓋率 82.73% ≥ 80%

### 核心功能
- ✅ `add` / `remove` / `list`：追蹤清單管理（`storage.py`）
- ✅ `check`：股價爬取（kabutan 主 + yfinance 備援）、持倉出場三選二判斷、停損偵測、吃貨訊號，同時整合 EDINET 申報（`scraper.py` + `analyzer.py`）
- ✅ `log`：歷史警示讀取（`data/log.csv`）

### EDINET 整合（2026-04-24 新增）
- ✅ `edinet`：金融廳官方 API，自動抓大量保有報告書（350）與変更報告書（360）
  - edinetCode → 証券コード 對照表：自動下載官方 `Edinetcode.zip`（3,697 家），快取 `data/cache/edinet/`
  - `check` 預設回掃 3 日並附帶顯示；`--edinet-days N` 可調、`--no-edinet` 可關
  - key 設定：`data/.env` → `EDINET_API_KEY=...`
  - 實測：7203 Toyota 過去 30 日查到 4 筆自己株買付申報

### 基本面分析（已存在）
- ✅ `fundamental`：IR Bank 8 指標評分（`fundamental.py`）
  - 指標：Sales / EPS / Op. Margin / Equity Ratio / Operating CF / Cash / DPS / Payout Ratio
  - 評等：STRONG / HEALTHY / CAUTION / RISKY
  - 快取：`data/cache/{CODE}_fundamental.csv`（TTL 24h）

## 已完成的程式碼
```
capystock/
├── __init__.py
├── config.py         — 參數設定（爬蟲、判斷邏輯閾值）
├── main.py           — CLI 入口（add/remove/check/log/list/edinet/fundamental）
├── scraper.py        — kabutan 爬蟲 + yfinance 備援 + 股票名稱
├── analyzer.py       — 持倉出場 / 停損 / 吃貨訊號判斷邏輯
├── storage.py        — watchlist.json + log.csv 讀寫 + 快取路徑
├── edinet.py         — EDINET API 5% rule 申報監控
└── fundamental.py    — IR Bank 基本面爬蟲 + 8 指標評分

api/                  # ★★ S1-S3 新增：FastAPI 服務層
├── main.py           — FastAPI app 入口 + 路由註冊
├── deps.py           — DI 與全域設定
├── schemas/
│   ├── common.py     — Pydantic 共用 models（WatchlistEntry, PriceBar, SignalResult 等）
│   ├── scan.py       — ★★ S2 新增（SignalScanRow, DividendScanRow, SnapshotMeta, JobStatus）
│   ├── favorites.py  — ★★ S3 新增（FavoriteEntry, FavoriteAddRequest, FavoriteUpdateRequest）
│   └── simulation.py  — ★★ S7 新增（Simulation, SimulationConfig, Position, ClosedTrade 等）
├── services/
│   ├── signal_service.py    — 訊號分析服務（抽自 CLI 邏輯）
│   ├── dividend_service.py  — 股息分析服務（基本面評分）
│   ├── scan_service.py      — ★★ S2 新增（掃描 + parquet I/O）
│   ├── favorite_service.py  — ★★ S3 新增（最愛 CRUD 服務）
│   ├── backtest_engine.py   — ★★ S7 新增（核心回測邏輯）
│   └── simulation_service.py — ★★ S7 新增（持久化 + CRUD）
├── routers/
│   ├── meta.py       — /health, /version endpoint
│   ├── watchlist.py  — 追蹤清單 CRUD API
│   ├── signals.py    — 訊號分析 API
│   ├── dividend.py   — 基本面分析 API
│   ├── scan.py       — ★★ S2 新增（掃描快照 + 觸發 endpoints）
│   ├── favorites.py  — ★★ S3 新增（最愛 API）
│   └── simulation.py  — ★★ S7 新增（模擬交易 8 endpoints）
└── workers/
    ├── scan_worker.py     — ★★ S2 新增（CLI worker for signals & dividend scan）
    └── paper_worker.py    — ★★ S7 新增（背景推進 paper 模擬）

frontend/             # ★★ S4-S5 新增：SvelteKit 前端
├── package.json
├── svelte.config.js
├── vite.config.ts
├── vitest.config.ts
├── playwright.config.ts
├── tsconfig.json
├── src/
│   ├── app.html
│   ├── lib/
│   │   ├── api.ts              — fetch wrapper + ApiError
│   │   ├── types.ts            — TypeScript 型別（PriceBar, FlowRow, SignalResult 等）
│   │   ├── components/         — ★★ S5-S6 新增
│   │   │   ├── KLineChart.svelte
│   │   │   ├── FlowBarChart.svelte
│   │   │   ├── MarginLineChart.svelte
│   │   │   ├── SignalTimeline.svelte
│   │   │   ├── ConditionGauge.svelte
│   │   │   ├── FavoriteToggle.svelte
│   │   │   ├── DataTable.svelte
│   │   │   ├── RadarChart.svelte            — ★★ S6 新增
│   │   │   └── DividendBarChart.svelte      — ★★ S6 新增
│   │   └── stores/
│   │       └── favorites.ts    — 最愛清單 store
│   └── routes/
│       ├── +layout.svelte      — 主導覽
│       ├── +page.svelte        — Dashboard
│       ├── signals/            — ★★ S5 新增實裝
│       │   ├── +page.svelte    — 列表頁（tab/篩選/排序）
│       │   └── [code]/+page.svelte — 詳細頁（四圖表+指標）
│       ├── dividend/            — ★★ S6 新增實裝
│       │   ├── +page.svelte    — 金雞清單（篩選/排序）
│       │   └── [code]/+page.svelte — 基本面詳細（雷達圖+配當表）
│       ├── favorites/+page.svelte
│       └── simulation/+page.svelte
└── tests/
    ├── unit/
    │   ├── api.test.ts
    │   ├── stores/favorites.test.ts
    │   └── components/         — ★★ S5-S6 新增
    │       ├── KLineChart.test.ts
    │       ├── FavoriteToggle.test.ts
    │       └── RadarChart.test.ts        — ★★ S6 新增
    └── e2e/
        ├── dashboard.spec.ts
        ├── signals.spec.ts    — ★★ S5 新增
        └── dividend.spec.ts   — ★★ S6 新增

data/
├── watchlist.json    — 追蹤清單
├── favorites.json    — ★★ S3 新增（我的最愛清單）
├── log.csv           — 警示歷史
├── universe.csv      — ★★ S2 新增（全股票清單）
└── scan_snapshots/   — ★★ S2 新增（parquet 快照目錄）

tests/                # ★★ S1-S3 新增：後端自動化測試（74 個測試，覆蓋率 87.81%）
├── conftest.py       — 共用 fixture
├── fixtures/         — ★★ S2 新增（universe_small.csv, price_7203.csv）
├── unit/
│   ├── test_signal_service.py
│   ├── test_dividend_service.py
│   ├── test_scan_service.py        — ★★ S2 新增（10 個測試）
│   ├── test_favorite_service.py    — ★★ S3 新增（15 個測試）
│   ├── test_backtest_engine.py     — ★★ S7 新增（12 個測試）
│   └── test_simulation_service.py  — ★★ S7 新增（20 個測試）
└── api/
    ├── test_watchlist_router.py
    ├── test_signals_router.py
    ├── test_dividend_router.py
    ├── test_scan_router.py         — ★★ S2 新增（9 個測試）
    ├── test_favorites_router.py    — ★★ S3 新增（13 個測試）
    └── test_simulation_router.py   — ★★ S7 新增（13 個測試）
```

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
