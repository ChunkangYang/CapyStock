"""技術指標服務層 — 從 price CSV 計算並打包成 API response。"""
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from capystock import scraper
from capystock.indicators import (
    IndicatorSignal, PriceBar,
    bollinger, detect_signals, ema, macd, rsi, sma,
)
from api.schemas.indicator import IndicatorBundle, IndicatorSeries

DEFAULT_INCLUDE = [
    "sma_5", "sma_20", "sma_60",
    "ema_12", "ema_26",
    "rsi_14",
    "macd", "macd_signal", "macd_hist",
    "bb_upper", "bb_mid", "bb_lower",
]


def _nan_to_none(arr: np.ndarray) -> list[Optional[float]]:
    return [None if np.isnan(v) else float(v) for v in arr]


def _load_price_bars(code: str, days: int) -> tuple[list[date], list[PriceBar]]:
    df, _ = scraper.fetch_price(code)
    if df is None or df.empty:
        return [], []

    bars: list[PriceBar] = []
    for _, row in df.iterrows():
        try:
            bars.append(PriceBar(
                date=pd.Timestamp(row["date"]).date(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0)),
            ))
        except (KeyError, ValueError, TypeError):
            continue

    if len(bars) > days:
        bars = bars[-days:]

    dates = [b.date for b in bars]
    return dates, bars


class IndicatorService:
    def get_bundle(
        self,
        code: str,
        days: int = 120,
        include: Optional[list[str]] = None,
    ) -> IndicatorBundle:
        if include is None:
            include = DEFAULT_INCLUDE

        include_set = set(include)
        dates, bars = _load_price_bars(code, days)

        if not bars:
            return IndicatorBundle(code=code, period_days=days, series={}, signals=[])

        closes = np.array([b.close for b in bars], dtype=float)
        date_list = dates
        series: dict[str, IndicatorSeries] = {}

        def _add(name: str, arr: np.ndarray) -> None:
            if name in include_set:
                series[name] = IndicatorSeries(
                    name=name,
                    dates=date_list,
                    values=_nan_to_none(arr),
                )

        # SMA
        _add("sma_5", sma(closes, 5))
        _add("sma_20", sma(closes, 20))
        _add("sma_60", sma(closes, 60))
        _add("sma_120", sma(closes, 120))

        # EMA
        _add("ema_12", ema(closes, 12))
        _add("ema_26", ema(closes, 26))

        # RSI
        _add("rsi_14", rsi(closes, 14))

        # MACD
        macd_d = macd(closes)
        _add("macd", macd_d["macd"])
        _add("macd_signal", macd_d["signal"])
        _add("macd_hist", macd_d["hist"])

        # Bollinger
        bb = bollinger(closes, 20)
        _add("bb_upper", bb["upper"])
        _add("bb_mid", bb["mid"])
        _add("bb_lower", bb["lower"])
        _add("bb_bandwidth", bb["bandwidth"])
        _add("bb_percent_b", bb["percent_b"])

        # 偵測訊號（使用最後一天）
        today = date_list[-1] if date_list else date.today()
        signals = detect_signals(bars, today)

        return IndicatorBundle(
            code=code,
            period_days=days,
            series=series,
            signals=signals,
        )


_service_instance: Optional[IndicatorService] = None


def get_indicator_service() -> IndicatorService:
    global _service_instance
    if _service_instance is None:
        _service_instance = IndicatorService()
    return _service_instance
