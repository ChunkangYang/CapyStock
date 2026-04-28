"""Scheduler 相關 Pydantic models。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


JobStatus = Literal["running", "success", "failed", "timeout", "skipped"]


class JobDef(BaseModel):
    id: str
    name: str
    cron: str
    handler: str
    enabled: bool = True
    timeout_seconds: int = 1800
    max_instances: int = 1
    next_run_time: Optional[datetime] = None


class JobRun(BaseModel):
    run_id: str
    job_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: JobStatus = "running"
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    output_summary: Optional[str] = None


class JobUpdateRequest(BaseModel):
    cron: Optional[str] = None
    enabled: Optional[bool] = None
    timeout_seconds: Optional[int] = None
    max_instances: Optional[int] = None


class JobTriggerResponse(BaseModel):
    run_id: str
    job_id: str
    status: JobStatus
    started_at: datetime


class JobListResponse(BaseModel):
    jobs: list[JobDef] = Field(default_factory=list)


class JobRunListResponse(BaseModel):
    runs: list[JobRun] = Field(default_factory=list)
