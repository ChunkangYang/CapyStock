"""比較模式 API 路由。"""
from fastapi import APIRouter, HTTPException, Query

from api.schemas.compare import CompareDividendBundle, CompareSignalsBundle
from api.services.compare_service import get_compare_service

router = APIRouter()

MAX_CODES = 5


def _parse_codes(codes_str: str) -> list[str]:
    parsed = [c.strip() for c in codes_str.split(",") if c.strip()]
    unique = list(dict.fromkeys(parsed))
    return unique


@router.get("/compare/signals", response_model=CompareSignalsBundle)
def compare_signals(
    codes: str = Query(..., description="逗號分隔股票代碼，最多 5 檔"),
    days: int = Query(120, ge=20, le=500),
):
    """投機模式：多檔 K 線正規化 + 指標 + 相關性矩陣。"""
    code_list = _parse_codes(codes)
    if not code_list:
        raise HTTPException(status_code=422, detail="codes 不可為空")
    if len(code_list) > MAX_CODES:
        raise HTTPException(status_code=422, detail=f"最多 {MAX_CODES} 檔，收到 {len(code_list)} 檔")
    try:
        return get_compare_service().signals_bundle(code_list, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare/dividend", response_model=CompareDividendBundle)
def compare_dividend(
    codes: str = Query(..., description="逗號分隔股票代碼，最多 5 檔"),
):
    """金雞模式：基本面雷達圖 + DPS 歷史並排。"""
    code_list = _parse_codes(codes)
    if not code_list:
        raise HTTPException(status_code=422, detail="codes 不可為空")
    if len(code_list) > MAX_CODES:
        raise HTTPException(status_code=422, detail=f"最多 {MAX_CODES} 檔，收到 {len(code_list)} 檔")
    try:
        return get_compare_service().dividend_bundle(code_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
