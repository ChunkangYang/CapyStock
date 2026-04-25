"""追蹤清單 API。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capystock import scraper, storage
from api.schemas.common import WatchlistEntry

router = APIRouter()


class WatchlistAddRequest(BaseModel):
    """加入追蹤請求。"""
    code: str
    start_price: float


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


@router.post("/watchlist")
def add_watchlist(req: WatchlistAddRequest) -> WatchlistEntry:
    """加入追蹤股票。"""
    code = req.code
    # 取得股票名稱
    name = scraper.fetch_name(code) or ""
    # 加入
    storage.add_watch(code, req.start_price, name)
    return WatchlistEntry(
        code=code,
        name=name,
        start_price=req.start_price,
    )


@router.delete("/watchlist/{code}")
def remove_watchlist(code: str) -> dict:
    """移除追蹤股票。"""
    if not storage.remove_watch(code):
        raise HTTPException(status_code=404, detail=f"{code} 不在追蹤清單")
    return {"status": "removed", "code": code}
