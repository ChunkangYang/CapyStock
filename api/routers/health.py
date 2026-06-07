"""System health aggregate API（S12）。

GET /api/v1/health/system — aggregate：
- worker heartbeat（healthcheck_ping 最近一次成功）
- 資料新鮮度（scan snapshots 最新日 / paper sim cursor 最舊）
- notification deliverability（過去 7 日成功率）
- disk usage（data/ 目錄）
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

from api.deps import DATA_DIR
from api.schemas.health import (
    DataFreshness,
    DeliverabilityPoint,
    DiskBreakdown,
    DiskUsage,
    SystemHealth,
    WorkerHeartbeat,
)
from api.services import notification_service as ns
from api.services import scheduler_service as ss

router = APIRouter()

_SNAPSHOT_RE = re.compile(r"^(signals|dividend)_(\d{4}-\d{2}-\d{2})\.parquet$")


def _heartbeat() -> WorkerHeartbeat:
    runs = ss.get_scheduler_service().list_runs(job_id="healthcheck_ping", days=2)
    last = next((r for r in runs if r.status == "success"), None)
    if last is None:
        return WorkerHeartbeat(job_id="healthcheck_ping", status="unknown")
    finished = last.finished_at or last.started_at
    delta = (datetime.utcnow() - finished).total_seconds()
    status = "ok" if delta <= 3600 else "stale"
    return WorkerHeartbeat(
        job_id="healthcheck_ping",
        last_success_at=finished,
        seconds_since=delta,
        status=status,
    )


def _freshness() -> DataFreshness:
    snapshots_dir = DATA_DIR / "scan_snapshots"
    sig_latest: Optional[date] = None
    div_latest: Optional[date] = None
    if snapshots_dir.exists():
        for f in snapshots_dir.iterdir():
            m = _SNAPSHOT_RE.match(f.name)
            if not m:
                continue
            kind, ds = m.group(1), m.group(2)
            try:
                d = date.fromisoformat(ds)
            except ValueError:
                continue
            if kind == "signals" and (sig_latest is None or d > sig_latest):
                sig_latest = d
            elif kind == "dividend" and (div_latest is None or d > div_latest):
                div_latest = d

    # 跟單帳本（ledger）持有中交易的最舊推進日，作為「模擬資料新鮮度」指標
    paper_oldest: Optional[date] = None
    try:
        from api.services import ledger_service
        for s in ledger_service.list_ledgers():
            lg = ledger_service.get_ledger(s.id)
            if lg is None:
                continue
            for t in lg.trades:
                if t.status != "open" or t.last_advanced_date is None:
                    continue
                if paper_oldest is None or t.last_advanced_date < paper_oldest:
                    paper_oldest = t.last_advanced_date
    except Exception:
        pass

    return DataFreshness(
        signals_latest_date=sig_latest,
        dividend_latest_date=div_latest,
        paper_oldest_cursor=paper_oldest,
    )


def _deliverability(days: int = 7) -> list[DeliverabilityPoint]:
    entries = ns.read_log(days=days)
    buckets: dict[date, list[bool]] = defaultdict(list)
    for e in entries:
        buckets[e.ts.date()].append(e.ok)
    today = date.today()
    out: list[DeliverabilityPoint] = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        bucket = buckets.get(d, [])
        total = len(bucket)
        ok = sum(1 for b in bucket if b)
        rate = (ok / total) if total else 0.0
        out.append(DeliverabilityPoint(date=d, total=total, ok=ok, success_rate=round(rate, 4)))
    return out


def _dir_size(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_file():
        try:
            return p.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in p.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def _disk() -> DiskUsage:
    breakdown: list[DiskBreakdown] = []
    if DATA_DIR.exists():
        for child in sorted(DATA_DIR.iterdir(), key=lambda x: x.name):
            if child.name.startswith("."):
                continue
            breakdown.append(DiskBreakdown(name=child.name, bytes=_dir_size(child)))
    total = sum(b.bytes for b in breakdown)
    return DiskUsage(total_bytes=total, breakdown=breakdown)


@router.get("/health/system", response_model=SystemHealth)
def system_health():
    return SystemHealth(
        generated_at=datetime.utcnow(),
        heartbeat=_heartbeat(),
        freshness=_freshness(),
        deliverability=_deliverability(7),
        disk=_disk(),
    )
