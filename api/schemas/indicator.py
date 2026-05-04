"""技術指標 API schema。"""
from datetime import date
from typing import Optional

from pydantic import BaseModel

from capystock.indicators import IndicatorSignal


class IndicatorSeries(BaseModel):
    name: str
    dates: list[date]
    values: list[Optional[float]]  # NaN → None


class IndicatorBundle(BaseModel):
    code: str
    period_days: int
    series: dict[str, IndicatorSeries]
    signals: list[IndicatorSignal]
