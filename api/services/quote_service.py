"""即時報價服務（intraday quote）。

東證延遲約 20 分的最新成交價，**不落地寫檔** — intraday 報價不能混進日線
price CSV（會讓 analyzer 把盤中價當收盤算訊號）。module-level dict 做 in-memory
TTL 快取，避免短時間內對同一檔重複建 yfinance Ticker。

供 quote 端點與 portfolio_service._current_price 共用。
"""
from __future__ import annotations

import threading
import time
from typing import Optional

# code -> (fetched_ts, price)
_quote_cache: dict[str, tuple[float, float]] = {}
_quote_lock = threading.Lock()
_TTL_SEC = 300.0  # 5 分鐘


def get_quote(code: str) -> Optional[dict]:
    """回傳 {code, price, price_time, source}；失敗回 None。

    TTL 內第二次呼叫直接回快取，不再建 Ticker。
    """
    now = time.time()
    with _quote_lock:
        hit = _quote_cache.get(code)
        if hit is not None and now - hit[0] < _TTL_SEC:
            return {
                "code": code,
                "price": hit[1],
                "price_time": _fmt_ts(hit[0]),
                "source": "yfinance:cache",
            }

    price = _fetch_last_price(code)
    if price is None:
        return None

    fetched_ts = time.time()
    with _quote_lock:
        _quote_cache[code] = (fetched_ts, price)
    return {
        "code": code,
        "price": price,
        "price_time": _fmt_ts(fetched_ts),
        "source": "yfinance",
    }


def _fetch_last_price(code: str) -> Optional[float]:
    try:
        import yfinance as yf
    except ImportError:
        return None
    try:
        info = yf.Ticker(f"{code}.T").fast_info
        last = info.get("last_price") if hasattr(info, "get") else getattr(info, "last_price", None)
        if last is None:
            return None
        val = float(last)
        return val if val > 0 else None
    except Exception:
        return None


def _fmt_ts(ts: float) -> str:
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime("%H:%M")
