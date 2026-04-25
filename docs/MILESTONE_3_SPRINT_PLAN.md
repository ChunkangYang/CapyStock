# Milestone 3 — Web UI（前端視覺化 + 模擬交易）詳細設計

> 本文件交付給 Sonnet / Haiku 作為實作藍本。每個 Sprint 含：目的、檔案產物、API/元件規格、驗收條件。
> 規劃決策（已確認）：
> - 技術棧：**FastAPI（後端）+ SvelteKit（前端）**
> - 模擬模式：**回測（backtest）+ 前進模擬（paper trading）兩者皆做**
> - 進場價規則：**使用者可選**（訊號當日收盤 / 隔日開盤 / 自訂價）

---

## 0. 整體架構

```
CapyStock/
├── capystock/                    # (現有) CLI / 業務邏輯核心
├── api/                          # ★新增 FastAPI 服務
│   ├── __init__.py
│   ├── main.py                   # FastAPI app 入口
│   ├── deps.py                   # DI（settings、storage path）
│   ├── schemas/                  # Pydantic models
│   │   ├── common.py
│   │   ├── signals.py
│   │   ├── dividend.py
│   │   ├── favorites.py
│   │   ├── simulation.py
│   │   └── scan.py
│   ├── routers/
│   │   ├── watchlist.py
│   │   ├── signals.py
│   │   ├── dividend.py
│   │   ├── favorites.py
│   │   ├── scan.py
│   │   ├── simulation.py
│   │   └── meta.py               # /health, /version
│   ├── services/                 # 把 capystock CLI 行為包成可重用服務
│   │   ├── signal_service.py
│   │   ├── dividend_service.py
│   │   ├── scan_service.py
│   │   ├── favorite_service.py
│   │   └── simulation_service.py
│   └── workers/
│       ├── scan_worker.py        # 全市場掃描（背景）
│       └── paper_worker.py       # 前進模擬每日推進
├── frontend/                     # ★新增 SvelteKit
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.ts
│   └── src/
│       ├── app.html
│       ├── lib/
│       │   ├── api.ts            # fetch wrapper
│       │   ├── stores/           # svelte stores（favorites, theme...）
│       │   ├── components/
│       │   │   ├── KLineChart.svelte         # lightweight-charts
│       │   │   ├── FlowBarChart.svelte       # echarts
│       │   │   ├── MarginLineChart.svelte
│       │   │   ├── SignalTimeline.svelte
│       │   │   ├── ConditionGauge.svelte
│       │   │   ├── RadarChart.svelte
│       │   │   ├── DividendBarChart.svelte
│       │   │   ├── FavoriteToggle.svelte
│       │   │   ├── StockCard.svelte
│       │   │   ├── DataTable.svelte
│       │   │   └── EquityCurveChart.svelte
│       │   └── types.ts
│       └── routes/
│           ├── +layout.svelte               # 主導覽
│           ├── +page.svelte                 # Dashboard
│           ├── signals/
│           │   ├── +page.svelte             # 訊號列表（投機）
│           │   └── [code]/+page.svelte      # 個股訊號詳細
│           ├── dividend/
│           │   ├── +page.svelte             # 金雞清單
│           │   └── [code]/+page.svelte      # 個股基本面詳細
│           ├── favorites/+page.svelte       # 我的最愛
│           └── simulation/
│               ├── +page.svelte             # 模擬列表
│               ├── new/+page.svelte         # 建立模擬
│               └── [id]/+page.svelte        # 模擬報告
├── data/
│   ├── watchlist.json            # (現有) 持倉追蹤
│   ├── log.csv                   # (現有)
│   ├── favorites.json            # ★新增
│   ├── scan_snapshots/           # ★新增 全市場掃描快照
│   │   ├── signals_YYYY-MM-DD.parquet
│   │   └── dividend_YYYY-MM-DD.parquet
│   ├── simulations/              # ★新增
│   │   ├── {sim_id}.json         # 模擬定義 + 結果
│   │   └── {sim_id}_trades.csv   # 交易紀錄
│   └── universe.csv              # ★新增 全上市股票代號清單（用於掃描）
└── docs/
    └── MILESTONE_3_SPRINT_PLAN.md (本文件)
```

### API base URL
- 開發：`http://localhost:8000`
- 前端 dev：`http://localhost:5173`，Vite proxy `/api → :8000`
- CORS：dev 階段允許 `localhost:5173`，prod 同源部署

### 命名前綴
所有 API 路由前綴 `/api/v1/`。

---

## Sprint 1 — Backend API 骨架 + 既有功能 service 化

### 目的
把 `capystock/` 內 CLI command 的 side effect 抽乾淨，供 API 重用。

### 檔案
- `requirements.txt`：新增 `fastapi`, `uvicorn[standard]`, `pydantic>=2.0`, `pyarrow`（parquet）
- `api/main.py`、`api/deps.py`、`api/schemas/common.py`
- `api/services/signal_service.py`、`api/services/dividend_service.py`
- `api/routers/meta.py`、`api/routers/watchlist.py`、`api/routers/signals.py`、`api/routers/dividend.py`

### Service 抽取規則
從 `main.py` 各 `cmd_*` 抽出純函式（不能 `print`、不能 `sys.exit`）：

```python
# api/services/signal_service.py
def analyze_one(code: str) -> SignalResult: ...
def analyze_watchlist() -> list[SignalResult]: ...
def get_price_history(code: str, days: int = 90) -> list[PriceBar]: ...
def get_flow_history(code: str, days: int = 30) -> list[FlowRow]: ...
def get_margin_history(code: str, weeks: int = 12) -> list[MarginRow]: ...
def get_edinet_events(code: str, days: int = 30) -> list[EdinetEvent]: ...
```

```python
# api/services/dividend_service.py
def get_fundamental_report(code: str) -> FundamentalReport: ...
def get_dividend_history(code: str) -> list[DpsRow]: ...
```

### Pydantic Schema（schemas/signals.py 摘錄）

```python
class PriceBar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float  # 千株

class FlowRow(BaseModel):
    date: date
    foreign_net: float | None
    institution_net: float | None
    individual_net: float | None

class SignalConditions(BaseModel):
    cond_inst_sell: bool
    cond_margin_surge: bool
    cond_price_rise: bool
    matched: int  # 0..3

class Alert(BaseModel):
    alert_type: Literal["exit", "stop_loss", "accumulation", "info"]
    severity: Literal["info", "warn", "critical"]
    message: str
    details: dict

class SignalResult(BaseModel):
    code: str
    name: str
    latest_price: float | None
    latest_date: date | None
    start_price: float | None        # 來自 watchlist；不在 watchlist 為 null
    price_vs_start_pct: float | None
    price_vs_recent_low_pct: float | None
    conditions: SignalConditions
    stop_loss_triggered: bool
    accumulation_signal: bool
    flow_recent: list[float]
    margin_trend_note: str
    notes: list[str]
    alerts: list[Alert]
```

### Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/health` | `{"status": "ok", "version": "..."}` |
| GET | `/api/v1/watchlist` | 列出持倉追蹤 |
| POST | `/api/v1/watchlist` | body `{code, start_price}`；回傳完整 entry |
| DELETE | `/api/v1/watchlist/{code}` | 移除 |
| GET | `/api/v1/signals` | 全 watchlist 的訊號分析（用 `analyze_watchlist`） |
| GET | `/api/v1/signals/{code}` | 單檔訊號 + 完整快照 |
| GET | `/api/v1/signals/{code}/price?days=90` | K 線資料 |
| GET | `/api/v1/signals/{code}/flow?days=30` | 法人買賣超 |
| GET | `/api/v1/signals/{code}/margin?weeks=12` | 信用残 |
| GET | `/api/v1/signals/{code}/edinet?days=30` | EDINET 事件 |
| GET | `/api/v1/dividend/{code}` | 基本面 8 指標報告 |
| GET | `/api/v1/dividend/{code}/series` | 各指標時序（供圖表） |

### 驗收（自動化）
- `pytest tests/unit/test_signal_service.py tests/unit/test_dividend_service.py -v` 全綠
- `pytest tests/api/test_watchlist_router.py tests/api/test_signals_router.py tests/api/test_dividend_router.py -v` 全綠
- 覆蓋率：`api/services/` + `api/routers/` ≥ 80%
- 確認測試**完全不發任何外部 HTTP 請求**（`pytest -p no:cacheprovider --strict-markers` + 全域 mock requests）
- 既有 CLI smoke：`python -m capystock.main list` / `check --code 7203`（後者用 mock）能跑（不可破壞 `capystock/main.py`）

---

## Sprint 2 — 全市場掃描 worker + 每日快照

### 目的
- 投機面板需要「今天有訊號的股票」清單
- 金雞面板需要「全市場高股息排序」清單
- 線上即時掃描不可行（throttle 2s × 4000 檔）→ **離線 worker + parquet 快照**

### 檔案
- `data/universe.csv`：手工準備（先放 TOPIX Core30 / Prime 500 之類縮減清單；欄位 `code,name,market`）
- `api/workers/scan_worker.py`
- `api/services/scan_service.py`
- `api/routers/scan.py`
- `api/schemas/scan.py`

### Worker 行為

```
python -m api.workers.scan_worker --kind signals [--universe data/universe.csv] [--limit N]
python -m api.workers.scan_worker --kind dividend
```

#### signals scan
- 對 universe 每檔執行 `signal_service.analyze_one`
- 篩選條件：`alerts` 內含 `accumulation` **或** EDINET 350 新規（過去 N 日）
- 寫入 `data/scan_snapshots/signals_{YYYY-MM-DD}.parquet`
  - 欄位：`code, name, latest_price, has_accumulation, has_exit, has_stop_loss, edinet_recent_count, score, generated_at`
  - `score` = 內部排序權重（吃貨 +3、EDINET 350 +2、EDINET 360 +1、出場 -2、停損 -3）

#### dividend scan
- 對 universe 每檔執行 `dividend_service.get_fundamental_report`
- 計算「估算殖利率」：用 `dps[最新]` / `latest_price`
- 寫入 `data/scan_snapshots/dividend_{YYYY-MM-DD}.parquet`
  - 欄位：`code, name, overall, pass_count, warn_count, fail_count, latest_dps, dps_streak_no_cut, est_yield, payout_avg, equity_ratio_latest, eps_growth, generated_at`

#### 失敗處理
- 任一檔失敗：寫入 `data/scan_snapshots/_errors_{kind}_{date}.csv`，繼續下一檔，不中斷
- worker 進度條：印出 `[i/N] code` 即可，不需 progress lib

### Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/scan/signals?date=YYYY-MM-DD` | 取訊號掃描快照（缺省= 最新一份） |
| GET | `/api/v1/scan/dividend?date=YYYY-MM-DD&min_yield=0.03&overall=STRONG,HEALTHY&order_by=est_yield&desc=true` | 金雞快照（含篩選排序） |
| GET | `/api/v1/scan/snapshots` | 列出可用快照日期 |
| POST | `/api/v1/scan/run` | body `{kind: "signals"|"dividend"}`；非同步觸發 worker（FastAPI BackgroundTasks），回 job_id；先簡化：同步阻塞回應，加 query `async=true` 才背景跑 |
| GET | `/api/v1/scan/jobs/{job_id}` | 查 job 狀態（in-memory dict，不持久化） |

### 驗收（自動化）
- `pytest tests/unit/test_scan_service.py tests/api/test_scan_router.py -v` 全綠
- 確定性測試：給 `tests/fixtures/universe_small.csv`（5 檔）+ mock service 回傳 → worker 跑完 parquet 內容欄位 / row 數 / 排序 / score 值精確相等
- 覆寫測試：同一日期跑兩次，parquet 不重複（檔案 mtime 變、row 數不變）
- 失敗容忍測試：5 檔中第 3 檔 raise，仍寫入其他 4 檔且 `_errors_*.csv` 含失敗那檔
- 篩選/排序測試：`GET /api/v1/scan/dividend?order_by=est_yield&desc=true&min_yield=0.03` 結果順序與篩選正確

---

## Sprint 3 — Favorites API + watchlist 整合

### 目的
- 「我的最愛」與 `watchlist.json`（持倉追蹤）**分離**：watchlist 是真有部位的、需要 start_price；favorites 只是觀察名單
- favorites 同時涵蓋「投機 / 金雞」兩類，用 tag 區分

### 資料結構（`data/favorites.json`）

```json
{
  "7203": {
    "code": "7203",
    "name": "トヨタ自動車",
    "tags": ["dividend"],
    "added_at": "2026-04-25T10:00:00",
    "note": "高配當+健全"
  },
  "9984": {
    "code": "9984",
    "name": "ソフトバンクG",
    "tags": ["speculative", "dividend"],
    "added_at": "2026-04-25T10:01:00",
    "note": ""
  }
}
```

### 檔案
- `api/services/favorite_service.py`：`load`, `add(code, tag)`, `remove(code, tag=None)`, `set_note(code, note)`, `list(tag=None)`
- `api/routers/favorites.py`
- `api/schemas/favorites.py`

### Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/favorites?tag=dividend` | 列出（可選 tag 過濾） |
| POST | `/api/v1/favorites` | body `{code, tag: "speculative"|"dividend", note?}`；已存在則合併 tag |
| PATCH | `/api/v1/favorites/{code}` | body `{tags?, note?}` |
| DELETE | `/api/v1/favorites/{code}?tag=speculative` | 移除單一 tag；無 tag 參數則整筆刪 |

### 驗收（自動化）
- `pytest tests/unit/test_favorite_service.py tests/api/test_favorites_router.py -v` 全綠
- 必測情境：
  - 同一檔同時加兩個 tag → JSON 內 tags 為 `["speculative", "dividend"]`（順序固定）
  - DELETE 帶 tag 只移除該 tag、剩 0 tag 時整筆刪除
  - 重複 add 不會產生重複 tag
  - PATCH note 不影響 tags
  - 並發安全：用 file lock 或 atomic write（測試以 monkeypatch 模擬中斷寫入仍能保留舊資料）

---

## Sprint 4 — SvelteKit 前端骨架

### 目的
建立可運行的前端基底，所有後續 Sprint 在此之上加頁面。

### 安裝
```
cd frontend
npm create svelte@latest .  # SvelteKit + TypeScript + ESLint + Prettier + Vitest + Playwright
npm i lightweight-charts echarts
npm i -D @sveltejs/adapter-static @testing-library/svelte @playwright/test
```

### 共用設施
- `src/lib/api.ts`：
  ```ts
  const BASE = import.meta.env.VITE_API_BASE || '/api/v1';
  export async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const r = await fetch(`${BASE}${path}`, init);
    if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
    return r.json();
  }
  ```
- `src/lib/types.ts`：對應後端 schema 的 TS 型別
- `src/lib/stores/favorites.ts`：載入後端後寫入 store，所有 `FavoriteToggle` 共用
- `vite.config.ts`：proxy `/api → http://localhost:8000`

### Layout
- `+layout.svelte`：左側欄導覽 `Dashboard / 投機訊號 / 金雞 / 我的最愛 / 模擬交易`
- 配色：暗色為主（金融工具慣例），主色 #4ade80（漲）/ #f87171（跌）
- 不引入 UI lib，CSS 自寫（檔案小、可控）

### Dashboard `/`
- 三張卡片：
  1. **持倉狀態**：watchlist 全部、最近 alert 數
  2. **今日訊號**：`scan/signals` 最新快照前 5 名 `score`
  3. **金雞 Top**：`scan/dividend` 排序前 5 名（est_yield desc）
- 一個「最近 EDINET 事件」列表（watchlist 內）

### 驗收（自動化）
- `npm run test:unit` 通過：
  - `api.test.ts`：成功路徑 / 4xx / 5xx 三種狀況
  - `stores/favorites.test.ts`：load / add / remove / 多 tag 行為
- `npm run test:e2e` 通過 `e2e/dashboard.spec.ts`：
  - 後端用 fixture data dir 啟動於 `:8000`
  - 訪問 `/`，斷言三張卡片 DOM 存在 + 內容文字符合 mock API 回傳
  - 點側欄四個連結，URL 路徑變化正確
  - 截圖 baseline 比對（`dashboard-default.png`）

---

## Sprint 5 — 進出場信號儀表板（投機）

### 路由
- `/signals`：列表頁
- `/signals/[code]`：個股詳細

### `/signals` 列表頁

#### 資料源
- 主表：`GET /api/v1/scan/signals`（最新快照）
- 上方切換 tab：
  - **全市場訊號**（scan/signals）
  - **我的持倉**（signals API）
  - **我的最愛**（favorites?tag=speculative → 對每檔取 signals）

#### 元件
- 篩選列：`只看吃貨` / `只看出場` / `只看停損` / `min score`
- `DataTable.svelte` 欄位：
  - ★（FavoriteToggle）/ Code / Name / Close / vs 起始 / vs 低點 / C1 / C2 / C3 / 訊號 icon / EDINET 計數 / Score
  - 點 row → 跳 `/signals/{code}`
- 排序：score / est_yield / 漲跌幅 / EDINET 數

### `/signals/[code]` 詳細頁

#### 上方 header
- Code / Name / 最新價 / 來源（kabutan/yfinance）/ ★ / 「加入 watchlist」按鈕（pop modal 輸入 start_price）/ 「加入模擬清單」按鈕（後設 sprint 8 用）

#### 主視覺（兩欄佈局，左 7 / 右 3）

**左欄（圖表）**：
1. **K 線圖**（KLineChart.svelte，lightweight-charts）
   - 日 K，60 日
   - 疊加：start_price 水平線（藍）、停損線 `start_price * 0.95`（紅）、近 30 日低點線（灰）
   - Marker：alert 出現的日期掛三角（紅=出場、橘=停損、綠=吃貨、紫=EDINET）
2. **法人買賣超 stacked bar**（FlowBarChart.svelte，echarts）
   - x 軸日期，y 軸正負（千株）
   - 三色：foreign / institution / individual
3. **信用残 line**（MarginLineChart.svelte）
   - x 週、y `margin_long` / `margin_short` 兩條線 + 倍率虛線
4. **訊號時間軸**（SignalTimeline.svelte）
   - 從 log.csv 撈該 code 全部歷史 alerts，水平時間軸

**右欄（指標）**：
- **三選二條件儀表**（ConditionGauge.svelte）：三顆燈 + 是否 ≥2/3
- **吃貨訊號**：是 / 否 + 條件描述
- **停損狀態**：是 / 否
- **EDINET 事件清單**：最近 30 日，含申報人/種類/PDF 連結
- **notes 區塊**：snapshot.notes

#### API 呼叫
- `GET /signals/{code}`
- `GET /signals/{code}/price?days=90`
- `GET /signals/{code}/flow?days=60`
- `GET /signals/{code}/margin?weeks=20`
- `GET /signals/{code}/edinet?days=30`

### 驗收（自動化）
- `npm run test:unit` 通過：
  - `KLineChart.test.ts`：給定 PriceBar[] 渲染後 canvas 存在、series 數量正確（含 start_price / 停損 / 低點三條線）
  - `FavoriteToggle.test.ts`：點擊 emit add/remove 事件且呼叫 API
- `npm run test:e2e` 通過 `e2e/signals.spec.ts`：
  - 列表頁載入後表格列數 = mock 快照 row 數
  - 點 row 跳轉 `/signals/7203`，URL 正確
  - 詳細頁四個圖表容器（K線 / 法人 / 信用残 / 時間軸）DOM 存在
  - 點 ★：斷言 POST `/api/v1/favorites` 被呼叫；reload 後 ★ 仍亮起
  - 訊號 icon 對應：用 mock 回三種訊號各一檔，斷言 icon 文字
  - 截圖回歸：列表頁 + 詳細頁各一張

---

## Sprint 6 — 金雞高股息儀表板

### 路由
- `/dividend`：清單
- `/dividend/[code]`：個股詳細

### `/dividend` 列表頁

#### 資料源
`GET /api/v1/scan/dividend`（最新 parquet）

#### 篩選器
- Overall：multi-check（STRONG / HEALTHY / CAUTION / RISKY）
- 估算殖利率最低值 slider（0–10%）
- 配當無減配年數最低值 slider（0–10）
- 自己資本比率 slider（0–80%）
- 配當性向上限 slider（10–100%）
- Tag：☆ 只看我的最愛

#### 表格欄位
- ★ / Code / Name / Overall（標籤色）/ DPS / Yield / 連續無減配 / Payout 平均 / 自己資本比 / EPS 成長 / Pass-Warn-Fail（迷你 stacked bar）

#### 排序
預設 est_yield desc；可點 header 切換

### `/dividend/[code]` 個股詳細

#### 上方 header
類似 signals 詳細頁

#### 主視覺
1. **8 指標雷達圖**（RadarChart.svelte）
   - 軸：Sales / EPS / OpMargin / Equity / OpCF / Cash / DPS / Payout
   - 數值 normalize 到 0–100：PASS=100, WARN=60, FAIL=20, N/A=0
2. **配當歷史 bar**（DividendBarChart.svelte）
   - 各年度 DPS（藍）+ EPS（虛線疊加）
3. **配當性向 vs EPS 折線**
   - 雙 y 軸：左 payout%、右 EPS
4. **指標明細 table**：metric / score / note（從 fundamental.report.metrics）
5. **比較模式按鈕**：選最多 3 檔，跳轉 `/dividend/compare?codes=7203,8058,9984`

#### 比較模式（option，可放到 Sprint 6 末端或之後）
- 路由 `/dividend/compare?codes=...`
- 雷達圖三色疊加；表格並排顯示

### 驗收（自動化）
- `npm run test:unit` 通過 `RadarChart.test.ts`：給定 8 指標分數渲染後軸標籤 + 數值 normalize 正確
- `npm run test:e2e` 通過 `e2e/dividend.spec.ts`：
  - 篩選器：拖 yield slider 後 URL `?min_yield=` 同步、表格 row 全部符合條件
  - 重整 URL → 篩選狀態保留
  - 排序：點 header → 表格第一列改變
  - 個股詳細：雷達圖 SVG/canvas 存在、配當 bar / payout 折線 DOM 存在、metric table row 數 = 8
  - 比較模式：選 3 檔跳 `/dividend/compare?codes=...`，雷達圖三條 series
  - 截圖回歸：列表（預設 + 篩選後） / 詳細 / 比較共 4 張

---

## Sprint 7 — 模擬交易引擎（後端）

### 模型核心概念

```
Simulation
├── id (uuid)
├── kind: "backtest" | "paper"
├── name
├── created_at
├── config: SimulationConfig
├── state: SimulationState
└── status: "draft" | "running" | "completed" | "failed"
```

```python
class SimulationConfig(BaseModel):
    kind: Literal["backtest", "paper"]
    initial_capital: float                 # JPY
    start_date: date                       # backtest 必填；paper = today
    end_date: date | None                  # backtest 必填；paper = null（不限）
    candidates: list[CandidateEntry]       # 使用者選的進場清單

    entry_rule: EntryRule
    exit_rule: ExitRule
    position_sizing: PositionSizing
    cost_model: CostModel

class CandidateEntry(BaseModel):
    code: str
    name: str
    entry_signal_date: date | None         # 哪天偵測到的訊號（資訊用）
    forced_entry_date: date | None         # 使用者強制進場日（None=照 entry_rule）

class EntryRule(BaseModel):
    price_basis: Literal["signal_close", "next_open", "user_specified"]
    user_price: float | None               # price_basis=user_specified 時必填
    require_signal: bool = True            # 是否需要當日仍有 accumulation 訊號才買；False=照進場日就買

class ExitRule(BaseModel):
    use_exit_signal: bool = True           # 三選二觸發即出
    use_stop_loss: bool = True             # 跌破 -5% 連 2 日
    take_profit_pct: float | None = None   # +X% 即出（None=不啟用）
    max_hold_days: int | None = None       # 持有天數上限
    exit_price_basis: Literal["signal_close", "next_open"] = "next_open"

class PositionSizing(BaseModel):
    mode: Literal["equal_weight", "fixed_jpy", "fixed_shares"]
    fixed_jpy: float | None                # mode=fixed_jpy
    fixed_shares: int | None               # mode=fixed_shares
    max_concurrent_positions: int = 10

class CostModel(BaseModel):
    commission_pct: float = 0.001          # 0.1% 雙邊
    slippage_pct: float = 0.001            # 0.1%
    tax_pct: float = 0.20315               # 賣出實現損益課稅；簡化先不影響權益曲線，只在報告顯示稅後
```

### State

```python
class Position(BaseModel):
    code: str
    name: str
    entry_date: date
    entry_price: float
    shares: int
    cost_basis: float                      # = entry_price * shares + commission

class ClosedTrade(BaseModel):
    code: str
    name: str
    entry_date: date; entry_price: float
    exit_date: date;  exit_price: float
    shares: int
    pnl_jpy: float                         # 實現損益（含手續費）
    pnl_pct: float
    hold_days: int
    exit_reason: Literal["exit_signal", "stop_loss", "take_profit", "max_hold", "end_of_sim", "manual"]

class EquityPoint(BaseModel):
    date: date
    cash: float
    market_value: float                    # 當日所有持倉的 close × shares
    equity: float                          # cash + market_value

class SimulationState(BaseModel):
    cash: float
    positions: list[Position]
    closed_trades: list[ClosedTrade]
    equity_curve: list[EquityPoint]
    cursor_date: date                      # 已處理到哪天（每日推進）
    pending_entries: list[CandidateEntry]  # 還沒進場的候選
```

### 引擎演算法（pseudocode）

```python
def run_one_day(sim: Simulation, today: date) -> None:
    state = sim.state
    cfg = sim.config

    # 1. 處理今日進場（pending_entries 中觸發條件達成的）
    for cand in list(state.pending_entries):
        entry_date, entry_price = resolve_entry(cand, cfg.entry_rule, today)
        if entry_date is None or entry_date > today:
            continue   # 還沒到進場日
        if cfg.entry_rule.require_signal:
            snap = signal_service.analyze_one(cand.code)
            if not snap.accumulation_signal:
                state.pending_entries.remove(cand); continue
        if len(state.positions) >= cfg.position_sizing.max_concurrent_positions:
            break
        shares = compute_shares(entry_price, cfg.position_sizing, state.cash)
        if shares <= 0:
            continue
        cost = shares * entry_price * (1 + cfg.cost_model.commission_pct + cfg.cost_model.slippage_pct)
        if cost > state.cash:
            continue
        state.cash -= cost
        state.positions.append(Position(...))
        state.pending_entries.remove(cand)

    # 2. 處理出場（每持倉跑 analyzer）
    for pos in list(state.positions):
        snap, alerts = signal_service.analyze_one_with_history(pos.code, as_of=today, start_price=pos.entry_price)
        reason = decide_exit(pos, snap, alerts, cfg.exit_rule, today)
        if reason:
            exit_price = resolve_exit_price(pos.code, today, cfg.exit_rule.exit_price_basis)
            close_position(state, pos, exit_price, today, reason, cfg.cost_model)

    # 3. 收盤後 mark-to-market 寫入 equity_curve
    market_value = sum(get_close(p.code, today) * p.shares for p in state.positions)
    state.equity_curve.append(EquityPoint(date=today, cash=state.cash, market_value=market_value, equity=state.cash+market_value))
    state.cursor_date = today
```

### Backtest vs Paper
- **Backtest**：呼叫 `run_one_day` 從 `start_date` 走到 `end_date`，全部用「歷史」資料（kabutan 已快取的 price.csv + flow.csv + margin.csv）。任何缺資料的日期 skip。
- **Paper**：每日由 cron 呼叫 `POST /api/v1/simulation/{id}/advance`，推進到 `today`。

### 檔案
- `api/services/simulation_service.py`
- `api/services/backtest_engine.py`（核心邏輯，與 paper 共用）
- `api/routers/simulation.py`
- `api/schemas/simulation.py`
- `api/workers/paper_worker.py`：`python -m api.workers.paper_worker` → 對所有 paper 模擬呼叫 advance

### 持久化
- `data/simulations/{sim_id}.json`：完整 Simulation（含 state）
- `data/simulations/{sim_id}_trades.csv`：append-only 交易紀錄（給 Excel 看）

### Endpoints

| Method | Path | 說明 |
|---|---|---|
| POST | `/api/v1/simulation` | 建立模擬（draft） |
| GET | `/api/v1/simulation` | 列表 |
| GET | `/api/v1/simulation/{id}` | 詳情（含 state）|
| PATCH | `/api/v1/simulation/{id}` | 修改 candidates / config（只在 draft） |
| POST | `/api/v1/simulation/{id}/run` | backtest：阻塞執行，完成回傳完整報告；paper：把 status 改 running |
| POST | `/api/v1/simulation/{id}/advance` | paper：推進到指定日期（缺省 today）|
| POST | `/api/v1/simulation/{id}/close-position` | body `{code, exit_price?, exit_date?}`：手動平倉 |
| POST | `/api/v1/simulation/{id}/add-candidate` | body `{code, forced_entry_date?}` |
| GET | `/api/v1/simulation/{id}/report` | 計算彙總指標（見下） |
| DELETE | `/api/v1/simulation/{id}` | 刪除 |

### 報告指標（`/report`）
- 期間：`start_date` ~ `cursor_date`
- 總報酬：`(equity_end - initial_capital) / initial_capital`
- 年化報酬：`(1+total)^(365/days) - 1`
- 最大回撤（MDD）：`max(peak - trough) / peak`
- 勝率：`win / total_closed`
- 平均單筆 PnL%、平均持有天數
- Profit Factor：sum(wins) / abs(sum(losses))
- 各筆交易明細（closed_trades）
- 權益曲線資料

### 驗收（自動化）

`pytest tests/unit/test_backtest_engine.py tests/unit/test_simulation_service.py tests/api/test_simulation_router.py -v` 全綠，且涵蓋下列確定性情境（每個情境給定固定 price 序列 → 預期 closed_trades 與 equity_curve **逐欄精確相等**，使用 `pytest.approx` 容忍浮點）：

| # | 情境 | 預期出場 reason |
|---|------|-----------------|
| 1 | 進場後股價跌破 -5% 連 2 日 | `stop_loss` |
| 2 | 進場後三選二觸發 | `exit_signal` |
| 3 | 設定 take_profit=0.10，股價 +10% | `take_profit` |
| 4 | 設定 max_hold_days=5，第 5 天仍無訊號 | `max_hold` |
| 5 | 走到 end_date 仍持有 | `end_of_sim` |
| 6 | 手動 close-position | `manual` |
| 7 | 進場日缺 price 資料 → skip 該日 | （不應進場） |
| 8 | 多檔同時進場、cash 不足 → 部分檔不進場且 candidates 保留 | — |
| 9 | `entry_rule.price_basis` 三種模式各一案 | 進場價符合 |
| 10 | paper：advance 兩次後 equity_curve 多兩點、cursor_date 推進 | — |

報告指標測試：給定 closed_trades 固定列表，驗 `total_return / annualized / mdd / win_rate / profit_factor` 計算結果與手算一致。

API 測試：建立 → run → report → close-position → delete 完整流程；不能在 draft 以外狀態 PATCH（回 409）。

關鍵：`backtest_engine` 內**完全不能呼叫 `datetime.now()` / `date.today()`**，所有時間從參數注入，否則測試非確定。

---

## Sprint 8 — 模擬交易 UI

### 路由
- `/simulation`：列表
- `/simulation/new`：建立精靈
- `/simulation/[id]`：執行 + 報告

### `/simulation` 列表
- 表格：Name / Kind / Status / 期間 / 初始資金 / 當前權益 / 報酬% / 操作（檢視 / 刪除）
- 右上「+ 新模擬」

### `/simulation/new` 三步驟精靈

**Step 1 — 基本設定**
- 名稱、類型（backtest / paper radio）
- 初始資金（JPY）
- backtest：選 start_date / end_date
- paper：start_date 預設 today，end_date 不選

**Step 2 — 候選股票**
- 兩種來源：
  - **從訊號掃描挑**：拉 `scan/signals`，預設只顯示 has_accumulation=true，使用者勾選
  - **從我的最愛挑**（tag=speculative）
  - **手動輸入** code list
- 每檔可額外設 `forced_entry_date`（預設由 entry_rule 決定）

**Step 3 — 規則設定**
- EntryRule：radio `signal_close / next_open / user_specified`（後者出現價格輸入框，per-code）+ `require_signal` checkbox
- ExitRule：所有欄位 form
- PositionSizing：mode 三選一，依 mode 顯示對應欄位
- CostModel：手續費 / 滑價 / 稅率（預設值帶好）
- 結尾「建立並執行」按鈕（backtest 直接跑、paper 建立草稿）

### `/simulation/[id]` 主頁

#### 上方
- 名稱 / 類型 / 期間 / status badge
- backtest completed：總報酬、年化、MDD、勝率 KPI 卡片
- paper running：今日權益、持倉數、現金
- 操作按鈕：`Advance Today`（paper）/ `Re-run`（backtest）/ `Delete`

#### 主視覺
1. **權益曲線 chart**（EquityCurveChart.svelte，lightweight-charts area）
   - 疊加 initial_capital 水平線、benchmark 可選（TOPIX，後續加）
2. **持倉表**：positions（目前未平倉）
3. **交易紀錄表**：closed_trades；可下載 CSV
4. **每筆交易條圖**：bar，藍正紅負，hover 顯示 code

#### 互動
- 持倉表每行有「手動平倉」按鈕 → 跳 modal 輸入價格 / 日期 → 呼叫 close-position
- 候選表每行可移除（draft 階段才能改）

### 驗收（自動化）

`npm run test:e2e` 通過 `e2e/simulation.spec.ts`：

1. **建立 backtest 流程**：
   - 訪問 `/simulation/new`，三步驟全部填完並送出
   - 等候完成（poll status 至 completed）
   - 跳轉 `/simulation/[id]`
   - 斷言：總報酬 KPI 文字 = API `/report` 回傳值（用 `toBeCloseTo`）
   - 點「下載 CSV」→ Playwright `page.waitForEvent('download')` → 讀檔 → 行數 = `closed_trades.length` + 1（header）
2. **paper 流程**：建立 paper → 點 Advance Today → 斷言 equity_curve series 多一點（ECharts option 內 data length 比較）
3. **手動平倉**：在持倉表點按鈕 → modal 輸入 → 提交 → 斷言該 row 從持倉表消失、closed_trades 表多一列、reason = `manual`
4. **錯誤處理**：建立模擬時故意送錯 config（缺 user_price）→ 斷言錯誤 toast 出現、不跳頁
5. **截圖回歸**：列表 / 新建三步 / 報告主頁共 5 張

---

## 跨 Sprint 共通約定

### 錯誤處理
- 後端 service 失敗 → raise `HTTPException(status_code=4xx/5xx, detail="...")`
- 前端 `api()` throw → 上層用 `try/catch`，畫面顯示 toast（自寫簡易 toast store）

### 日期格式
- 所有 API 出入皆 ISO 8601 字串（`2026-04-25`）
- 前端用原生 Date + `Intl.DateTimeFormat('ja-JP')`

### 測試（自動化為主，不依賴人工目視）

#### 測試檔案結構
```
tests/
├── conftest.py                      # 共用 fixture（mock DataFrame、tmp data dir、FastAPI TestClient）
├── fixtures/
│   ├── price_7203.csv               # 60 日真實 K 線快照（測試用，凍結資料）
│   ├── flow_7203.csv
│   ├── margin_7203.csv
│   ├── fundamental_7203.csv
│   └── universe_small.csv           # 5 檔股票的縮減 universe
├── unit/
│   ├── test_signal_service.py
│   ├── test_dividend_service.py
│   ├── test_favorite_service.py
│   ├── test_scan_service.py
│   ├── test_simulation_service.py
│   └── test_backtest_engine.py
├── api/
│   ├── test_watchlist_router.py
│   ├── test_signals_router.py
│   ├── test_dividend_router.py
│   ├── test_favorites_router.py
│   ├── test_scan_router.py
│   └── test_simulation_router.py
└── e2e/
    └── test_full_flows.py           # 用 Playwright 測完整使用者流程

frontend/
├── tests/
│   ├── unit/                        # vitest
│   │   ├── api.test.ts
│   │   ├── stores/favorites.test.ts
│   │   └── components/
│   │       ├── KLineChart.test.ts
│   │       ├── RadarChart.test.ts
│   │       └── FavoriteToggle.test.ts
│   └── e2e/                         # @playwright/test（與後端共用）
│       ├── signals.spec.ts
│       ├── dividend.spec.ts
│       ├── favorites.spec.ts
│       └── simulation.spec.ts
```

#### 後端測試規則

1. **隔離 data 目錄**：`conftest.py` 提供 `tmp_data_dir` fixture，monkeypatch `config.DATA_DIR` / `CACHE_DIR` / `WATCHLIST_PATH` / `LOG_PATH` 到 tmp，避免測試污染真實 `data/`
2. **禁止外部網路**：`autouse=True` fixture 用 `monkeypatch.setattr` 把 `requests.get` 設為丟錯，所有測試必須用 fixture CSV 餵 mock 資料；EDINET / kabutan / IR Bank scraper 全部走 mock
3. **FastAPI**：用 `from fastapi.testclient import TestClient`，每個 router 至少測 happy path + 一個 4xx 錯誤
4. **覆蓋率門檻**：`pytest --cov=api --cov-fail-under=80`
5. **判斷邏輯**：`backtest_engine` 必須有確定性測試（給定固定 price 序列，預期 equity_curve 與 closed_trades 完全相符）

#### 前端測試規則

1. **單元測試（vitest）**：
   - `lib/api.ts`：mock fetch，驗證 URL / payload / error handling
   - stores：驗證新增 / 移除 / persist 行為
   - 元件：用 `@testing-library/svelte`，給定 props 驗 DOM 輸出與事件 emit
2. **E2E 測試（Playwright）**：
   - 後端跑在 `:8000`（用 fixture data dir 啟動）、前端 `npm run preview` 跑在 `:4173`
   - `playwright.config.ts` 用 `webServer` 自動拉起兩端
   - 每個主要頁面：載入 → 取得資料 → 點互動元素 → 斷言 DOM/URL/網路請求
   - **截圖回歸**：`expect(page).toHaveScreenshot('signals-detail.png')`，第一次跑生 baseline，之後比對；視覺差 > 0.1% 失敗 → 不需人工看圖，CI 直接擋

#### CI 執行（本地等同 CI）

```bash
# 後端
pytest tests/ -v --cov=api --cov-fail-under=80

# 前端單元
cd frontend && npm run test:unit -- --run

# E2E（自動拉起 server）
cd frontend && npm run test:e2e
```

#### 每個 Sprint 必須附帶的測試（補進各 Sprint 驗收）

| Sprint | 測試產物 |
|---|---|
| S1 | `tests/unit/test_signal_service.py`、`tests/unit/test_dividend_service.py`、`tests/api/test_*_router.py`（watchlist/signals/dividend） |
| S2 | `tests/unit/test_scan_service.py`（給 5 檔 mock universe，跑完寫 parquet，讀回比對欄位）、`tests/api/test_scan_router.py` |
| S3 | `tests/unit/test_favorite_service.py`、`tests/api/test_favorites_router.py`（測 tag merge / 部分刪除） |
| S4 | `frontend/tests/unit/api.test.ts`、`stores/favorites.test.ts`、`e2e/dashboard.spec.ts`（首頁載入 + 三張卡片資料正確） |
| S5 | `e2e/signals.spec.ts`：列表 → 點 row → 詳細頁四張圖 canvas 存在 → ★ toggle → reload 後仍記得；含截圖回歸 |
| S6 | `e2e/dividend.spec.ts`：篩選器組合 → URL query 同步 → 重整後狀態保留；雷達圖 SVG/canvas 存在；比較模式 3 檔疊加 |
| S7 | `tests/unit/test_backtest_engine.py`：給定確定性 price 序列（fixture），驗 closed_trades / equity_curve / 報告指標**全部值精確相等**；至少 5 種情境（停損觸發、出場訊號、take_profit、max_hold、end_of_sim） |
| S8 | `e2e/simulation.spec.ts`：三步驟精靈完整走過 → backtest 跑完 → KPI 卡片數值與 API 回傳一致 → 下載 CSV 內容比對；paper Advance 後 equity 多一點 |

#### 確定性測試的關鍵
- backtest_engine 不應呼叫 `datetime.now()` / `date.today()` — 一律從參數注入 `as_of`
- scan_worker 內所有時間戳都從注入的 clock 取得，方便測試
- 任何測試需要的 mock CSV 必須 commit 進 `tests/fixtures/`，禁止測試時動態下載

### 開發指令
```
# 後端
uvicorn api.main:app --reload --port 8000

# 前端
cd frontend && npm run dev

# 全市場掃描
python -m api.workers.scan_worker --kind signals
python -m api.workers.scan_worker --kind dividend

# 推進 paper
python -m api.workers.paper_worker
```

### 測試指令（每個 Sprint 完成必跑全綠）
```
# 後端全部
pytest tests/ -v --cov=api --cov-fail-under=80

# 前端單元
cd frontend && npm run test:unit -- --run

# E2E（自動拉起前後端）
cd frontend && npm run test:e2e

# 一鍵全測（建議寫進 Makefile / npm script）
make test    # 或 npm run test:all
```

### 部署（之後可選）
- 前端 `npm run build` → adapter-static 輸出到 `frontend/build`
- 後端 mount static：`app.mount("/", StaticFiles(directory="frontend/build", html=True))`
- 單一 uvicorn 起整個服務

---

## 給實作者的順序建議

1. **S1 → S2 → S3**：純後端可獨立驗證（curl）
2. **S4**：前端骨架，後續每個 sprint 邊加頁
3. **S5、S6**：可平行（兩個前端頁面互不依賴）
4. **S7 → S8**：模擬交易最後做（依賴前面所有 service）

完成 S1–S6 已經能用前端瀏覽全部訊號 / 金雞 / 加最愛；S7–S8 是回測核心。
