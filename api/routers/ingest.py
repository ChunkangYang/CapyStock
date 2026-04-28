"""Ingest API endpoints。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from api.schemas.ingest import IngestRequest, IngestionResult, IngestStatusResponse
from api.services.ingest_service import IngestService

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
