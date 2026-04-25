"""我的最愛 API。"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.schemas.favorites import FavoriteEntry, FavoriteAddRequest, FavoriteUpdateRequest
from api.services import favorite_service
from capystock import scraper

router = APIRouter()


@router.get("/favorites")
def list_favorites(tag: Optional[str] = Query(None)) -> list[FavoriteEntry]:
    """列出最愛。可選 tag 過濾。"""
    entries = favorite_service.list_favorites(tag=tag)
    return [
        FavoriteEntry(
            code=e["code"],
            name=e["name"],
            tags=e["tags"],
            added_at=e["added_at"],
            note=e.get("note", ""),
        )
        for e in entries
    ]


@router.post("/favorites")
def add_favorite(req: FavoriteAddRequest) -> FavoriteEntry:
    """加入最愛。可指定 tag（speculative 或 dividend）。"""
    code = req.code
    name = scraper.fetch_name(code) or ""

    entry = favorite_service.add(
        code=code,
        tag=req.tag,
        name=name,
    )

    # 若提供 note，立即更新
    if req.note:
        entry = favorite_service.set_note(code, req.note)

    return FavoriteEntry(
        code=entry["code"],
        name=entry["name"],
        tags=entry["tags"],
        added_at=entry["added_at"],
        note=entry.get("note", ""),
    )


@router.patch("/favorites/{code}")
def update_favorite(code: str, req: FavoriteUpdateRequest) -> FavoriteEntry:
    """更新最愛。可更新 tags 和 note。"""
    fav = favorite_service.load()

    if code not in fav:
        raise HTTPException(status_code=404, detail=f"{code} 不在最愛清單")

    entry = fav[code]

    # 更新 tags（如果提供）
    if req.tags is not None:
        sorted_tags = sorted(set(req.tags))  # 去重並排序
        entry["tags"] = sorted_tags
        if not sorted_tags:
            # 沒有 tag 了，整筆刪除
            favorite_service.remove(code)
            raise HTTPException(status_code=404, detail=f"{code} 因無 tag 已被刪除")

    # 更新 note（如果提供）
    if req.note is not None:
        entry["note"] = req.note

    # 儲存
    favorite_service._save(fav)

    return FavoriteEntry(
        code=entry["code"],
        name=entry["name"],
        tags=entry["tags"],
        added_at=entry["added_at"],
        note=entry.get("note", ""),
    )


@router.delete("/favorites/{code}")
def delete_favorite(code: str, tag: Optional[str] = Query(None)) -> dict:
    """移除最愛。若指定 tag 則只移除該 tag；若無 tag 則整筆刪除。"""
    if not favorite_service.remove(code, tag=tag):
        if tag:
            raise HTTPException(status_code=404, detail=f"{code} 無 tag '{tag}'")
        else:
            raise HTTPException(status_code=404, detail=f"{code} 不在最愛清單")

    return {"status": "removed", "code": code, "tag": tag}
