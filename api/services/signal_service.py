"""訊號分析服務（從 CLI 邏輯抽取成可重用服務）。"""
from datetime import date
from typing import Optional

import pandas as pd

from capystock import analyzer, edinet, scraper, storage
from capystock.indicators import IndicatorSignal, PriceBar as IndicatorPriceBar, detect_signals
from api.schemas.common import (
    Alert, MarginRow, PriceBar, SignalConditions, SignalResult,
)


def get_price_history(code: str, days: int = 90) -> list[PriceBar]:
    """取得股價 K 線歷史。"""
    df, _ = scraper.fetch_price(code, days=days)
    if df is None or df.empty:
        return []

    # 轉換為 schema
    bars = []
    for _, row in df.iterrows():
        try:
            bars.append(PriceBar(
                date=pd.Timestamp(row["date"]).date(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            ))
        except (KeyError, ValueError, TypeError):
            continue

    # 只保留最後 N 天
    if len(bars) > days:
        bars = bars[-days:]
    return bars


def get_margin_history(code: str, weeks: int = 12) -> list[MarginRow]:
    """取得信用殘歷史。"""
    df = scraper.fetch_margin(code)
    if df is None or df.empty:
        return []

    rows = []
    for _, row in df.iterrows():
        try:
            rows.append(MarginRow(
                week=pd.Timestamp(row["week"]).date(),
                margin_long=float(row["margin_long"]),
                margin_short=float(row["margin_short"]),
                ratio=float(row.get("ratio")) if pd.notna(row.get("ratio")) else None,
            ))
        except (KeyError, ValueError, TypeError):
            continue

    if len(rows) > weeks:
        rows = rows[-weeks:]
    return rows


def get_edinet_events(code: str, days: int = 30) -> list[dict]:
    """取得 EDINET 5% rule 事件（需要 EDINET_API_KEY）。"""
    # 簡化實現：直接調用 edinet 模組
    from capystock import config
    if not config.EDINET_API_KEY:
        return []
    try:
        reports = edinet.fetch_since(days=days, codes={code})
        return [
            {
                "date": r["submit_date"],
                "filer": r["filer_name"],
                "doc_type": r["doc_type_code"],
                "pdf_url": r["pdf_url"],
            }
            for r in reports
        ]
    except Exception:
        return []


_SIGNAL_WEIGHTS = {
    "macd_golden_cross": 1.0,
    "macd_dead_cross": -1.0,
    "sma_golden_cross_5_20": 1.0,
    "sma_dead_cross_5_20": -1.0,
    "rsi_oversold": 0.5,
    "rsi_overbought": -0.5,
    "bb_breakout_up": 0.5,
    "bb_breakout_down": -0.5,
}


def _compute_technical_score(signals: list[IndicatorSignal]) -> float:
    score = sum(_SIGNAL_WEIGHTS.get(s.name, 0.0) for s in signals)
    return float(max(-3.0, min(3.0, score)))


def analyze_one(
    code: str,
    name: str = "",
    start_price: Optional[float] = None,
    price_df: Optional[pd.DataFrame] = None,
) -> SignalResult:
    """分析單檔股票訊號。

    Args:
        code: 股票代碼
        name: 股票名稱（若為空，會自動爬取）
        start_price: 起始價（若為 None，視為非 watchlist 股票）
        price_df: 預先下載的價格 DataFrame（批次掃描用，傳入則跳過 HTTP 爬取）
    """
    if not name:
        name = scraper.fetch_name(code) or ""

    if price_df is None:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as executor:
            price_future = executor.submit(scraper.fetch_price, code)
            margin_future = executor.submit(scraper.fetch_margin, code)
            price_df, _ = price_future.result()
            margin_df = margin_future.result()
    else:
        if isinstance(price_df, pd.DataFrame) and price_df.empty:
            price_df = None
        margin_df = scraper.fetch_margin(code)

    # 有傳入真實 start_price → 持倉/追蹤視角（停損等持倉專屬訊號適用）；
    # 沒傳入（全市場掃描）→ 用最新價當佔位，holdings_context=False 跳過持倉專屬訊號。
    holdings_context = start_price is not None
    if start_price is None:
        if price_df is not None and len(price_df) > 0:
            start_price = float(price_df.iloc[-1]["close"])
        else:
            start_price = 0.0

    snap, alerts = analyzer.analyze(
        code, name, start_price, price_df, margin_df,
        holdings_context=holdings_context,
    )

    conditions = SignalConditions(
        cond_margin_surge=snap.cond_margin_surge,
        cond_price_rise=snap.cond_price_rise,
        matched=sum([snap.cond_margin_surge, snap.cond_price_rise]),
    )

    schema_alerts = [
        Alert(
            alert_type=a["alert_type"],
            severity=a["severity"],
            message=a["message"],
            details=a.get("details", {}),
        )
        for a in alerts
    ]

    # 計算技術指標訊號
    indicator_signals: list[IndicatorSignal] = []
    technical_score: float = 0.0
    try:
        if price_df is not None and not price_df.empty:
            ind_bars: list[IndicatorPriceBar] = []
            for _, row in price_df.iterrows():
                try:
                    ind_bars.append(IndicatorPriceBar(
                        date=pd.Timestamp(row["date"]).date(),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume", 0)),
                    ))
                except (KeyError, ValueError, TypeError):
                    continue

            if ind_bars:
                today_date = ind_bars[-1].date
                indicator_signals = detect_signals(ind_bars, today_date)
                technical_score = _compute_technical_score(indicator_signals)
    except Exception:
        pass

    return SignalResult(
        code=snap.code,
        name=snap.name,
        latest_price=snap.latest_price,
        latest_date=snap.latest_date.date() if snap.latest_date else None,
        start_price=start_price,
        price_vs_start_pct=snap.price_vs_start_pct,
        price_vs_recent_low_pct=snap.price_vs_recent_low_pct,
        conditions=conditions,
        stop_loss_triggered=snap.stop_loss_triggered,
        trailing_stop_stage=snap.trailing_stop_stage,
        trailing_stop_price=snap.trailing_stop_price,
        trailing_stop_triggered=snap.trailing_stop_triggered,
        trailing_stop_anchor=snap.trailing_stop_anchor,
        atr_14=snap.atr_14,
        exit_warnings=snap.exit_warnings,
        margin_trend_note=snap.margin_trend_note,
        notes=snap.notes,
        alerts=schema_alerts,
        indicator_signals=indicator_signals,
        technical_score=technical_score,
    )


def analyze_watchlist() -> list[SignalResult]:
    """分析整個追蹤清單的訊號。"""
    wl = storage.load_watchlist()
    results = []
    for code, entry in wl.items():
        try:
            name = entry.get("name", "") if isinstance(entry, dict) else ""
            start_price = entry.get("start_price") if isinstance(entry, dict) else None
            result = analyze_one(code, name=name, start_price=start_price)
            results.append(result)
        except Exception:
            # 單檔失敗不中斷，記錄為空結果
            continue
    return results
