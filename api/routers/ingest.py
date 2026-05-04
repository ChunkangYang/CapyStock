"""Ingest API endpoints。"""
from __future__ import annotations

import logging
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from api.schemas.ingest import (
    IngestRequest,
    IngestionResult,
    IngestStatusResponse,
    JpxWeeklyRequest,
    MarketFlowRow,
)
from api.services.ingest_service import IngestService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])
_svc = IngestService()


@router.post("/margin/{code}", response_model=IngestionResult)
async def ingest_margin(code: str, req: IngestRequest = IngestRequest()):
    return _svc.fetch_margin(code, force=req.force)


@router.post("/flow/{code}", response_model=IngestionResult)
async def ingest_flow(code: str, req: IngestRequest = IngestRequest()):
    return _svc.fetch_flow(code, force=req.force)


@router.post("/upload", response_model=IngestionResult)
async def ingest_upload(
    file: UploadFile = File(...),
    code: str = Form(...),
    kind: str = Form(...),
):
    content = await file.read()
    return _svc.import_manual(code, kind, content, filename=file.filename or "")


@router.get("/status/{code}", response_model=IngestStatusResponse)
async def ingest_status(code: str):
    return _svc.get_status(code)


@router.post("/jpx-weekly", response_model=IngestionResult)
async def ingest_jpx_weekly(req: JpxWeeklyRequest = JpxWeeklyRequest()):
    """抓取 JPX 最新投資部門別週報 Excel，解析並寫入 _market_flow.csv。"""
    from capystock.ingest.jpx_flow import _fetch_jpx_excel, parse_jpx_excel, MARKET_FLOW_PATH
    from capystock import config
    try:
        content = _fetch_jpx_excel(week=req.week)
        df = parse_jpx_excel(content, week_label=req.week)
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if MARKET_FLOW_PATH.exists():
            existing = pd.read_csv(MARKET_FLOW_PATH)
            df = pd.concat([existing, df], ignore_index=True).drop_duplicates("week")
        df.to_csv(MARKET_FLOW_PATH, index=False)
        return IngestionResult(
            code="_market", kind="flow", source="jpx_weekly",
            rows_fetched=len(df), written_path=str(MARKET_FLOW_PATH), ok=True,
        )
    except Exception as e:
        logger.warning(f"JPX weekly ingest failed: {e}")
        return IngestionResult(
            code="_market", kind="flow", source="jpx_weekly",
            rows_fetched=0, ok=False, error=str(e),
        )


@router.get("/market-flow", response_model=List[MarketFlowRow])
async def get_market_flow(weeks: int = 12):
    """回傳市場層級 flow（最近 N 週）。"""
    from capystock.ingest.jpx_flow import MARKET_FLOW_PATH
    if not MARKET_FLOW_PATH.exists():
        return []
    df = pd.read_csv(MARKET_FLOW_PATH)
    df = df.tail(weeks)
    rows = []
    for _, r in df.iterrows():
        rows.append(MarketFlowRow(
            week=str(r.get("week", "")),
            foreign_net=float(r.get("foreign_net", 0) or 0),
            institution_net=float(r.get("institution_net", 0)) if pd.notna(r.get("institution_net")) else None,
            individual_net=float(r.get("individual_net", 0)) if pd.notna(r.get("individual_net")) else None,
            estimated=bool(r.get("estimated", False)),
        ))
    return rows
