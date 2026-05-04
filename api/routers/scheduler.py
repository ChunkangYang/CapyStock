"""Scheduler API。"""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from api.schemas.scheduler import (
    JobDef,
    JobListResponse,
    JobRun,
    JobRunListResponse,
    JobTriggerResponse,
    JobUpdateRequest,
)
from api.services import scheduler_service as ss


router = APIRouter()


def _svc():
    return ss.get_scheduler_service()


@router.get("/scheduler/jobs", response_model=JobListResponse)
def list_jobs():
    return JobListResponse(jobs=_svc().list_jobs())


@router.patch("/scheduler/jobs/{job_id}", response_model=JobDef)
def patch_job(job_id: str, body: JobUpdateRequest):
    try:
        return _svc().update_job(job_id, **body.model_dump(exclude_none=True))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scheduler/jobs/{job_id}/run", response_model=JobTriggerResponse)
def trigger_job(job_id: str, background_tasks: BackgroundTasks):
    svc = _svc()
    if svc.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    import uuid
    from datetime import datetime
    run_id = uuid.uuid4().hex
    started = datetime.utcnow()

    def _run():
        try:
            svc.trigger_now(job_id)
        except Exception:
            pass

    background_tasks.add_task(_run)
    return JobTriggerResponse(
        run_id=run_id,
        job_id=job_id,
        status="running",
        started_at=started,
    )


@router.get("/scheduler/runs", response_model=JobRunListResponse)
def list_runs(
    job_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=365),
    status: Optional[str] = Query(None),
):
    return JobRunListResponse(runs=_svc().list_runs(job_id=job_id, days=days, status=status))


@router.get("/scheduler/runs/{run_id}", response_model=JobRun)
def get_run(run_id: str):
    run = _svc().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return run
