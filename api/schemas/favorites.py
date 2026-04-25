"""我的最愛 schema 定義。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FavoriteEntry(BaseModel):
    """最愛項目。"""
    code: str
    name: str
    tags: list[str]  # ["speculative", "dividend"] 等
    added_at: str  # ISO 8601 datetime
    note: str = ""


class FavoriteAddRequest(BaseModel):
    """加入最愛請求。"""
    code: str
    tag: str  # "speculative" 或 "dividend"
    note: Optional[str] = None


class FavoriteUpdateRequest(BaseModel):
    """更新最愛請求。"""
    tags: Optional[list[str]] = None
    note: Optional[str] = None
