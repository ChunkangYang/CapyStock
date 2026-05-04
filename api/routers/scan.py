import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.schemas.scan import DividendScanRow, JobStatus, SignalScanRow, ScanRunRequest, SnapshotMeta
from api.services import scan_service

router = APIRouter()

# In-memory job registry
jobs_registry: dict[str, JobStatus] = {}


@router.get("/scan/snapshots")
def get_snapshots(kind: Optional[str] = None) -> list[SnapshotMeta]:
    """列出所有可用快照"""
    snapshots = scan_service.list_snapshots(kind)
    return [SnapshotMeta(**s) for s in snapshots]


@router.get("/scan/signals")
def get_signals_snapshot(date: Optional[str] = None) -> list[SignalScanRow]:
    """讀訊號快照（缺省最新）"""
    df = scan_service.load_latest_snapshot("signals", date)
    if df is None:
        raise HTTPException(status_code=404, detail="No snapshot found")

    rows = []
    for _, row in df.iterrows():
        rows.append(
            SignalScanRow(
                code=row["code"],
                name=row["name"],
                latest_price=float(row["latest_price"]) if row["latest_price"] is not None else None,
                has_accumulation=bool(row["has_accumulation"]),
                has_exit=bool(row["has_exit"]),
                has_stop_loss=bool(row["has_stop_loss"]),
                edinet_recent_count=int(row["edinet_recent_count"]),
                score=int(row["score"]),
                generated_at=row["generated_at"],
            )
        )

    return rows


@router.get("/scan/dividend")
def get_dividend_snapshot(
    date: Optional[str] = None,
    min_yield: Optional[float] = None,
    overall: Optional[str] = None,
    order_by: Optional[str] = None,
    desc: Optional[bool] = None,
) -> list[DividendScanRow]:
    """讀配息快照（含篩選排序）"""
    df = scan_service.load_latest_snapshot("dividend", date)
    if df is None:
        raise HTTPException(status_code=404, detail="No snapshot found")

    # 篩選：min_yield
    if min_yield is not None:
        df = df[(df["est_yield"].notna()) & (df["est_yield"] >= min_yield)]

    # 篩選：overall
    if overall is not None:
        overalls = [s.strip() for s in overall.split(",")]
        df = df[df["overall"].isin(overalls)]

    # 排序
    if order_by:
        descending = desc if desc is not None else False
        df = df.sort_values(order_by, ascending=not descending)

    rows = []
    for _, row in df.iterrows():
        rows.append(
            DividendScanRow(
                code=row["code"],
                name=row["name"],
                overall=row["overall"],
                pass_count=int(row["pass_count"]),
                warn_count=int(row["warn_count"]),
                fail_count=int(row["fail_count"]),
                latest_dps=float(row["latest_dps"]) if row["latest_dps"] is not None else None,
                dps_streak_no_cut=int(row["dps_streak_no_cut"]),
                est_yield=float(row["est_yield"]) if row["est_yield"] is not None else None,
                payout_avg=float(row["payout_avg"]) if row["payout_avg"] is not None else None,
                equity_ratio_latest=float(row["equity_ratio_latest"]) if row["equity_ratio_latest"] is not None else None,
                eps_growth=float(row["eps_growth"]) if row["eps_growth"] is not None else None,
                generated_at=row["generated_at"],
            )
        )

    return rows


@router.post("/scan/run")
def run_scan(req: ScanRunRequest, async_mode: bool = Query(False)) -> JobStatus:
    """觸發掃描；async_mode=true 背景跑，false 同步阻塞"""
    job_id = str(uuid.uuid4())

    if async_mode:
        # 背景跑
        status = JobStatus(
            job_id=job_id,
            kind=req.kind,
            status="running",
            message=None,
            started_at=datetime.now(),
            finished_at=None,
        )
        jobs_registry[job_id] = status
        # TODO: 實際背景工作（簡化先不實作，在 S8 加）
        return status

    else:
        # 同步阻塞
        try:
            universe = scan_service.load_universe()
            today_str = datetime.now().strftime("%Y-%m-%d")

            if req.kind == "signals":
                include_technical = req.include_technical if hasattr(req, "include_technical") else True
                rows, errors = scan_service.run_signals_scan(universe, include_technical=include_technical)
                scan_service.write_snapshot("signals", rows, today_str)
                if errors:
                    scan_service.write_errors("signals", errors, today_str)
            elif req.kind == "dividend":
                rows, errors = scan_service.run_dividend_scan(universe)
                scan_service.write_snapshot("dividend", rows, today_str)
                if errors:
                    scan_service.write_errors("dividend", errors, today_str)
            else:
                raise HTTPException(status_code=400, detail=f"Invalid kind: {req.kind}")

            status = JobStatus(
                job_id=job_id,
                kind=req.kind,
                status="completed",
                message=None,
                started_at=datetime.now(),
                finished_at=datetime.now(),
            )
            jobs_registry[job_id] = status
            return status

        except Exception as e:
            status = JobStatus(
                job_id=job_id,
                kind=req.kind,
                status="failed",
                message=str(e),
                started_at=datetime.now(),
                finished_at=datetime.now(),
            )
            jobs_registry[job_id] = status
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan/jobs/{job_id}")
def get_job_status(job_id: str) -> JobStatus:
    """查 job 狀態"""
    if job_id not in jobs_registry:
        raise HTTPException(status_code=404, detail="Job not found")

    return jobs_registry[job_id]
