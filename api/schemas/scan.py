from datetime import datetime
from pydantic import BaseModel


class SignalScanRow(BaseModel):
    code: str
    name: str
    latest_price: float | None
    has_accumulation: bool
    has_exit: bool
    has_stop_loss: bool
    edinet_recent_count: int
    score: int
    generated_at: datetime


class DividendScanRow(BaseModel):
    code: str
    name: str
    overall: str
    pass_count: int
    warn_count: int
    fail_count: int
    latest_dps: float | None
    dps_streak_no_cut: int
    est_yield: float | None
    payout_avg: float | None
    equity_ratio_latest: float | None
    eps_growth: float | None
    generated_at: datetime


class SnapshotMeta(BaseModel):
    date: str
    kind: str
    rows: int
    path: str


class JobStatus(BaseModel):
    job_id: str
    kind: str
    status: str
    message: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ScanRunRequest(BaseModel):
    kind: str
    include_technical: bool = True
