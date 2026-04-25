"""基本面 / 高股息 API。"""
from fastapi import APIRouter, HTTPException

from api.schemas.common import FundamentalReport as FundamentalReportSchema
from api.services import dividend_service

router = APIRouter()


@router.get("/dividend/{code}")
def get_fundamental(code: str) -> FundamentalReportSchema:
    """取得基本面 8 指標報告。"""
    report = dividend_service.get_fundamental_report(code)
    if report is None:
        raise HTTPException(status_code=404, detail=f"無法取得 {code} 的基本面資料")
    return report


@router.get("/dividend/{code}/series")
def get_dividend_series(code: str) -> dict:
    """取得配當與其他指標時序（供圖表用）。"""
    return dividend_service.get_dividend_history(code)
