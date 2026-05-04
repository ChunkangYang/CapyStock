"""比較模式 API schema。"""
from typing import Optional
from pydantic import BaseModel

from api.schemas.common import FundamentalReport
from api.schemas.indicator import IndicatorSeries
from capystock.indicators import IndicatorSignal


class DpsRow(BaseModel):
    year: int
    dps: Optional[float] = None


class CompareSignalsBundle(BaseModel):
    codes: list[str]
    period_days: int
    # key: code → dict of series_name → IndicatorSeries
    series_by_code: dict[str, dict[str, IndicatorSeries]]
    # key: code → list[date_str]
    dates_by_code: dict[str, list[str]]
    # key: code → list[normalized_close]（以期初 = 100 為基準）
    normalized_close: dict[str, list[Optional[float]]]
    # key: code → list[IndicatorSignal]
    signals_by_code: dict[str, list[IndicatorSignal]]
    # Pearson correlation matrix（key: code_i → {code_j: corr}）
    correlation_matrix: dict[str, dict[str, float]]


class CompareDividendBundle(BaseModel):
    codes: list[str]
    fundamentals: dict[str, Optional[FundamentalReport]]
    dividend_history: dict[str, list[DpsRow]]
    # 8 軸 0–100 正規化雷達分數（key: code → {metric: score}）
    radar_normalized: dict[str, dict[str, float]]
