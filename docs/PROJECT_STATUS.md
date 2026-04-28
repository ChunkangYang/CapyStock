# CapyStock — 專案進度

## 最後更新
2026-04-28（S16/S17/S18：比較模式、指標 UI、回測整合全部完成）

## 目前待做（下一步）
- ✅ **Milestone 3：Web UI（FastAPI + SvelteKit）** — 全部完成（S1–S8）— 詳見 [MILESTONE_03.md](MILESTONE_03.md)
- ✅ **Milestone 4：自動化、排程、通知** — 全部完成（S9–S13）— 詳見 [MILESTONE_04.md](MILESTONE_04.md)
  - ✅ S9：通知通道抽象（Email / LINE）
  - ✅ S10：通知規則 + digest / realtime 整合
  - ✅ S11：APScheduler 排程器 + daily_pipeline
  - ✅ S12：通知 / 排程設定 UI + 健康監控頁
  - ✅ S13：部署整合（Docker / Windows 服務） + 文件
- ✅ **Milestone 5：技術指標與分析增強**（S14–S18）— 全部完成 — 詳見 [MILESTONE_05.md](MILESTONE_05.md)
  - ✅ S14：RSI / MACD / 布林通道 / SMA / EMA 引擎
  - ✅ S15：指標 API + scan score 融合
  - ✅ S16：比較模式 service（最多 5 檔）+ 對比頁前端
  - ✅ S17：前端技術指標 + 對比頁 UI（IndicatorOverlay / RSIPanel / MACDPanel）
  - ✅ S18：技術指標接入 simulation 引擎（indicator_entry/exit + AND/OR logic）
- [ ] **Milestone 6：資料源擴展 + 進階分析**（S19–S23）— 詳見 [MILESTONE_06.md](MILESTONE_06.md)
  - [ ] S19：信用残自動抓取（多來源 ingest 層）
  - [ ] S20：JPX 投資部門別週報 ingest
  - [ ] S21：異常偵測 + 事件研究
  - [ ] S22：策略參數 Sweep（網格回測）
  - [ ] S23：資料管理面板 + 上傳介面
- [ ] **Milestone 6：資料源擴展 + 進階分析**（S19–S23）— 詳見 [MILESTONE_06.md](MILESTONE_06.md)
  - [ ] S19：信用残自動抓取（多來源 ingest 層）
  - [ ] S20：JPX 投資部門別週報 ingest
  - [ ] S21：異常偵測 + 事件研究
  - [ ] S22：策略參數 Sweep（網格回測）
  - [ ] S23：資料管理面板 + 上傳介面

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
