"""Analytics API：異常偵測 + 事件研究。"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter

from api.schemas.analytics import AnomalyEvent, EventStudyRequest, EventStudyResult
from api.services.anomaly_service import AnomalyService
from api.services.event_study_service import EventStudyService

router = APIRouter(prefix="/analytics", tags=["analytics"])
_anomaly_svc = AnomalyService()
_event_svc = EventStudyService()


@router.get("/anomaly/{code}", response_model=List[AnomalyEvent])
async def get_anomalies(
    code: str,
    days: int = 90,
    volume_multiplier: float = 3.0,
    price_sigma: float = 2.5,
    gap_pct: float = 0.05,
):
    return _anomaly_svc.scan(
        code, days=days,
        volume_multiplier=volume_multiplier,
        price_sigma=price_sigma,
        gap_pct=gap_pct,
    )


@router.post("/event-study/{code}", response_model=EventStudyResult)
async def run_event_study(code: str, req: EventStudyRequest):
    return _event_svc.run(
        code=code,
        events=req.events,
        window=req.window,
        benchmark=req.benchmark,
    )
