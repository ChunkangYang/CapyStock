"""S15 驗收測試 — 指標 API + 服務整合。"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from api.schemas.indicator import IndicatorBundle, IndicatorSeries
from api.services.indicator_service import IndicatorService, DEFAULT_INCLUDE
from capystock.indicators import IndicatorSignal, PriceBar


# ──────── Fixture：產生假價格資料 ────────

def _make_price_df(n: int = 150):
    """產生 n 筆單調遞增收盤價的假 DataFrame。"""
    import pandas as pd
    base = date(2025, 1, 1)
    rows = []
    for i in range(n):
        rows.append({
            "date": (base + timedelta(days=i)).isoformat(),
            "open": 100.0 + i * 0.1,
            "high": 101.0 + i * 0.1,
            "low": 99.0 + i * 0.1,
            "close": 100.0 + i * 0.1,
            "volume": 1000.0,
        })
    return pd.DataFrame(rows)


def _make_bars(n: int = 150) -> list[PriceBar]:
    base = date(2025, 1, 1)
    return [
        PriceBar(
            date=base + timedelta(days=i),
            open=100.0 + i * 0.1,
            high=101.0 + i * 0.1,
            low=99.0 + i * 0.1,
            close=100.0 + i * 0.1,
            volume=1000.0,
        )
        for i in range(n)
    ]


# ──────── IndicatorService 測試 ────────

class TestIndicatorService:
    def _make_service(self, n: int = 150) -> IndicatorService:
        svc = IndicatorService()
        return svc

    def _patched_bundle(self, code: str = "7203", days: int = 120, include=None, n: int = 150):
        df = _make_price_df(n)
        with patch("api.services.indicator_service.scraper") as mock_scraper:
            mock_scraper.fetch_price.return_value = (df, None)
            svc = IndicatorService()
            return svc.get_bundle(code, days=days, include=include)

    def test_default_include_all_series_present(self):
        bundle = self._patched_bundle()
        for name in DEFAULT_INCLUDE:
            assert name in bundle.series, f"Missing series: {name}"

    def test_series_length_equals_price_length(self):
        days = 120
        bundle = self._patched_bundle(days=days, n=200)
        for name, series in bundle.series.items():
            assert len(series.dates) == len(series.values), f"dates/values mismatch in {name}"
            assert len(series.values) == days, f"Expected {days}, got {len(series.values)} for {name}"

    def test_nan_serialized_as_none(self):
        bundle = self._patched_bundle(days=120, n=200)
        rsi_series = bundle.series.get("rsi_14")
        assert rsi_series is not None
        # 前 14 個點應為 None（warm-up）
        assert rsi_series.values[0] is None

    def test_include_filter_limits_series(self):
        bundle = self._patched_bundle(include=["rsi_14", "macd"])
        assert set(bundle.series.keys()) == {"rsi_14", "macd"}

    def test_empty_price_returns_empty_bundle(self):
        import pandas as pd
        with patch("api.services.indicator_service.scraper") as mock_scraper:
            mock_scraper.fetch_price.return_value = (pd.DataFrame(), None)
            svc = IndicatorService()
            bundle = svc.get_bundle("9999", days=120)
        assert bundle.series == {}
        assert bundle.signals == []

    def test_signals_list_is_valid(self):
        bundle = self._patched_bundle(n=200)
        for sig in bundle.signals:
            assert isinstance(sig, IndicatorSignal)
            assert sig.name in [
                "rsi_oversold", "rsi_overbought",
                "macd_golden_cross", "macd_dead_cross",
                "bb_breakout_up", "bb_breakout_down",
                "sma_golden_cross_5_20", "sma_dead_cross_5_20",
            ]


# ──────── SignalResult 技術指標整合測試 ────────

class TestSignalResultIndicators:
    def test_analyze_one_returns_indicator_signals_and_score(self):
        from api.services.signal_service import analyze_one
        from capystock.analyzer import Snapshot

        df = _make_price_df(150)
        mock_snap = MagicMock(spec=Snapshot)
        mock_snap.code = "7203"
        mock_snap.name = "Toyota"
        mock_snap.latest_price = 100.0
        mock_snap.latest_date = None
        mock_snap.price_vs_start_pct = 0.0
        mock_snap.price_vs_recent_low_pct = 0.0
        mock_snap.cond_inst_sell = False
        mock_snap.cond_margin_surge = False
        mock_snap.cond_price_rise = False
        mock_snap.stop_loss_triggered = False
        mock_snap.accumulation_signal = False
        mock_snap.flow_recent = []
        mock_snap.margin_trend_note = ""
        mock_snap.notes = []

        with patch("api.services.signal_service.scraper") as mock_scraper, \
             patch("api.services.signal_service.analyzer") as mock_analyzer:
            mock_scraper.fetch_price.return_value = (df, None)
            mock_scraper.fetch_margin.return_value = None
            mock_scraper.fetch_flow.return_value = None
            mock_scraper.fetch_name.return_value = "Toyota"
            mock_analyzer.analyze.return_value = (mock_snap, [])

            result = analyze_one("7203", start_price=100.0)

        assert hasattr(result, "indicator_signals")
        assert hasattr(result, "technical_score")
        assert isinstance(result.indicator_signals, list)
        assert isinstance(result.technical_score, float)
        assert -3.0 <= result.technical_score <= 3.0


# ──────── technical_score 計算測試 ────────

class TestTechnicalScore:
    def test_score_bounds(self):
        from api.services.signal_service import _compute_technical_score

        many_signals = [
            IndicatorSignal(name="macd_golden_cross", date=date.today(), value=1.0, strength=1.0),
            IndicatorSignal(name="sma_golden_cross_5_20", date=date.today(), value=1.0, strength=1.0),
            IndicatorSignal(name="rsi_oversold", date=date.today(), value=25.0, strength=0.5),
            IndicatorSignal(name="bb_breakout_up", date=date.today(), value=100.0, strength=0.3),
        ]
        score = _compute_technical_score(many_signals)
        assert score == 3.0  # clamped

        negative_signals = [
            IndicatorSignal(name="macd_dead_cross", date=date.today(), value=-1.0, strength=1.0),
            IndicatorSignal(name="sma_dead_cross_5_20", date=date.today(), value=-1.0, strength=1.0),
            IndicatorSignal(name="rsi_overbought", date=date.today(), value=75.0, strength=0.5),
            IndicatorSignal(name="bb_breakout_down", date=date.today(), value=90.0, strength=0.3),
        ]
        score = _compute_technical_score(negative_signals)
        assert score == -3.0  # clamped

    def test_empty_signals_score_zero(self):
        from api.services.signal_service import _compute_technical_score
        assert _compute_technical_score([]) == 0.0


# ──────── scan_service include_technical 測試 ────────

class TestScanServiceTechnical:
    def test_compute_score_without_technical(self):
        from api.services.scan_service import compute_score

        mock_result = MagicMock()
        mock_result.alerts = []
        mock_result.technical_score = 2.0

        score_with = compute_score(mock_result, [], include_technical=True)
        score_without = compute_score(mock_result, [], include_technical=False)

        assert score_with == 2
        assert score_without == 0

    def test_compute_score_matches_existing_without_technical(self):
        from api.services.scan_service import compute_score

        mock_result = MagicMock()
        mock_result.alerts = []
        mock_result.technical_score = 1.5

        score = compute_score(mock_result, [{"doc_type_code": "350"}], include_technical=False)
        assert score == 2  # EDINET 350 → +2, no technical
