"""模擬交易 schema 定義。"""
from datetime import date
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IndicatorCondition(BaseModel):
    """技術指標條件。"""
    type: Literal[
        "rsi_oversold", "rsi_overbought",
        "macd_golden_cross", "macd_dead_cross",
        "sma_cross", "bb_breakout_up", "bb_breakout_down",
    ]
    params: dict = Field(default_factory=dict)


class _BaseModelWithDateSerialization(BaseModel):
    """支援日期序列化的基礎模型。"""
    model_config = ConfigDict(
        json_encoders={date: lambda v: v.isoformat()},
        ser_json_timedelta='float'
    )


class CandidateEntry(_BaseModelWithDateSerialization):
    """進場候選股票。"""
    code: str
    name: str
    entry_signal_date: Optional[date] = None
    forced_entry_date: Optional[date] = None


class EntryRule(_BaseModelWithDateSerialization):
    """進場規則。"""
    price_basis: Literal["signal_close", "next_open", "user_specified"] = "next_open"
    user_price: Optional[float] = None
    require_signal: bool = True
    indicator_entry: list[IndicatorCondition] = Field(default_factory=list)
    indicator_entry_logic: Literal["and", "or"] = "or"


class ExitRule(_BaseModelWithDateSerialization):
    """出場規則。"""
    use_exit_signal: bool = True
    use_stop_loss: bool = True
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_hold_days: Optional[int] = None
    exit_price_basis: Literal["signal_close", "next_open"] = "next_open"
    indicator_exit: list[IndicatorCondition] = Field(default_factory=list)
    indicator_exit_logic: Literal["and", "or"] = "or"


class PositionSizing(_BaseModelWithDateSerialization):
    """部位規模。"""
    mode: Literal["equal_weight", "fixed_jpy", "fixed_shares"] = "equal_weight"
    fixed_jpy: Optional[float] = None
    fixed_shares: Optional[int] = None
    max_concurrent_positions: int = 10


class CostModel(_BaseModelWithDateSerialization):
    """成本模型。"""
    commission_pct: float = 0.001
    slippage_pct: float = 0.001
    tax_pct: float = 0.20315


class SimulationConfig(_BaseModelWithDateSerialization):
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


class Position(_BaseModelWithDateSerialization):
    """未平倉部位。"""
    code: str
    name: str
    entry_date: date
    entry_price: float
    shares: int
    cost_basis: float  # entry_price * shares + commission


class ClosedTrade(_BaseModelWithDateSerialization):
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
        "exit_signal", "stop_loss", "take_profit", "max_hold", "end_of_sim", "manual", "indicator_exit"
    ]


class EquityPoint(_BaseModelWithDateSerialization):
    """權益曲線資料點。"""
    date: date
    cash: float
    market_value: float
    equity: float


class SimulationState(_BaseModelWithDateSerialization):
    """模擬狀態。"""
    cash: float
    positions: list[Position] = Field(default_factory=list)
    closed_trades: list[ClosedTrade] = Field(default_factory=list)
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    cursor_date: date
    pending_entries: list[CandidateEntry] = Field(default_factory=list)


class Simulation(_BaseModelWithDateSerialization):
    """完整模擬物件。"""
    id: str
    name: str
    kind: Literal["backtest", "paper"]
    created_at: str
    config: SimulationConfig
    state: SimulationState
    status: Literal["draft", "running", "completed", "failed"] = "draft"


class SimulationReport(_BaseModelWithDateSerialization):
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
    exit_reason_breakdown: dict[str, int] = Field(default_factory=dict)
    strategy_type: Literal["pure_signal", "signal_indicator", "pure_indicator"] = "pure_signal"
