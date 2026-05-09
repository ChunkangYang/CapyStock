"""追蹤清單 API。"""
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capystock import config, scraper, storage
from api.schemas.common import WatchlistEntry

router = APIRouter()


class WatchlistAddRequest(BaseModel):
    """加入追蹤請求。start_price 若未提供則由後端從 price cache 取最新收盤價，仍無則為 0。"""
    code: str
    start_price: Optional[float] = None


@router.get("/watchlist")
def list_watchlist() -> list[WatchlistEntry]:
    """列出所有追蹤清單。"""
    wl = storage.load_watchlist()
    return [
        WatchlistEntry(
            code=v["code"],
            name=v.get("name", ""),
            start_price=v["start_price"],
            added_date=v.get("added_date"),
        )
        for v in wl.values()
    ]


def _resolve_start_price(code: str, provided: Optional[float]) -> float:
    """priority: 1. 呼叫端提供的值  2. price cache 最新收盤  3. 0"""
    if provided is not None and provided > 0:
        return provided
    cache = config.CACHE_DIR / f"{code}_price.csv"
    if cache.exists():
        try:
            df = pd.read_csv(cache)
            if not df.empty and "close" in df.columns:
                return float(df.iloc[-1]["close"])
        except Exception:
            pass
    return 0.0


@router.post("/watchlist")
def add_watchlist(req: WatchlistAddRequest) -> WatchlistEntry:
    """加入追蹤股票。start_price 自動解析：provided > cache 最新收盤 > 0。"""
    code = req.code
    start_price = _resolve_start_price(code, req.start_price)
    name = scraper.fetch_name(code) or ""
    storage.add_watch(code, start_price, name)
    return WatchlistEntry(
        code=code,
        name=name,
        start_price=start_price,
    )


@router.delete("/watchlist/{code}")
def remove_watchlist(code: str) -> dict:
    """移除追蹤股票。"""
    if not storage.remove_watch(code):
        raise HTTPException(status_code=404, detail=f"{code} 不在追蹤清單")
    return {"status": "removed", "code": code}
