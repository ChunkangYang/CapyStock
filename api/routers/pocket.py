"""三盤濾網選股 API。

GET  /api/v1/pocket            取得最新口袋名單快照（無則即時掃描）
POST /api/v1/pocket/scan       即時對全市場跑三盤濾網並寫入快照
"""
from typing import Optional

from fastapi import APIRouter, Query

from api.services import pocket_service

router = APIRouter()


@router.get("/pocket")
def get_pocket_list(refresh: bool = Query(False, description="True 則略過快照即時重算")):
    """取得口袋名單 + 三盤漏斗。預設讀最新快照，無快照則即時掃描。"""
    if not refresh:
        snap = pocket_service.latest_snapshot()
        if snap is not None:
            return snap
    result = pocket_service.scan_pocket_list()
    pocket_service.write_snapshot(result)
    return result


@router.post("/pocket/scan")
def run_pocket_scan(
    min_filings: Optional[int] = None,
    window_days: Optional[int] = None,
    cost_tolerance: Optional[float] = None,
    margin_weeks: Optional[int] = None,
    limit: Optional[int] = None,
):
    """即時全市場掃描（可覆寫參數），寫入當日快照後回傳。"""
    from capystock import config
    result = pocket_service.scan_pocket_list(
        min_filings=min_filings if min_filings is not None else config.POCKET_GATE1_MIN_FILINGS,
        window_days=window_days if window_days is not None else config.POCKET_GATE1_WINDOW_DAYS,
        cost_tolerance=cost_tolerance if cost_tolerance is not None else config.POCKET_GATE2_COST_TOLERANCE_PCT,
        margin_weeks=margin_weeks if margin_weeks is not None else config.POCKET_GATE3_MARGIN_DECLINE_WEEKS,
        limit=limit,
    )
    pocket_service.write_snapshot(result)
    return result
