# CapyStock — 專案進度

## 最後更新
2026-05-11（投機訊號頁：四個群組分離 - 全市場 / 我的最愛 / 我的持倉 / 追蹤清單）

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
- **下一步**：
  - ✅ SvelteKit SPA 路由 + 金雞/投機頁面 bug 修復（2026-05-04）
  - ✅ IMP-001：/watchlist 前端追蹤清單管理頁（2026-05-05）
  - ✅ 實時掃描進度（2026-05-10）
  - ✅ 投機訊號頁四個群組（2026-05-11）
  - 修復 BUG-001（toast 動畫 + channel dot 更新）
  - 評估是否規劃後續功能

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
