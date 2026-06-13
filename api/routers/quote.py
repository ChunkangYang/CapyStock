"""即時報價 API。

GET /api/v1/quote/{code} → {code, price, price_time, source}
東證延遲約 20 分；yfinance 取不到時回 404，呼叫端 fallback 到日線最後收盤。
"""
from fastapi import APIRouter, HTTPException

from api.services import quote_service

router = APIRouter()


@router.get("/quote/{code}")
def get_quote(code: str) -> dict:
    q = quote_service.get_quote(code)
    if q is None:
        raise HTTPException(status_code=404, detail=f"無法取得 {code} 即時報價")
    return q
