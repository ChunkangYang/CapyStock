"""資料管理 API：cache 概覽 + 批量 ingest + SSE。"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.services.ingest_service import IngestService, _cache_age, _cache_path, _load_meta
from api.services.scan_service import load_universe
from capystock import config, storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["data"])
_svc = IngestService()

# in-memory 批量 job 狀態
_batch_jobs: dict[str, dict] = {}


class CacheOverviewRow(BaseModel):
    code: str
    name: str
    price_age_days: Optional[int] = None
    margin_age_days: Optional[int] = None
    fundamental_age_days: Optional[int] = None


class BatchIngestRequest(BaseModel):
    codes: List[str]
    kinds: List[str]


class UniverseStock(BaseModel):
    code: str
    name: str
    market: str = ""


@router.get("/universe-list", response_model=List[UniverseStock])
async def universe_list():
    """回傳全市場股票清單（從 universe.csv）。"""
    try:
        rows = load_universe()
        return [UniverseStock(code=str(r["code"]), name=str(r.get("name", "")), market=str(r.get("market", ""))) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview", response_model=List[CacheOverviewRow])
async def data_overview(scope: str = "watchlist"):
    """取得各 code 各 kind 的 cache 狀態。"""
    wl = storage.load_watchlist()
    codes = [item.get("code", "") for item in wl] if isinstance(wl, list) else list(wl.keys())

    rows = []
    for code in codes:
        name = ""
        if isinstance(wl, list):
            entry = next((w for w in wl if w.get("code") == code), {})
            name = entry.get("name", code)
        else:
            name = wl.get(code, {}).get("name", code)

        def age(kind: str) -> Optional[int]:
            td = _cache_age(code, kind)
            return td.days if td is not None else None

        rows.append(CacheOverviewRow(
            code=code, name=name,
            price_age_days=age("price"),
            margin_age_days=age("margin"),
            fundamental_age_days=age("fundamental"),
        ))
    return rows


@router.post("/batch-ingest", response_model=dict)
async def batch_ingest(req: BatchIngestRequest):
    """批量觸發 ingest；回傳 job_id（使用 SSE 追蹤進度）。"""
    job_id = str(uuid.uuid4())
    tasks = [(code, kind) for code in req.codes for kind in req.kinds]
    _batch_jobs[job_id] = {
        "status": "running",
        "total": len(tasks),
        "done": 0,
        "results": [],
        "tasks": tasks,
    }
    # 同步執行（後端 asyncio task）
    asyncio.create_task(_run_batch(job_id, tasks))
    return {"job_id": job_id, "total": len(tasks)}


async def _run_batch(job_id: str, tasks: list[tuple[str, str]]):
    job = _batch_jobs[job_id]
    for code, kind in tasks:
        try:
            if kind == "margin":
                result = _svc.fetch_margin(code, force=True)
            else:
                result = None

            job["results"].append({
                "code": code, "kind": kind,
                "ok": result.ok if result else False,
                "source": result.source if result else "n/a",
                "rows": result.rows_fetched if result else 0,
                "error": result.error if result else None,
            })
        except Exception as e:
            job["results"].append({
                "code": code, "kind": kind, "ok": False, "error": str(e), "source": "error", "rows": 0,
            })
        job["done"] += 1
        await asyncio.sleep(0)

    job["status"] = "completed"


@router.get("/batch-ingest/{job_id}/stream")
async def batch_ingest_stream(job_id: str):
    """SSE 進度串流。"""
    if job_id not in _batch_jobs:
        raise HTTPException(status_code=404, detail="job not found")

    async def event_gen():
        for _ in range(300):
            job = _batch_jobs.get(job_id)
            if not job:
                break
            import json
            yield f"data: {json.dumps({'done': job['done'], 'total': job['total'], 'status': job['status']})}\n\n"
            if job["status"] == "completed":
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/batch-ingest/{job_id}", response_model=dict)
async def get_batch_job(job_id: str):
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.get("/cloud-sync/status")
async def cloud_sync_status():
    """回傳雲端 cache 狀態（從 data/cloud-cache/_fetch_report.json 讀）。"""
    import json

    cache_dir = config.PROJECT_ROOT / "data" / "cloud-cache"
    report_path = cache_dir / "_fetch_report.json"

    if not report_path.exists():
        return {"available": False, "message": "尚未從雲端拉取過資料"}

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        csv_files = sorted([p.name for p in cache_dir.glob("*.csv")])
        return {
            "available": True,
            "ended_utc": report.get("ended_utc"),
            "summary": report.get("summary", {}),
            "kinds": report.get("kinds", []),
            "files_count": len(csv_files),
            "files_sample": csv_files[:10],
        }
    except Exception as e:
        return {"available": False, "message": f"報告檔解析失敗: {e}"}


class CloudSyncRequest(BaseModel):
    pull: bool = True  # True=從 GitHub 下載最新；False=只套用現有 cloud-cache 到 cache
    rescan_after_sync: bool = True  # 同步完自動重算全市場訊號（建議開啟，避免 stale snapshot）
    kinds: Optional[List[str]] = None  # None=全量；["price"]=只同步價格（價格獨立排程用）


@router.post("/cloud-sync")
async def cloud_sync(req: CloudSyncRequest):
    """從雲端同步資料（cloud-cache → cache），完成後（可選）重算全市場訊號。

    實作搬到 data_sync_service.run_cloud_sync（router 與 price_sync 排程共用同一份），
    這裡只負責把同步函式丟到 threadpool 並把錯誤轉成 HTTPException。
    """
    import asyncio

    from api.services import data_sync_service

    try:
        return await asyncio.to_thread(
            data_sync_service.run_cloud_sync,
            pull=req.pull,
            kinds=req.kinds,
            rescan=req.rescan_after_sync,
        )
    except RuntimeError as e:
        msg = str(e)
        status = 404 if "沒有 data/cloud-cache" in msg or "不存在" in msg else 500
        raise HTTPException(status_code=status, detail=msg)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"cloud-sync 失敗: {e}")


@router.get("/latest-price/{code}")
async def get_latest_price(code: str):
    """只讀 cache，回傳最新收盤價。不發網路請求。"""
    import pandas as pd
    cache = _cache_path(code, "price")
    if not cache.exists():
        raise HTTPException(status_code=404, detail="no price cache")
    try:
        df = pd.read_csv(cache)
        if df.empty or "close" not in df.columns:
            raise HTTPException(status_code=404, detail="no close data")
        latest = float(df.iloc[-1]["close"])
        return {"code": code, "close": latest, "date": str(df.iloc[-1].get("date", ""))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
