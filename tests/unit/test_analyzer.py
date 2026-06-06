"""analyzer 單元測試：吃貨（籌碼沉澱）重定義 + 停損分層（holdings_context）。"""
from datetime import datetime, timedelta

import pandas as pd

from capystock import analyzer, config


def _price_df(closes, volumes=None):
    """由收盤序列建 price_df（date/open/high/low/close/volume）。"""
    n = len(closes)
    base = datetime(2026, 5, 1)
    if volumes is None:
        volumes = [1000.0] * n
    return pd.DataFrame({
        "date": [base + timedelta(days=i) for i in range(n)],
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": volumes,
    })


def _margin_df(longs):
    """由 margin_long 序列建週頻 margin_df。"""
    base = datetime(2026, 4, 1)
    return pd.DataFrame({
        "week": [base + timedelta(weeks=i) for i in range(len(longs))],
        "margin_long": longs,
        "margin_short": [100.0] * len(longs),
        "ratio": [1.0] * len(longs),
    })


def test_accumulation_fires_on_margin_decline_price_hold():
    """信用残連 3 週下降 + 股價撐住 + 量能維持 → 吃貨成立。"""
    closes = [100.0 + i * 0.5 for i in range(25)]  # 緩步上漲（撐住）
    price_df = _price_df(closes)
    margin_df = _margin_df([1000.0, 950.0, 900.0, 850.0])  # 連 3 週降

    snap, alerts = analyzer.analyze("9999", "TestCo", closes[-1], price_df, margin_df)

    assert snap.accumulation_signal is True
    assert any(a["alert_type"] == "accumulation" for a in alerts)


def test_accumulation_no_fire_when_margin_rising():
    """融資餘額上升 → 不算吃貨。"""
    closes = [100.0 + i * 0.5 for i in range(25)]
    price_df = _price_df(closes)
    margin_df = _margin_df([850.0, 900.0, 950.0, 1000.0])  # 上升

    snap, alerts = analyzer.analyze("9999", "TestCo", closes[-1], price_df, margin_df)

    assert snap.accumulation_signal is False
    assert not any(a["alert_type"] == "accumulation" for a in alerts)


def test_accumulation_no_fire_when_price_drops():
    """融資下降但股價同期下跌 → 不算吃貨（非沉澱，是潰散）。"""
    closes = [120.0 - i * 0.8 for i in range(25)]  # 下跌
    price_df = _price_df(closes)
    margin_df = _margin_df([1000.0, 950.0, 900.0, 850.0])

    snap, alerts = analyzer.analyze("9999", "TestCo", closes[-1], price_df, margin_df)

    assert snap.accumulation_signal is False


def test_accumulation_no_fire_when_volume_collapses():
    """量能崩潰（近 5 日均量遠低於 20 日均量）→ 不算吃貨。"""
    closes = [100.0 + i * 0.5 for i in range(25)]
    volumes = [1000.0] * 20 + [100.0] * 5  # 最近 5 日量縮到 1/10
    price_df = _price_df(closes, volumes)
    margin_df = _margin_df([1000.0, 950.0, 900.0, 850.0])

    snap, _ = analyzer.analyze("9999", "TestCo", closes[-1], price_df, margin_df)

    assert snap.accumulation_signal is False


def test_holdings_context_skips_stop_loss_in_market_scan():
    """holdings_context=False（全市場）跳過停損；=True（持倉）才算。"""
    # 股價一路下殺，若以「進場價 200」當錨點，連 2 日收盤遠低於 200×0.95
    closes = [200.0] + [150.0 - i for i in range(24)]
    price_df = _price_df(closes)

    # 全市場視角：start_price=最新價、holdings_context=False → 不應觸發停損
    market_snap, market_alerts = analyzer.analyze(
        "9999", "TestCo", closes[-1], price_df, None, holdings_context=False,
    )
    assert market_snap.stop_loss_triggered is False
    assert market_snap.trailing_stop_stage is None
    assert not any(a["alert_type"] == "stop_loss" for a in market_alerts)

    # 持倉視角：以高進場價 200 當錨點、holdings_context=True → 應觸發停損
    hold_snap, hold_alerts = analyzer.analyze(
        "9999", "TestCo", 200.0, price_df, None, holdings_context=True,
    )
    assert hold_snap.stop_loss_triggered is True
    assert any(a["alert_type"] == "stop_loss" for a in hold_alerts)
