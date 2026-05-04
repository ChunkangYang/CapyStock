"""Sweep（網格回測）相關 schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from api.schemas.simulation import SimulationConfig


class ParamGrid(BaseModel):
    """笛卡兒積參數網格，每欄位為 list[value]。"""
    stop_loss_pct: Optional[List[float]] = None
    take_profit_pct: Optional[List[float]] = None
    max_hold_days: Optional[List[int]] = None
    indicator_entry_combos: Optional[List[List[str]]] = None


class SweepRequest(BaseModel):
    base_config: SimulationConfig
    grid: ParamGrid
    metric: Literal["total_return", "sharpe", "profit_factor", "win_rate", "max_drawdown"] = "total_return"
    top_n: int = 20


class SweepRow(BaseModel):
    params: Dict[str, object]
    total_return: float
    annualized: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    n_trades: int


class SweepResult(BaseModel):
    job_id: str
    request: SweepRequest
    rows: List[SweepRow] = Field(default_factory=list)
    started_at: datetime
    finished_at: Optional[datetime] = None
    n_combinations: int
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"
    error: Optional[str] = None


class SweepJobStatus(BaseModel):
    job_id: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    progress: int = 0
    total: int = 0
    result: Optional[SweepResult] = None
