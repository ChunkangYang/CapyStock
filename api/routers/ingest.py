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
)
from api.services.ingest_service import IngestService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])
_svc = IngestService()


@router.post("/margin/{code}", response_model=IngestionResult)
async def ingest_margin(code: str, req: IngestRequest = IngestRequest()):
    return _svc.fetch_margin(code, force=req.force)


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


class UniverseUpdateResult(BaseModel):
    ok: bool
    total: int = 0
    prime: int = 0
    standard: int = 0
    growth: int = 0
    error: Optional[str] = None


@router.post("/update-universe", response_model=UniverseUpdateResult)
async def update_jpx_universe():
    """下載 JPX 官方上市公司清單並更新 universe.csv。"""
    try:
        import subprocess
        import sys
        from pathlib import Path

        script_path = Path(__file__).parent.parent.parent / "scripts" / "update_jpx_universe.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            logger.warning(f"Universe update failed: {result.stderr}")
            return UniverseUpdateResult(ok=False, error=result.stderr or "Unknown error")

        # 解析輸出中的統計資訊
        output = result.stdout
        stats = {"ok": True, "total": 0, "prime": 0, "standard": 0, "growth": 0}

        # 簡單的統計提取（從 universe.csv）
        from capystock import config
        universe_path = config.DATA_DIR / "universe.csv"
        if universe_path.exists():
            df = pd.read_csv(universe_path)
            stats["total"] = len(df)
            stats["prime"] = len(df[df["market"] == "Prime"])
            stats["standard"] = len(df[df["market"] == "Standard"])
            stats["growth"] = len(df[df["market"] == "Growth"])

        logger.info(f"Universe updated: {stats}")
        return UniverseUpdateResult(**stats)

    except Exception as e:
        logger.error(f"Universe update error: {e}")
        return UniverseUpdateResult(ok=False, error=str(e))
