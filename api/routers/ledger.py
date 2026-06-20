"""跟單帳本 API — IMP-002。"""
from fastapi import APIRouter, HTTPException

from api.schemas.ledger import (
    AdvanceResult, Ledger, LedgerCreateRequest, LedgerSummary, Trade, TradeAddRequest,
)
from api.services import ledger_service

router = APIRouter()


@router.get("/ledgers", response_model=list[LedgerSummary])
def list_ledgers():
    return ledger_service.list_ledgers()


@router.post("/ledgers", response_model=Ledger)
def create_ledger(req: LedgerCreateRequest):
    return ledger_service.create_ledger(req.name)


@router.get("/ledgers/{ledger_id}", response_model=Ledger)
def get_ledger(ledger_id: str):
    lg = ledger_service.get_ledger(ledger_id)
    if lg is None:
        raise HTTPException(404, f"帳本 {ledger_id} 不存在")
    return lg


@router.delete("/ledgers/{ledger_id}")
def delete_ledger(ledger_id: str):
    if not ledger_service.delete_ledger(ledger_id):
        raise HTTPException(404, f"帳本 {ledger_id} 不存在")
    return {"status": "deleted", "id": ledger_id}


@router.post("/ledgers/{ledger_id}/trades", response_model=Trade)
def add_trade(ledger_id: str, req: TradeAddRequest):
    if req.shares <= 0:
        raise HTTPException(422, "購入股數必須 > 0")
    if req.entry_price <= 0:
        raise HTTPException(422, "購入時價必須 > 0")
    trade = ledger_service.add_trade(ledger_id, req)
    if trade is None:
        raise HTTPException(404, f"帳本 {ledger_id} 不存在")
    return trade


@router.delete("/ledgers/{ledger_id}/trades/{trade_id}")
def delete_trade(ledger_id: str, trade_id: str):
    if not ledger_service.delete_trade(ledger_id, trade_id):
        raise HTTPException(404, "帳本或交易不存在")
    return {"status": "deleted", "id": trade_id}


@router.get("/ledgers/{ledger_id}/trades/{trade_id}/price")
def trade_price_series(ledger_id: str, trade_id: str):
    """單筆交易：進場日 → 今天（已出場到出場日）的日曆軸收盤序列（缺資料留 None）。"""
    data = ledger_service.trade_price_series(ledger_id, trade_id)
    if data is None:
        raise HTTPException(404, "帳本或交易不存在")
    return data


@router.post("/ledgers/{ledger_id}/advance", response_model=AdvanceResult)
def advance_ledger(ledger_id: str):
    r = ledger_service.advance_ledger(ledger_id)
    if r is None:
        raise HTTPException(404, f"帳本 {ledger_id} 不存在")
    return r


@router.post("/ledgers/advance-all", response_model=AdvanceResult)
def advance_all():
    return ledger_service.advance_all()
