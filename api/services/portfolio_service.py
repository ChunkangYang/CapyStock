"""Portfolio service — CRUD + 現價查詢 + 損益計算。"""
from __future__ import annotations

from typing import Optional

from capystock import portfolio as pf_store
from capystock import scraper
from api.schemas.portfolio import PortfolioEntry, PortfolioLot


def _current_price(code: str) -> Optional[float]:
    # 先打即時報價（共用 TTL cache，延遲約 20 分）；失敗再 fallback 日線最後收盤。
    try:
        from api.services import quote_service
        q = quote_service.get_quote(code)
        if q is not None and q.get("price"):
            return float(q["price"])
    except Exception:
        pass
    try:
        df, _ = scraper.fetch_price(code)
        if df is not None and not df.empty:
            return float(df["close"].iloc[-1])
    except Exception:
        pass
    return None


def _enrich_lot(lot: dict, current: Optional[float]) -> PortfolioLot:
    pnl = None
    ret = None
    if current is not None and lot["exit_date"] is None:
        pnl = (current - lot["entry_price"]) * lot["quantity"]
        ret = (current / lot["entry_price"] - 1) * 100
    return PortfolioLot(
        id=lot["id"],
        code=lot["code"],
        name=lot["name"],
        entry_price=lot["entry_price"],
        quantity=lot["quantity"],
        entry_date=lot["entry_date"],
        exit_price=lot.get("exit_price"),
        exit_date=lot.get("exit_date"),
        note=lot.get("note", ""),
        current_price=current if lot["exit_date"] is None else None,
        unrealized_pnl=pnl,
        return_pct=ret,
    )


def list_portfolio(open_only: bool = True) -> list[PortfolioEntry]:
    data = pf_store.list_all()
    result = []
    for entry in data.values():
        lots = [
            {**lot, "code": entry["code"], "name": entry["name"]}
            for lot in entry["lots"]
            if not open_only or lot["exit_date"] is None
        ]
        if not lots:
            continue
        current = _current_price(entry["code"])
        enriched = [_enrich_lot(lot, current) for lot in lots]
        total_cost = sum(l.entry_price * l.quantity for l in enriched)
        total_pnl = sum(l.unrealized_pnl for l in enriched if l.unrealized_pnl is not None)
        result.append(PortfolioEntry(
            code=entry["code"],
            name=entry["name"],
            lots=enriched,
            total_cost=total_cost,
            total_unrealized_pnl=total_pnl if enriched and enriched[0].current_price else None,
        ))
    return result


def add_lot(code: str, entry_price: float, quantity: int,
            entry_date: Optional[str], note: str) -> PortfolioLot:
    name = scraper.fetch_name(code) or ""
    lot = pf_store.add_lot(code, name, entry_price, quantity, entry_date, note)
    lot_with_meta = {**lot, "code": code, "name": name}
    current = _current_price(code)
    return _enrich_lot(lot_with_meta, current)


def close_lot(code: str, lot_id: str, exit_price: float) -> Optional[PortfolioLot]:
    entry = pf_store.get_entry(code)
    if entry is None:
        return None
    lot = pf_store.close_lot(code, lot_id, exit_price)
    if lot is None:
        return None
    lot_with_meta = {**lot, "code": code, "name": entry["name"]}
    return _enrich_lot(lot_with_meta, None)
