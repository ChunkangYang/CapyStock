# Sprint 1 — Backend API 骨架 + 既有功能 service 化

依賴：[MILESTONE_03.md](MILESTONE_03.md)

## 目的
把 `capystock/` 內 CLI command 的 side effect 抽乾淨，供 API 重用。

## 檔案
- `requirements.txt`：新增 `fastapi`, `uvicorn[standard]`, `pydantic>=2.0`, `pyarrow`（parquet）
- `api/main.py`、`api/deps.py`、`api/schemas/common.py`
- `api/services/signal_service.py`、`api/services/dividend_service.py`
- `api/routers/meta.py`、`api/routers/watchlist.py`、`api/routers/signals.py`、`api/routers/dividend.py`

## Service 抽取規則
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

## Pydantic Schema（schemas/signals.py 摘錄）

```python
class PriceBar(BaseModel):
    date: date
    open: float; high: float; low: float; close: float
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
    start_price: float | None
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

## Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/health` | `{"status": "ok", "version": "..."}` |
| GET | `/api/v1/watchlist` | 列出持倉追蹤 |
| POST | `/api/v1/watchlist` | body `{code, start_price}`；回傳完整 entry |
| DELETE | `/api/v1/watchlist/{code}` | 移除 |
| GET | `/api/v1/signals` | 全 watchlist 的訊號分析 |
| GET | `/api/v1/signals/{code}` | 單檔訊號 + 完整快照 |
| GET | `/api/v1/signals/{code}/price?days=90` | K 線資料 |
| GET | `/api/v1/signals/{code}/flow?days=30` | 法人買賣超 |
| GET | `/api/v1/signals/{code}/margin?weeks=12` | 信用残 |
| GET | `/api/v1/signals/{code}/edinet?days=30` | EDINET 事件 |
| GET | `/api/v1/dividend/{code}` | 基本面 8 指標報告 |
| GET | `/api/v1/dividend/{code}/series` | 各指標時序 |

## 驗收（自動化）
- `pytest tests/unit/test_signal_service.py tests/unit/test_dividend_service.py -v` 全綠
- `pytest tests/api/test_watchlist_router.py tests/api/test_signals_router.py tests/api/test_dividend_router.py -v` 全綠
- 覆蓋率：`api/services/` + `api/routers/` ≥ 80%
- 確認測試**完全不發任何外部 HTTP 請求**
- 既有 CLI smoke 不可破壞 `capystock/main.py`
