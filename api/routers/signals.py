"""訊號分析 API。"""
from fastapi import APIRouter, HTTPException

from api.schemas.common import (
    FlowRow, MarginRow, PriceBar, SignalResult,
)
from api.services import signal_service

router = APIRouter()


@router.get("/signals")
def list_signals() -> list[SignalResult]:
    """分析整個追蹤清單的訊號。"""
    return signal_service.analyze_watchlist()


@router.get("/signals/{code}")
def get_signal(code: str) -> SignalResult:
    """取得單檔股票訊號。"""
    try:
        return signal_service.analyze_one(code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/{code}/price")
def get_price_history(code: str, days: int = 90) -> list[PriceBar]:
    """取得股價 K 線（可指定天數）。"""
    return signal_service.get_price_history(code, days)


@router.get("/signals/{code}/flow")
def get_flow_history(code: str, days: int = 30) -> list[FlowRow]:
    """取得投資部門別買賣超（可指定天數）。"""
    return signal_service.get_flow_history(code, days)


@router.get("/signals/{code}/margin")
def get_margin_history(code: str, weeks: int = 12) -> list[MarginRow]:
    """取得信用殘歷史（可指定週數）。"""
    return signal_service.get_margin_history(code, weeks)


@router.get("/signals/{code}/edinet")
def get_edinet_events(code: str, days: int = 30) -> list[dict]:
    """取得 EDINET 5% rule 申報事件。"""
    return signal_service.get_edinet_events(code, days)
