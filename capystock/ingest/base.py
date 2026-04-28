"""資料引入層抽象基類與結果模型。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Literal, Optional

import pandas as pd
from pydantic import BaseModel


class IngestionResult(BaseModel):
    code: str
    kind: Literal["margin", "flow", "price"]
    source: str
    rows_fetched: int
    date_range: Optional[tuple[date, date]] = None
    written_path: Optional[str] = None
    ok: bool
    error: Optional[str] = None


class IngestionSource(ABC):
    name: str
    kind: Literal["margin", "flow", "price"]

    @abstractmethod
    def fetch(self, code: str) -> pd.DataFrame:
        """抓取資料，回傳 normalized DataFrame。失敗時 raise Exception。"""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """簡易連線測試，True = 來源可用。"""
        ...
