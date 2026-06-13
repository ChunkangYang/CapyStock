import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
import threading

import pandas as pd
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
# refreshing：是否有背景重算 in-flight（stale-while-revalidate）。
_live_signals_lock = threading.Lock()
_live_signals_state: dict = {"key": None, "rows": None, "errors": None, "at": None, "refreshing": False}


# mtime key 自身的短 TTL 快取：避免每個請求都 stat 11k+ 檔（實測 ~0.34 秒）。
# 60 秒內重用上次算出的 key；副作用是 CSV 變動最晚 60 秒後才反映（可接受，
# 因為 Fix 1-B 之後重算已非阻塞）。
_mtime_key_lock = threading.Lock()
_mtime_key_cache: dict = {"computed_ts": 0.0, "key": None}
_MTIME_KEY_TTL_SEC = 60.0


def _inputs_mtime_key() -> str:
    """涵蓋 run_signals_scan 的**所有輸入**的最新 mtime — 任一輸入變動就失效 cache。

    輸入有兩條來源：
    - data/cache/*.csv（cloud-sync 寫入；CSV 影響 analyze_one 的算出值）
    - data/watchlist.json（影響 start_price 注入；不納入會導致改 watchlist 後 stale）

    結果自身有 60 秒 TTL（_MTIME_KEY_TTL_SEC），省掉每請求對 11k+ 檔的 stat。
    """
    import time as _time
    now_ts = _time.time()
    with _mtime_key_lock:
        if (
            _mtime_key_cache["key"] is not None
            and now_ts - _mtime_key_cache["computed_ts"] < _MTIME_KEY_TTL_SEC
        ):
            return _mtime_key_cache["key"]

    cache_dir: Path = DATA_DIR / "cache"
    csv_max = 0.0
    if cache_dir.exists():
        for p in cache_dir.glob("*.csv"):
            try:
                m = p.stat().st_mtime
                if m > csv_max:
                    csv_max = m
            except OSError:
                pass
    wl_path = DATA_DIR / "watchlist.json"
    wl_mtime = 0.0
    try:
        if wl_path.exists():
            wl_mtime = wl_path.stat().st_mtime
    except OSError:
        pass
    key = f"csv:{csv_max}|wl:{wl_mtime}"
    with _mtime_key_lock:
        _mtime_key_cache["computed_ts"] = now_ts
        _mtime_key_cache["key"] = key
    return key


def prime_live_signals_cache(
    rows: list[SignalScanRow], errors: list[dict], computed_at: datetime
) -> None:
    """讓其他 endpoint（如 /api/data/cloud-sync）在剛重算完後把結果塞進 cache，
    避免下次首發 /scan/signals 又花 60 秒重算同樣的東西。"""
    with _live_signals_lock:
        _live_signals_state.update({
            "key": _inputs_mtime_key(),
            "rows": rows,
            "errors": errors,
            "at": computed_at,
            "refreshing": False,
        })


def _recompute_live_signals(key: str) -> None:
    """背景重算全市場訊號並 swap state。run_signals_scan 本身已有 _scan_lock
    序列化，這裡不持有 _live_signals_lock（只在最後 swap 時短暫持有）。"""
    try:
        universe = scan_service.load_universe()
        rows, errors = scan_service.run_signals_scan(universe)
        now = datetime.now()
        with _live_signals_lock:
            _live_signals_state.update({
                "key": key, "rows": rows, "errors": errors, "at": now,
            })
    finally:
        with _live_signals_lock:
            _live_signals_state["refreshing"] = False


def _get_or_compute_live_signals() -> tuple[list[SignalScanRow], list[dict], datetime, bool]:
    """stale-while-revalidate 取得全市場訊號。

    - state 有舊 rows（即使 key 不符）→ 立即回舊資料；若無 in-flight 重算則起
      daemon thread 背景重算，算完 swap state。回傳 refreshing=True 提示前端輪詢。
    - state 完全沒 rows（冷啟動）→ 同步算一次再回。

    回傳 (rows, errors, computed_at, refreshing)。
    """
    current_key = _inputs_mtime_key()
    with _live_signals_lock:
        state = _live_signals_state
        fresh = state["key"] == current_key and state["rows"] is not None

        if state["rows"] is not None:
            if fresh:
                # 命中且新鮮：直接回，不重算
                return state["rows"], state["errors"], state["at"], state["refreshing"]
            # 有舊資料但已 stale：立即回舊資料，背景重算（若尚未啟動）
            if not state["refreshing"]:
                state["refreshing"] = True
                thread = threading.Thread(
                    target=_recompute_live_signals, args=(current_key,), daemon=True
                )
                thread.start()
            return state["rows"], state["errors"], state["at"], True

    # 冷啟動：沒有任何舊資料，只能同步算一次
    universe = scan_service.load_universe()
    rows, errors = scan_service.run_signals_scan(universe)
    now = datetime.now()
    with _live_signals_lock:
        _live_signals_state.update({
            "key": current_key, "rows": rows, "errors": errors, "at": now, "refreshing": False,
        })
    return rows, errors, now, False


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
        # stale-while-revalidate：有舊資料時立即回（refreshing=True 提示前端輪詢）
        rows_all, _errors, computed_at, refreshing = _get_or_compute_live_signals()
        total = len(rows_all)
        rows_page = rows_all[offset:offset + limit]
        return {
            "data": rows_page, "total": total, "limit": limit, "offset": offset,
            "computed_at": computed_at.isoformat() if computed_at else None,
            "refreshing": refreshing,
        }

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
    limit: int = 50,
    offset: int = 0,
) -> list[DividendScanRow]:
    """讀配息快照（含篩選排序 + 分頁）。

    預設只回前 50 筆 — 避免每請求把整張 ~3700 列表轉成 pydantic 物件、回傳數 MB JSON。
    回傳形狀維持 list（相容現有前端）。
    """
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

    # 分頁（篩選排序後再切片）
    df = df.iloc[offset:offset + limit]

    def _opt_float(v) -> Optional[float]:
        return float(v) if v is not None and pd.notna(v) else None

    rows = []
    for row in df.to_dict("records"):
        rows.append(
            DividendScanRow(
                code=row["code"],
                name=row["name"],
                overall=row["overall"],
                pass_count=int(row["pass_count"]),
                warn_count=int(row["warn_count"]),
                fail_count=int(row["fail_count"]),
                latest_dps=_opt_float(row["latest_dps"]),
                dps_streak_no_cut=int(row["dps_streak_no_cut"]),
                est_yield=_opt_float(row["est_yield"]),
                payout_avg=_opt_float(row["payout_avg"]),
                equity_ratio_latest=_opt_float(row["equity_ratio_latest"]),
                eps_growth=_opt_float(row["eps_growth"]),
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
            scan_service.write_snapshot("signals", rows, today_str, guard=True)
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
                scan_service.write_snapshot("signals", rows, today_str, guard=True)
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
