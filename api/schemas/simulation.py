"""模擬交易 schema 定義。"""
from datetime import date
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CandidateEntry(BaseModel):
    """進場候選股票。"""
    code: str
    name: str
    entry_signal_date: Optional[date] = None
    forced_entry_date: Optional[date] = None


class EntryRule(BaseModel):
    """進場規則。"""
    price_basis: Literal["signal_close", "next_open", "user_specified"] = "next_open"
    user_price: Optional[float] = None
    require_signal: bool = True


class ExitRule(BaseModel):
    """出場規則。"""
    use_exit_signal: bool = True
    use_stop_loss: bool = True
    take_profit_pct: Optional[float] = None
    max_hold_days: Optional[int] = None
    exit_price_basis: Literal["signal_close", "next_open"] = "next_open"


class PositionSizing(BaseModel):
    """部位規模。"""
    mode: Literal["equal_weight", "fixed_jpy", "fixed_shares"] = "equal_weight"
    fixed_jpy: Optional[float] = None
    fixed_shares: Optional[int] = None
    max_concurrent_positions: int = 10


class CostModel(BaseModel):
    """成本模型。"""
    commission_pct: float = 0.001
    slippage_pct: float = 0.001
    tax_pct: float = 0.20315


class SimulationConfig(BaseModel):
    """模擬設定。"""
    kind: Literal["backtest", "paper"]
    initial_capital: float
    start_date: date
    end_date: Optional[date] = None
    candidates: list[CandidateEntry] = Field(default_factory=list)
    entry_rule: EntryRule = Field(default_factory=EntryRule)
    exit_rule: ExitRule = Field(default_factory=ExitRule)
    position_sizing: PositionSizing = Field(default_factory=PositionSizing)
    cost_model: CostModel = Field(default_factory=CostModel)


class Position(BaseModel):
    """未平倉部位。"""
    code: str
    name: str
    entry_date: date
    entry_price: float
    shares: int
    cost_basis: float  # entry_price * shares + commission


class ClosedTrade(BaseModel):
    """已平倉交易。"""
    code: str
    name: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    shares: int
    pnl_jpy: float
    pnl_pct: float
    hold_days: int
    exit_reason: Literal[
        "exit_signal", "stop_loss", "take_profit", "max_hold", "end_of_sim", "manual"
    ]


class EquityPoint(BaseModel):
    """權益曲線資料點。"""
    date: date
    cash: float
    market_value: float
    equity: float


class SimulationState(BaseModel):
    """模擬狀態。"""
    cash: float
    positions: list[Position] = Field(default_factory=list)
    closed_trades: list[ClosedTrade] = Field(default_factory=list)
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    cursor_date: date
    pending_entries: list[CandidateEntry] = Field(default_factory=list)


class Simulation(BaseModel):
    """完整模擬物件。"""
    id: str
    name: str
    kind: Literal["backtest", "paper"]
    created_at: str
    config: SimulationConfig
    state: SimulationState
    status: Literal["draft", "running", "completed", "failed"] = "draft"


class SimulationReport(BaseModel):
    """模擬報告指標。"""
    id: str
    name: str
    kind: Literal["backtest", "paper"]
    status: Literal["draft", "running", "completed", "failed"]
    period_start: date
    period_end: date
    initial_capital: float
    final_equity: float
    total_return_pct: float
    annualized_return_pct: float
    max_drawdown_pct: float
    win_rate: Optional[float] = None
    avg_pnl_pct: Optional[float] = None
    avg_hold_days: Optional[int] = None
    profit_factor: Optional[float] = None
    total_trades: int
    winning_trades: int
    losing_trades: int
    closed_trades: list[ClosedTrade] = Field(default_factory=list)
    equity_curve: list[EquityPoint] = Field(default_factory=list)
