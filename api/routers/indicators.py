"""技術指標 API 路由。"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.schemas.indicator import IndicatorBundle, IndicatorSeries
from api.services.indicator_service import get_indicator_service
from capystock.indicators import IndicatorSignal

router = APIRouter()


@router.get("/indicators/{code}", response_model=IndicatorBundle)
def get_indicators(
    code: str,
    days: int = Query(120, ge=20, le=500),
    include: Optional[str] = Query(None, description="逗號分隔，如 rsi_14,macd,bollinger_20"),
):
    """取得指標時序 bundle（給前端畫圖用）。"""
    include_list = [s.strip() for s in include.split(",")] if include else None

    # bollinger_20 → bb_upper, bb_mid, bb_lower
    if include_list and "bollinger_20" in include_list:
        include_list.remove("bollinger_20")
        include_list.extend(["bb_upper", "bb_mid", "bb_lower"])

    try:
        bundle = get_indicator_service().get_bundle(code, days=days, include=include_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return bundle


@router.get("/indicators/{code}/signals", response_model=list[IndicatorSignal])
def get_indicator_signals(
    code: str,
    days: int = Query(30, ge=20, le=500),
):
    """只取最近 N 天的技術指標訊號清單。"""
    try:
        bundle = get_indicator_service().get_bundle(code, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return bundle.signals
