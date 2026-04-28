# Milestone 6 — 資料源擴展 + 進階分析 詳細設計

> 本文件交付給 Sonnet / Haiku 作為實作藍本。每個 Sprint 含：目的、檔案產物、API/元件規格、驗收條件。
> 規劃決策（已確認）：
> - 信用残資料：**半自動 import**（Yahoo Finance Japan / Minkabu 爬蟲嘗試 + 手動 CSV 上傳兜底）。
> - 投資部門別：同上策略，使用 JPX 公開週報 PDF / Excel 解析。
> - 進階分析：**事件研究（event study）**、**異常成交量偵測**、**選股回測 sweep**。
> - 多帳戶：本 Milestone 不做（單使用者）。

---

## 0. 整體架構新增

```
CapyStock/
├── capystock/
│   └── ingest/                    # ★新增 資料引入層
│       ├── __init__.py
│       ├── base.py                # IngestionSource ABC
│       ├── yahoo_jp_margin.py     # Yahoo Japan 信用残爬蟲
│       ├── minkabu_margin.py      # Minkabu 備援
│       ├── jpx_flow.py            # JPX 週報投資部門別
│       └── manual_csv.py          # 手動上傳 CSV 解析（最後保險）
├── api/
│   ├── services/
│   │   ├── ingest_service.py      # ★新增 整合 ingest 來源 + 寫 cache
│   │   ├── event_study_service.py # ★新增
│   │   ├── anomaly_service.py     # ★新增 異常成交量 / 跳空
│   │   └── strategy_sweep_service.py  # ★新增 參數 sweep
│   ├── routers/
│   │   ├── ingest.py
│   │   ├── analytics.py           # event study / anomaly endpoints
│   │   └── sweep.py
│   └── schemas/
│       ├── ingest.py
│       ├── analytics.py
│       └── sweep.py
├── frontend/src/routes/
│   ├── data/                      # ★新增 資料管理
│   │   ├── +page.svelte
│   │   ├── ingest/+page.svelte
│   │   └── upload/+page.svelte
│   ├── analytics/                 # ★新增
│   │   ├── event-study/+page.svelte
│   │   └── anomaly/+page.svelte
│   └── simulation/sweep/+page.svelte
└── docs/
    └── MILESTONE_6_SPRINT_PLAN.md (本文件)
```

---

## Sprint 19 — 信用残自動抓取（多來源 ingest 層）

### 目的
- 降低使用者手動準備 `data/cache/{CODE}_margin.csv` 的負擔
- 當 source A 失敗自動 fallback 到 source B / C
- 永遠允許手動 CSV 上傳兜底

### 檔案
- `capystock/ingest/base.py`
- `capystock/ingest/yahoo_jp_margin.py`
- `capystock/ingest/minkabu_margin.py`
- `capystock/ingest/manual_csv.py`
- `api/services/ingest_service.py`
- `api/routers/ingest.py`
- `api/schemas/ingest.py`

### IngestionSource 抽象

```python
class IngestionResult(BaseModel):
    code: str
    kind: Literal["margin", "flow", "price"]
    source: str
    rows_fetched: int
    date_range: tuple[date, date]
    written_path: str | None
    ok: bool
    error: str | None

class IngestionSource(ABC):
    name: str
    kind: Literal["margin", "flow", "price"]
    @abstractmethod
    def fetch(self, code: str) -> pd.DataFrame: ...   # 標準化欄位
    @abstractmethod
    def health_check(self) -> bool: ...
```

### Yahoo Japan margin
- URL：`https://finance.yahoo.co.jp/quote/{CODE}.T/credit_balance`
- 解析表格 → 欄位 normalize 到 `week, margin_long, margin_short, ratio`（千株）
- robots.txt 遵守：USER_AGENT = `config.USER_AGENT`，request delay 2s

### Minkabu fallback
- URL：`https://minkabu.jp/stock/{CODE}/`（信用倍率區塊）

### Manual CSV
- 接受多種欄位命名 alias：`margin_long` / `融資残` / `Long`
- 自動轉單位（如果偵測到 「株」 而非「千株」）

### IngestService

```python
class IngestService:
    def __init__(self, sources_by_kind: dict[str, list[IngestionSource]]): ...

    def fetch_margin(self, code: str, force: bool=False) -> IngestionResult:
        """依序試 sources；第一個成功即停。force=True 時繞過 24h cache。"""

    def import_manual(self, code: str, kind: str, file_content: bytes) -> IngestionResult: ...

    def cache_age(self, code: str, kind: str) -> timedelta | None: ...
```

### Endpoints

| Method | Path | 說明 |
|---|---|---|
| POST | `/api/v1/ingest/margin/{code}` | body `{force?: false}`：抓取並回 result |
| POST | `/api/v1/ingest/flow/{code}` | 同上 |
| POST | `/api/v1/ingest/upload` | multipart `file`, form `code`, `kind`：手動上傳 |
| GET | `/api/v1/ingest/status/{code}` | 各 kind cache age + last source used |

### 驗收（自動化）

`pytest tests/unit/test_ingest_yahoo.py tests/unit/test_ingest_minkabu.py tests/unit/test_ingest_manual.py tests/unit/test_ingest_service.py tests/api/test_ingest_router.py -v`：

- Yahoo：mock response（fixture HTML）→ parse 後欄位 / 數值正確（千株單位轉換）
- Minkabu：同上
- Manual CSV：上傳 5 種不同欄位名 fixture → 全部 normalize 成標準欄位
- IngestService 失敗 fallback：Yahoo mock 拋 → 自動試 Minkabu → 成功；result.source = "minkabu"
- 全部失敗：result.ok=false、error 含每來源錯誤摘要
- API：upload 接收 file → 寫入 `data/cache/`、回 IngestionResult；force=true 時 mtime 更新

### 給實作者
- 爬蟲若 HTTP 403 → 印 warning 並回 ok=false（**不 raise**），讓 IngestService 試下一 source
- 任何 ingest 失敗都不應該讓 `signal_service.analyze_one` 整個失敗（既有「缺資料 skip 條件」邏輯保留）

---

## Sprint 20 — 投資部門別 ingest（JPX 週報）

### 目的
- JPX 每週四發佈「投資部門別売買状況」Excel
- 解析後寫入 `data/cache/{CODE}_flow.csv`（某些 source 給的是市場別，個股別需另解 — 實務上只能對 ETF 用）
- 個股 flow：fallback 用「等比例分配」估算 — 標 estimated=true，UI 上以虛線顯示

### 檔案
- `capystock/ingest/jpx_flow.py`
- `tests/fixtures/jpx_weekly_2026wXX.xlsx`

### 處理流程
1. 下載 `https://www.jpx.co.jp/markets/statistics-equities/investor-type/...`（最新一份）
2. `pandas.read_excel(sheet_name='総合')` → 取「外資」「個人」「投信」三大類週淨買賣（億日圓）
3. 寫入 `data/cache/_market_flow.csv`（不分個股）
4. 對個股：呼叫時若 `_flow.csv` 缺，用市場 flow × (個股成交額 / 市場成交額) 估算，標 estimated=true

### Endpoints

| Method | Path | 說明 |
|---|---|---|
| POST | `/api/v1/ingest/jpx-weekly` | 抓取最新週報；body `{week?: "2026-W17"}` |
| GET | `/api/v1/ingest/market-flow?weeks=12` | 市場層級 flow（給 dashboard 用） |

### 驗收
- Fixture xlsx → parse 後欄位齊全；億日圓單位
- 估算個股 flow：給定市場 = (1000, -500, 300) 億，個股佔 0.5% → 個股 = (5, -2.5, 1.5) 億
- API：抓取 JPX mock 後 `_market_flow.csv` 出現

---

## Sprint 21 — 異常偵測 + 事件研究

### 目的
- **異常成交量**：今日 volume > N × 過去 20 日均量 → 標記
- **異常價格波動**：今日 |return| > K × 20 日 std → 標記
- **事件研究**：給定一組事件日期（例：法說會、EDINET 5% 申報），計算 CAR (Cumulative Abnormal Return)

### 檔案
- `api/services/anomaly_service.py`
- `api/services/event_study_service.py`
- `api/routers/analytics.py`
- `api/schemas/analytics.py`

### Anomaly

```python
class AnomalyEvent(BaseModel):
    code: str
    date: date
    type: Literal["volume_spike", "price_jump", "gap_up", "gap_down"]
    value: float       # 倍率或 %
    threshold: float
    severity: Literal["info", "warn", "critical"]

class AnomalyService:
    def scan(self, code: str, days: int=90,
             volume_multiplier: float=3.0, price_sigma: float=2.5,
             gap_pct: float=0.05) -> list[AnomalyEvent]: ...
```

### Event Study

```python
class EventStudyResult(BaseModel):
    code: str
    events: list[date]
    window_days: tuple[int, int]   # (-5, +20)
    aar: list[float]               # average abnormal return per offset
    car: list[float]               # cumulative
    n_events: int
    benchmark: str                 # "TOPIX" or "self_mean"

class EventStudyService:
    def run(self, code: str, events: list[date], window: tuple[int,int]=(-5, 20),
            benchmark: Literal["TOPIX", "self_mean"]="self_mean") -> EventStudyResult:
        """
        AR_t = R_stock_t - R_benchmark_t
        AAR = mean over events
        CAR = cumsum(AAR)
        """
```

- benchmark `self_mean`：用該股票過去 60 日平均報酬
- benchmark `TOPIX`：需先有 `data/cache/_topix_price.csv`（暫先實作 self_mean，TOPIX 留 v2）

### Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/analytics/anomaly/{code}?days=90` | 列出異常事件 |
| POST | `/api/v1/analytics/event-study/{code}` | body `{events: [date], window?: [-5, 20]}` |

### 驗收（自動化）

`pytest tests/unit/test_anomaly_service.py tests/unit/test_event_study_service.py tests/api/test_analytics_router.py -v`：

- Anomaly：人工序列 20 日均量 = 100，第 21 日 = 400 → 觸發 volume_spike value=4.0
- Anomaly：缺資料天 → 不 raise、不誤報
- Event study：構造已知 AR 序列 → CAR 與手算逐 offset 相符
- 0 events → n_events=0，aar/car 空陣列
- API：錯誤 events 格式 → 422

---

## Sprint 22 — 策略參數 Sweep（網格回測）

### 目的
- 模擬交易目前一次只跑一組參數
- Sweep：給定參數網格 → 跑 N 組 backtest → 回傳排名 + 熱圖資料
- 用途：找最佳停損 % / take profit / max_hold_days

### 檔案
- `api/services/strategy_sweep_service.py`
- `api/routers/sweep.py`
- `api/schemas/sweep.py`
- `frontend/src/routes/simulation/sweep/+page.svelte`

### Schema

```python
class ParamGrid(BaseModel):
    """每欄位 list[value]；笛卡兒積"""
    stop_loss_pct: list[float] | None = None       # e.g. [0.03, 0.05, 0.07]
    take_profit_pct: list[float] | None = None
    max_hold_days: list[int] | None = None
    indicator_entry_combos: list[list[str]] | None = None  # 每組是一份 indicator type list

class SweepRequest(BaseModel):
    base_config: SimulationConfig    # 進場名單 / 期間 / 初始資金 共用
    grid: ParamGrid
    metric: Literal["total_return", "sharpe", "profit_factor", "win_rate", "max_drawdown"] = "total_return"
    top_n: int = 20

class SweepRow(BaseModel):
    params: dict
    total_return: float
    annualized: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    n_trades: int

class SweepResult(BaseModel):
    request: SweepRequest
    rows: list[SweepRow]            # 已依 metric desc 排序
    started_at: datetime
    finished_at: datetime
    n_combinations: int
```

### Service

```python
class StrategySweepService:
    def run(self, req: SweepRequest, on_progress: Callable[[int, int], None] | None=None) -> SweepResult:
        """
        1. 笛卡兒積展開 grid
        2. 對每組複製 base_config，覆蓋對應欄位
        3. 呼叫 backtest_engine.run_backtest（使用快取資料，不重抓）
        4. 收集 metrics → 排序
        """
```

### 性能限制
- combinations > 200 → 拒絕（422）；建議使用者收斂
- 預設使用 `concurrent.futures.ProcessPoolExecutor`，max_workers = `min(8, os.cpu_count())`
- 進度透過 SSE 回前端：`GET /api/v1/sweep/{job_id}/stream`

### Endpoints

| Method | Path | 說明 |
|---|---|---|
| POST | `/api/v1/sweep/run` | 啟動 job，回 `{job_id}` |
| GET | `/api/v1/sweep/{job_id}` | 查狀態 + 結果 |
| GET | `/api/v1/sweep/{job_id}/stream` | SSE 進度（completed / total / current_params） |
| DELETE | `/api/v1/sweep/{job_id}` | 取消 |

### Sweep UI

#### `/simulation/sweep`
- 參數網格表單：每欄位可輸入 list（chip input）
- 進場名單：與 `/simulation/new` Step 2 共用元件
- 「估算 N 組合」即時顯示
- 「執行」→ 進度條（SSE）+ 預估剩餘
- 完成顯示：
  - **熱圖**（2 維 sweep 時）：x = stop_loss, y = take_profit, 色 = total_return
  - **排行榜表格**：top_n
  - **點 row → 跳完整 simulation 詳情頁**（自動建一筆模擬保存結果）

### 驗收（自動化）

`pytest tests/unit/test_strategy_sweep_service.py tests/api/test_sweep_router.py -v`：

- 網格 stop_loss=[0.03,0.05] × take_profit=[0.10,0.15] = 4 組合 → rows 4 列
- 排序：metric=total_return desc，第 1 列 total_return ≥ 第 2 列
- 過大網格：500 組合 → 422
- 並行正確性：並行跑 4 組 vs 序列跑，rows 完全相同（含順序）
- SSE：模擬 mock 進度 → 收到 5 個事件依序 (0/4) (1/4) (2/4) (3/4) (4/4)
- DELETE 中途：剩餘任務不執行，status=cancelled

`npm run test:e2e` 通過 `e2e/sweep.spec.ts`：
1. `/simulation/sweep`：填三個欄位 → 「估算 N 組合」顯示 = 預期數
2. 執行 → 進度條動 → 完成顯示熱圖 + 表格
3. 點 top 1 → 跳 `/simulation/{id}`，配置欄位 = sweep 該組合
4. 截圖回歸：sweep 設定頁 + 結果頁 2 張

---

## Sprint 23 — 資料管理面板 + 上傳介面

### 目的
- 集中管理：使用者可以一頁看到「每檔股票 cache 何時更新、缺什麼」
- 補資料：批量觸發 ingest / 上傳

### 路由
- `/data`（總覽）
- `/data/ingest`（批量抓取）
- `/data/upload`（拖拉上傳）

### `/data` 總覽
- 表格：Code / Name / price 最新日期 / margin 最新週 / flow 最新日期 / fundamental 上次更新 / 操作（重抓 / 上傳）
- 顏色：> 7 日未更新 = 黃；> 30 日 = 紅
- 篩選：watchlist / favorites / 全部

### `/data/ingest`
- 多選 codes + 多選 kinds（margin / flow / fundamental / price）
- 「執行」→ SSE 進度
- 完成後表格：每 (code, kind) 一行，source / rows / ok / error

### `/data/upload`
- 拖拉區：接受 csv / xlsx
- 自動偵測 code（從檔名 `{CODE}_margin.csv` 或讓使用者選）
- 預覽前 10 列 + 欄位 mapping UI（dropdown：source col → 標準欄位）
- 確認後 `POST /ingest/upload`

### Endpoints
| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/data/overview?scope=watchlist` | 各 code 各 kind 的 cache 狀態 |
| POST | `/api/v1/data/batch-ingest` | body `{codes, kinds}`：批量觸發；回 job_id |
| GET | `/api/v1/data/batch-ingest/{job_id}/stream` | SSE |

### 驗收

`pytest tests/api/test_data_router.py -v`：
- overview 回每 code 4 個 kind，age_days 欄位
- batch-ingest 5 codes × 2 kinds = 10 task，全部成功；其中 1 個失敗仍繼續、result 標 ok=false

`npm run test:e2e` 通過 `e2e/data.spec.ts`：
1. `/data`：表格 row 數 = watchlist size；顏色驗證（mock 一檔 35 日舊 → 紅 cell）
2. `/data/ingest`：選 3 codes 1 kind → 執行 → SSE 進度 → 完成
3. `/data/upload`：拖拉 CSV → 預覽 10 列 → mapping → 上傳 → toast 成功
4. 截圖：`/data`、`/data/upload` 2 張

---

## 跨 Sprint 共通約定（沿用 M3 / M4 / M5，補充以下）

### 爬蟲倫理
- 任何新 source 都需 `time.sleep(REQUEST_DELAY_SECONDS)`
- USER_AGENT 一律 `config.USER_AGENT`（聲明用途 + 聯絡方式）
- robots.txt 違反者直接不實作

### 估算資料標記
- 任何「估算」資料（如部門別 flow 估算）必須在 schema 上有 `estimated: bool` 欄位
- UI 上虛線 / 角標 / tooltip 三重提示

### 並行
- 一律 `concurrent.futures.ProcessPoolExecutor`，避免 GIL 限制
- 子程序內不能讀全域 `Settings`，需透過 pickle-able 參數傳

---

## 順序建議
1. **S19 → S20**：ingest 層獨立可驗證
2. **S21**：分析服務（依賴 ingest 的資料完整性）
3. **S22**：sweep（依賴 simulation engine M3、indicator M5）
4. **S23**：資料 UI（最後做，依賴 S19/S20 API）

完成 M6 後：使用者不需要手動準備 CSV，可以做事件研究、找最佳參數，並掌握全 watchlist 資料新鮮度。

---

## Milestone 全圖

| Milestone | 主題 | Sprint 範圍 | 狀態 |
|---|---|---|---|
| M1 | CLI + 核心爬蟲 + EDINET | （pre-S1）| ✅ 已完成 |
| M2 | 基本面分析 fundamental | （pre-S1）| ✅ 已完成 |
| M3 | Web UI（FastAPI + SvelteKit）| S1–S8 | ✅ 已完成 |
| M4 | 自動化、排程、通知 | S9–S13 | 規劃中 |
| M5 | 技術指標 + 比較模式 | S14–S18 | 規劃中 |
| M6 | 資料源擴展 + 進階分析 | S19–S23 | 規劃中 |

往後若要再擴：
- **M7（候選）**：多帳戶 / 雲端部署 / 行動 App
- **M8（候選）**：機器學習選股（特徵工程 + 簡單模型）
- **M9（候選）**：選擇權 / 信用交易模擬
