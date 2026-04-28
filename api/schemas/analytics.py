"""Analytics 相關 Pydantic schemas。"""
from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel


class AnomalyEvent(BaseModel):
    code: str
    date: date
    type: Literal["volume_spike", "price_jump", "gap_up", "gap_down"]
    value: float
    threshold: float
    severity: Literal["info", "warn", "critical"]


class EventStudyRequest(BaseModel):
    events: List[date]
    window: Tuple[int, int] = (-5, 20)
    benchmark: Literal["self_mean"] = "self_mean"


class EventStudyResult(BaseModel):
    code: str
    events: List[date]
    window_days: Tuple[int, int]
    aar: List[float]
    car: List[float]
    n_events: int
    benchmark: str
