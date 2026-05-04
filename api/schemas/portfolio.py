from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class LotIn(BaseModel):
    code: str
    entry_price: float
    quantity: int
    entry_date: Optional[str] = None
    note: str = ""


class CloseIn(BaseModel):
    exit_price: float


class PortfolioLot(BaseModel):
    id: str
    code: str
    name: str
    entry_price: float
    quantity: int
    entry_date: str
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    note: str = ""
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    return_pct: Optional[float] = None


class PortfolioEntry(BaseModel):
    code: str
    name: str
    lots: list[PortfolioLot]
    total_cost: float
    total_unrealized_pnl: Optional[float] = None
