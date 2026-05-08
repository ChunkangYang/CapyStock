"""Sweep（網格回測）API endpoints。"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.schemas.sweep import SweepJobStatus, SweepRequest, SweepResult
from api.services.strategy_sweep_service import StrategySweepService, _expand_grid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sweep", tags=["sweep"])
_svc = StrategySweepService()


@router.post("/run", response_model=dict)
async def start_sweep(req: SweepRequest):
    """啟動 sweep job（非同步，立即回傳 job_id）。"""
    combos = _expand_grid(req.grid)
    n = len(combos)
    if n > 200:
        raise HTTPException(status_code=422, detail=f"組合數 {n} 超過上限 200")

    try:
        job_id = _svc.start_async(req)
        return {"job_id": job_id, "status": "running", "n_combinations": n}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/progress")
async def get_progress(job_id: str):
    """查詢 sweep job 進度。"""
    job = _svc.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    prog = _svc.get_progress(job_id) or (0, job.n_combinations)
    return {
        "job_id": job_id,
        "status": job.status,
        "done": prog[0],
        "total": prog[1],
    }


@router.get("/{job_id}", response_model=Optional[SweepResult])
async def get_sweep(job_id: str):
    """查詢 sweep job 狀態與結果。"""
    result = _svc.get_job(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="job not found")
    return result


@router.get("/{job_id}/stream")
async def stream_sweep_progress(job_id: str):
    """SSE 進度串流。"""
    async def event_gen():
        for _ in range(120):
            result = _svc.get_job(job_id)
            if result is None:
                yield f"data: {{\"error\": \"job not found\"}}\n\n"
                break
            prog = _svc.get_progress(job_id) or (0, result.n_combinations)
            yield f"data: {{\"done\": {prog[0]}, \"total\": {prog[1]}, \"status\": \"{result.status}\"}}\n\n"
            if result.status in ("completed", "failed", "cancelled"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.delete("/{job_id}")
async def cancel_sweep(job_id: str):
    """取消 sweep job。"""
    ok = _svc.cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, "status": "cancelled"}
