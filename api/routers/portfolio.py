from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas.portfolio import CloseIn, LotIn, PortfolioEntry, PortfolioLot
from api.services import portfolio_service

router = APIRouter(prefix="/portfolio")


@router.get("", response_model=list[PortfolioEntry])
def get_portfolio(open_only: bool = True):
    return portfolio_service.list_portfolio(open_only=open_only)


@router.post("", response_model=PortfolioLot)
def add_lot(body: LotIn):
    return portfolio_service.add_lot(
        code=body.code,
        entry_price=body.entry_price,
        quantity=body.quantity,
        entry_date=body.entry_date,
        note=body.note,
    )


@router.post("/{code}/{lot_id}/close", response_model=PortfolioLot)
def close_lot(code: str, lot_id: str, body: CloseIn):
    result = portfolio_service.close_lot(code, lot_id, body.exit_price)
    if result is None:
        raise HTTPException(status_code=404, detail=f"lot {lot_id} not found or already closed")
    return result
