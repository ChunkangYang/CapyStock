# Sprint 7 — 模擬交易引擎（後端）

依賴：[MILESTONE_03.md](MILESTONE_03.md)

## 模型核心概念

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
    initial_capital: float
    start_date: date
    end_date: date | None
    candidates: list[CandidateEntry]
    entry_rule: EntryRule
    exit_rule: ExitRule
    position_sizing: PositionSizing
    cost_model: CostModel

class CandidateEntry(BaseModel):
    code: str
    name: str
    entry_signal_date: date | None
    forced_entry_date: date | None

class EntryRule(BaseModel):
    price_basis: Literal["signal_close", "next_open", "user_specified"]
    user_price: float | None
    require_signal: bool = True

class ExitRule(BaseModel):
    use_exit_signal: bool = True
    use_stop_loss: bool = True
    take_profit_pct: float | None = None
    max_hold_days: int | None = None
    exit_price_basis: Literal["signal_close", "next_open"] = "next_open"

class PositionSizing(BaseModel):
    mode: Literal["equal_weight", "fixed_jpy", "fixed_shares"]
    fixed_jpy: float | None
    fixed_shares: int | None
    max_concurrent_positions: int = 10

class CostModel(BaseModel):
    commission_pct: float = 0.001
    slippage_pct: float = 0.001
    tax_pct: float = 0.20315
```

## State

```python
class Position(BaseModel):
    code: str; name: str
    entry_date: date; entry_price: float
    shares: int; cost_basis: float

class ClosedTrade(BaseModel):
    code: str; name: str
    entry_date: date; entry_price: float
    exit_date: date;  exit_price: float
    shares: int
    pnl_jpy: float; pnl_pct: float
    hold_days: int
    exit_reason: Literal["exit_signal", "stop_loss", "take_profit", "max_hold", "end_of_sim", "manual"]

class EquityPoint(BaseModel):
    date: date
    cash: float; market_value: float; equity: float

class SimulationState(BaseModel):
    cash: float
    positions: list[Position]
    closed_trades: list[ClosedTrade]
    equity_curve: list[EquityPoint]
    cursor_date: date
    pending_entries: list[CandidateEntry]
```

## 引擎演算法（pseudocode）

```python
def run_one_day(sim: Simulation, today: date) -> None:
    state = sim.state; cfg = sim.config
    # 1. 處理今日進場
    for cand in list(state.pending_entries):
        entry_date, entry_price = resolve_entry(cand, cfg.entry_rule, today)
        if entry_date is None or entry_date > today: continue
        if cfg.entry_rule.require_signal:
            snap = signal_service.analyze_one(cand.code)
            if not snap.accumulation_signal:
                state.pending_entries.remove(cand); continue
        if len(state.positions) >= cfg.position_sizing.max_concurrent_positions: break
        shares = compute_shares(entry_price, cfg.position_sizing, state.cash)
        if shares <= 0: continue
        cost = shares * entry_price * (1 + cfg.cost_model.commission_pct + cfg.cost_model.slippage_pct)
        if cost > state.cash: continue
        state.cash -= cost
        state.positions.append(Position(...))
        state.pending_entries.remove(cand)
    # 2. 處理出場
    for pos in list(state.positions):
        snap, alerts = signal_service.analyze_one_with_history(pos.code, as_of=today, start_price=pos.entry_price)
        reason = decide_exit(pos, snap, alerts, cfg.exit_rule, today)
        if reason:
            exit_price = resolve_exit_price(pos.code, today, cfg.exit_rule.exit_price_basis)
            close_position(state, pos, exit_price, today, reason, cfg.cost_model)
    # 3. 收盤後 mark-to-market
    market_value = sum(get_close(p.code, today) * p.shares for p in state.positions)
    state.equity_curve.append(EquityPoint(date=today, cash=state.cash, market_value=market_value, equity=state.cash+market_value))
    state.cursor_date = today
```

## Backtest vs Paper
- **Backtest**：呼叫 `run_one_day` 從 `start_date` 走到 `end_date`，全部用「歷史」資料。任何缺資料的日期 skip
- **Paper**：每日由 cron 呼叫 `POST /api/v1/simulation/{id}/advance`，推進到 `today`

## 檔案
- `api/services/simulation_service.py`
- `api/services/backtest_engine.py`（核心邏輯，與 paper 共用）
- `api/routers/simulation.py`
- `api/schemas/simulation.py`
- `api/workers/paper_worker.py`：`python -m api.workers.paper_worker`

## 持久化
- `data/simulations/{sim_id}.json`：完整 Simulation
- `data/simulations/{sim_id}_trades.csv`：append-only

## Endpoints

| Method | Path | 說明 |
|---|---|---|
| POST | `/api/v1/simulation` | 建立模擬（draft） |
| GET | `/api/v1/simulation` | 列表 |
| GET | `/api/v1/simulation/{id}` | 詳情 |
| PATCH | `/api/v1/simulation/{id}` | 修改（只在 draft） |
| POST | `/api/v1/simulation/{id}/run` | backtest：阻塞；paper：status=running |
| POST | `/api/v1/simulation/{id}/advance` | paper：推進到指定日期 |
| POST | `/api/v1/simulation/{id}/close-position` | 手動平倉 |
| POST | `/api/v1/simulation/{id}/add-candidate` | 新增候選 |
| GET | `/api/v1/simulation/{id}/report` | 計算彙總指標 |
| DELETE | `/api/v1/simulation/{id}` | 刪除 |

## 報告指標（`/report`）
- 期間：`start_date` ~ `cursor_date`
- 總報酬、年化、MDD、勝率、平均單筆 PnL%、平均持有天數、Profit Factor、各筆交易明細、權益曲線

## 驗收（自動化）

`pytest tests/unit/test_backtest_engine.py tests/unit/test_simulation_service.py tests/api/test_simulation_router.py -v` 全綠：

| # | 情境 | 預期 reason |
|---|------|------|
| 1 | 進場後股價跌破 -5% 連 2 日 | `stop_loss` |
| 2 | 進場後三選二觸發 | `exit_signal` |
| 3 | take_profit=0.10，股價 +10% | `take_profit` |
| 4 | max_hold_days=5，第 5 天仍無訊號 | `max_hold` |
| 5 | 走到 end_date 仍持有 | `end_of_sim` |
| 6 | 手動 close-position | `manual` |
| 7 | 進場日缺 price 資料 → skip | （不應進場） |
| 8 | 多檔同時進場、cash 不足 | 部分檔不進場且 candidates 保留 |
| 9 | `entry_rule.price_basis` 三種模式各一案 | 進場價符合 |
| 10 | paper：advance 兩次後 equity_curve 多兩點 | — |

關鍵：`backtest_engine` 內**完全不能呼叫 `datetime.now()` / `date.today()`**，所有時間從參數注入。
