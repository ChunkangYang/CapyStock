"""元資訊 endpoint（health, version 等）。"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    """健檢。"""
    return {"status": "ok", "version": "0.1.0"}
