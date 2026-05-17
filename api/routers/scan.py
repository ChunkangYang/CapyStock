import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
import threading

from fastapi import APIRouter, HTTPException, Query

from api.deps import DATA_DIR
from api.schemas.scan import DividendScanRow, JobStatus, SignalScanRow, ScanRunRequest, SnapshotMeta
from api.services import scan_service

router = APIRouter()

# In-memory job registry
jobs_registry: dict[str, JobStatus] = {}
_registry_lock = threading.Lock()

# In-memory live-scan cache（單一 source of truth = data/cache/*.csv）
# key = CSV 目錄的最新 mtime；CSV 一變動就自動失效。
_live_signals_lock = threading.Lock()
_live_signals_state: dict = {"key": None, "rows": None, "errors": None, "at": None}


def _csv_mtime_key() -> float:
    """data/cache 內所有 .csv 的最新 mtime — 任一檔被寫入就會改變。"""
    cache_dir: Path = DATA_DIR / "cache"
    if not cache_dir.exists():
        return 0.0
    latest = 0.0
    for p in cache_dir.glob("*.csv"):
        try:
            m = p.stat().st_mtime
            if m > latest:
                latest = m
        except OSError:
            pass
    return latest


def _get_or_compute_live_signals() -> tuple[list[SignalScanRow], list[dict], datetime]:
    """即時計算全市場訊號；用 CSV mtime 當 cache key，CSV 變動自動失效。"""
    current_key = _csv_mtime_key()
    state = _live_signals_state
    if state["key"] == current_key and state["rows"] is not None:
        return state["rows"], state["errors"], state["at"]
    with _live_signals_lock:
        if _live_signals_state["key"] == current_key and _live_signals_state["rows"] is not None:
            return _live_signals_state["rows"], _live_signals_state["errors"], _live_signals_state["at"]
        universe = scan_service.load_universe()
        rows, errors = scan_service.run_signals_scan(universe)
        now = datetime.now()
        _live_signals_state.update({"key": current_key, "rows": rows, "errors": errors, "at": now})
        return rows, errors, now


@router.get("/scan/snapshots")
def get_snapshots(kind: Optional[str] = None) -> list[SnapshotMeta]:
    """列出所有可用快照"""
    snapshots = scan_service.list_snapshots(kind)
    return [SnapshotMeta(**s) for s in snapshots]


@router.get("/scan/signals")
def get_signals_snapshot(date: Optional[str] = None, limit: int = 50, offset: int = 0) -> dict:
    """取得訊號列表。

    - 不指定 date（預設）：**即時**從 data/cache/*.csv 算最新訊號，CSV 改動自動失效。
    - 指定 date=YYYY-MM-DD：讀歷史 parquet 快照（用於回溯）。
    """
    if date is None:
        # 即時計算路徑：唯一 source of truth = data/cache/*.csv
        rows_all, _errors, computed_at = _get_or_compute_live_signals()
        total = len(rows_all)
        rows_page = rows_all[offset:offset + limit]
        return {"data": rows_page, "total": total, "limit": limit, "offset": offset}

    # 歷史快照路徑：僅當使用者明確要看某天 parquet
    df = scan_service.load_latest_snapshot("signals", date)
    if df is None:
        raise HTTPException(status_code=404, detail="No snapshot found")

    total = len(df)
    df_page = df.iloc[offset:offset + limit]

    rows = []
    for _, row in df_page.iterrows():
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

    return {"data": rows, "total": total, "limit": limit, "offset": offset}


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


def _background_scan(job_id: str, req: ScanRunRequest):
    """背景掃描函數，邊掃邊更新快照"""
    try:
        universe = scan_service.load_universe()
        today_str = datetime.now().strftime("%Y-%m-%d")

        with _registry_lock:
            jobs_registry[job_id].progress_total = len(universe)

        if req.kind == "signals":
            include_technical = req.include_technical if hasattr(req, "include_technical") else True
            rows, errors = scan_service.run_signals_scan(
                universe,
                include_technical=include_technical,
                progress_callback=lambda curr: _update_progress(job_id, curr),
                snapshot_callback=lambda r, e: scan_service.write_snapshot("signals", r, today_str)
            )
            scan_service.write_snapshot("signals", rows, today_str)
            if errors:
                scan_service.write_errors("signals", errors, today_str)
        elif req.kind == "dividend":
            rows, errors = scan_service.run_dividend_scan(
                universe,
                progress_callback=lambda curr: _update_progress(job_id, curr),
                snapshot_callback=lambda r, e: scan_service.write_snapshot("dividend", r, today_str)
            )
            scan_service.write_snapshot("dividend", rows, today_str)
            if errors:
                scan_service.write_errors("dividend", errors, today_str)

        with _registry_lock:
            jobs_registry[job_id].status = "completed"
            jobs_registry[job_id].finished_at = datetime.now()
            jobs_registry[job_id].progress_current = len(universe)
    except Exception as e:
        with _registry_lock:
            jobs_registry[job_id].status = "failed"
            jobs_registry[job_id].message = str(e)
            jobs_registry[job_id].finished_at = datetime.now()


def _update_progress(job_id: str, current: int):
    """更新掃描進度"""
    with _registry_lock:
        if job_id in jobs_registry:
            jobs_registry[job_id].progress_current = current


@router.post("/scan/run")
def run_scan(req: ScanRunRequest, async_mode: bool = Query(True)) -> JobStatus:
    """觸發掃描；async_mode=true 背景跑，false 同步阻塞"""
    job_id = str(uuid.uuid4())

    if async_mode:
        # 背景跑 + 進度追蹤
        status = JobStatus(
            job_id=job_id,
            kind=req.kind,
            status="running",
            message=None,
            started_at=datetime.now(),
            finished_at=None,
            progress_current=0,
            progress_total=0,
        )
        with _registry_lock:
            jobs_registry[job_id] = status

        thread = threading.Thread(target=_background_scan, args=(job_id, req), daemon=True)
        thread.start()
        return status

    else:
        # 同步阻塞（已棄用）
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
                progress_current=len(universe),
                progress_total=len(universe),
            )
            with _registry_lock:
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
            with _registry_lock:
                jobs_registry[job_id] = status
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan/jobs/{job_id}")
def get_job_status(job_id: str) -> JobStatus:
    """查 job 狀態"""
    if job_id not in jobs_registry:
        raise HTTPException(status_code=404, detail="Job not found")

    return jobs_registry[job_id]
