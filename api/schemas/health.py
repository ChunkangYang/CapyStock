"""Health monitor 相關 Pydantic models（S12）。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class WorkerHeartbeat(BaseModel):
    job_id: str
    last_success_at: Optional[datetime] = None
    seconds_since: Optional[float] = None
    status: str = "unknown"  # ok / stale / unknown


class DataFreshness(BaseModel):
    signals_latest_date: Optional[date] = None
    dividend_latest_date: Optional[date] = None
    paper_oldest_cursor: Optional[date] = None


class DeliverabilityPoint(BaseModel):
    date: date
    total: int
    ok: int
    success_rate: float


class DiskBreakdown(BaseModel):
    name: str
    bytes: int


class DiskUsage(BaseModel):
    total_bytes: int
    breakdown: list[DiskBreakdown] = Field(default_factory=list)


class SystemHealth(BaseModel):
    generated_at: datetime
    heartbeat: WorkerHeartbeat
    freshness: DataFreshness
    deliverability: list[DeliverabilityPoint] = Field(default_factory=list)
    disk: DiskUsage
