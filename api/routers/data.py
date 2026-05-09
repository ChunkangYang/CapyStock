"""資料管理 API：cache 概覽 + 批量 ingest + SSE。"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.services.ingest_service import IngestService, _cache_age, _cache_path, _load_meta
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
    flow_age_days: Optional[int] = None
    fundamental_age_days: Optional[int] = None


class BatchIngestRequest(BaseModel):
    codes: List[str]
    kinds: List[str]


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
            flow_age_days=age("flow"),
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
            elif kind == "flow":
                result = _svc.fetch_flow(code, force=True)
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
