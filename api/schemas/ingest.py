"""Ingest 相關 Pydantic schemas。"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, Optional

from pydantic import BaseModel


class IngestionResult(BaseModel):
    code: str
    kind: Literal["margin", "flow", "price"]
    source: str
    rows_fetched: int
    date_range: Optional[tuple[date, date]] = None
    written_path: Optional[str] = None
    ok: bool
    error: Optional[str] = None


class IngestRequest(BaseModel):
    force: bool = False


class CacheStatus(BaseModel):
    kind: Literal["margin", "flow", "price"]
    last_updated: Optional[date] = None
    age_days: Optional[int] = None
    last_source: Optional[str] = None
    exists: bool


class IngestStatusResponse(BaseModel):
    code: str
    statuses: list[CacheStatus]


class MarketFlowRow(BaseModel):
    week: str
    foreign_net: float
    institution_net: Optional[float] = None
    individual_net: Optional[float] = None
    estimated: bool = False


class JpxWeeklyRequest(BaseModel):
    week: Optional[str] = None
