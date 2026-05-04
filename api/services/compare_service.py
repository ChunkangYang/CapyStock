"""比較模式服務層。"""
from datetime import date
from typing import Optional

import numpy as np

from api.schemas.compare import CompareDividendBundle, CompareSignalsBundle, DpsRow
from api.schemas.common import FundamentalReport
from api.schemas.indicator import IndicatorSeries
from api.services.dividend_service import get_fundamental_report
from api.services.indicator_service import _load_price_bars, _nan_to_none
from capystock import fundamental as fundamental_module
from capystock.indicators import bollinger, detect_signals, ema, macd, rsi, sma


RADAR_METRIC_ORDER = [
    "Sales Growth", "EPS Growth", "Op. Margin",
    "Equity Ratio", "Operating CF", "Cash",
    "DPS Growth", "Payout Ratio",
]

_SCORE_MAP = {"PASS": 100.0, "WARN": 50.0, "FAIL": 0.0, "N/A": 50.0}


def _compute_correlation_matrix(
    closes_by_code: dict[str, np.ndarray],
    dates_by_code: dict[str, list[date]],
) -> dict[str, dict[str, float]]:
    """計算所有 code 對間的 Pearson correlation（基於 log return，對齊交易日）。"""
    codes = list(closes_by_code.keys())

    # 建立 date → close 的 mapping
    date_close: dict[str, dict[date, float]] = {}
    for code, closes in closes_by_code.items():
        dates = dates_by_code[code]
        date_close[code] = {d: c for d, c in zip(dates, closes)}

    # 取所有 code 都有的日期交集
    common_dates: Optional[set] = None
    for code in codes:
        s = set(date_close[code].keys())
        common_dates = s if common_dates is None else common_dates & s

    matrix: dict[str, dict[str, float]] = {c: {} for c in codes}

    if not common_dates or len(common_dates) < 2:
        for c1 in codes:
            for c2 in codes:
                matrix[c1][c2] = 1.0 if c1 == c2 else float("nan")
        return matrix

    sorted_dates = sorted(common_dates)

    log_returns: dict[str, np.ndarray] = {}
    for code in codes:
        arr = np.array([date_close[code][d] for d in sorted_dates], dtype=float)
        lr = np.diff(np.log(arr))
        log_returns[code] = lr

    for c1 in codes:
        for c2 in codes:
            if c1 == c2:
                matrix[c1][c2] = 1.0
            else:
                r1, r2 = log_returns[c1], log_returns[c2]
                if len(r1) < 2 or len(r2) < 2:
                    matrix[c1][c2] = float("nan")
                else:
                    corr = float(np.corrcoef(r1, r2)[0, 1])
                    matrix[c1][c2] = corr if not np.isnan(corr) else float("nan")

    return matrix


def _normalized_close(closes: np.ndarray) -> list[Optional[float]]:
    """以第一個非 NaN 值為 100，正規化 close 序列。"""
    result: list[Optional[float]] = []
    base: Optional[float] = None
    for v in closes:
        if np.isnan(v):
            result.append(None)
        else:
            if base is None:
                base = v
            result.append(round(v / base * 100, 4) if base else None)
    return result


class CompareService:
    def signals_bundle(
        self, codes: list[str], days: int = 120
    ) -> CompareSignalsBundle:
        codes = list(dict.fromkeys(codes))  # 去重保序

        series_by_code: dict[str, dict[str, IndicatorSeries]] = {}
        dates_by_code: dict[str, list[str]] = {}
        normalized_close: dict[str, list[Optional[float]]] = {}
        signals_by_code: dict[str, list] = {}
        closes_map: dict[str, np.ndarray] = {}
        raw_dates_map: dict[str, list[date]] = {}

        for code in codes:
            raw_dates, bars = _load_price_bars(code, days)
            if not bars:
                series_by_code[code] = {}
                dates_by_code[code] = []
                normalized_close[code] = []
                signals_by_code[code] = []
                continue

            closes = np.array([b.close for b in bars], dtype=float)
            closes_map[code] = closes
            raw_dates_map[code] = raw_dates
            date_strs = [d.isoformat() for d in raw_dates]
            dates_by_code[code] = date_strs

            normalized_close[code] = _normalized_close(closes)

            today = raw_dates[-1] if raw_dates else date.today()
            signals_by_code[code] = detect_signals(bars, today)

            s: dict[str, IndicatorSeries] = {}

            def _add(name: str, arr: np.ndarray) -> None:
                s[name] = IndicatorSeries(name=name, dates=raw_dates, values=_nan_to_none(arr))

            _add("sma_5", sma(closes, 5))
            _add("sma_20", sma(closes, 20))
            _add("sma_60", sma(closes, 60))
            _add("ema_12", ema(closes, 12))
            _add("ema_26", ema(closes, 26))
            _add("rsi_14", rsi(closes, 14))
            macd_d = macd(closes)
            _add("macd", macd_d["macd"])
            _add("macd_signal", macd_d["signal"])
            _add("macd_hist", macd_d["hist"])
            bb = bollinger(closes, 20)
            _add("bb_upper", bb["upper"])
            _add("bb_mid", bb["mid"])
            _add("bb_lower", bb["lower"])

            series_by_code[code] = s

        corr = _compute_correlation_matrix(closes_map, raw_dates_map)

        return CompareSignalsBundle(
            codes=codes,
            period_days=days,
            series_by_code=series_by_code,
            dates_by_code=dates_by_code,
            normalized_close=normalized_close,
            signals_by_code=signals_by_code,
            correlation_matrix=corr,
        )

    def dividend_bundle(self, codes: list[str]) -> CompareDividendBundle:
        codes = list(dict.fromkeys(codes))

        fundamentals: dict[str, Optional[FundamentalReport]] = {}
        dividend_history: dict[str, list[DpsRow]] = {}
        radar_normalized: dict[str, dict[str, float]] = {}

        for code in codes:
            report = get_fundamental_report(code)
            fundamentals[code] = report

            # DPS 歷史
            cache_path = fundamental_module._cache_path(code)
            dps_rows: list[DpsRow] = []
            if cache_path.exists():
                try:
                    import pandas as pd
                    df = pd.read_csv(cache_path)
                    if "year" in df.columns and "dps" in df.columns:
                        for _, row in df.iterrows():
                            try:
                                dps_rows.append(DpsRow(year=int(row["year"]), dps=float(row["dps"]) if pd.notna(row["dps"]) else None))
                            except Exception:
                                pass
                except Exception:
                    pass
            dividend_history[code] = dps_rows

            # 雷達正規化（8 軸 0–100）
            if report:
                radar: dict[str, float] = {}
                for m in report.metrics:
                    radar[m.metric] = _SCORE_MAP.get(m.score, 50.0)
                radar_normalized[code] = radar
            else:
                radar_normalized[code] = {}

        return CompareDividendBundle(
            codes=codes,
            fundamentals=fundamentals,
            dividend_history=dividend_history,
            radar_normalized=radar_normalized,
        )


_svc: Optional[CompareService] = None


def get_compare_service() -> CompareService:
    global _svc
    if _svc is None:
        _svc = CompareService()
    return _svc
