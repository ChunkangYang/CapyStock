"""海龜投資法（Turtle Trading）核心計算函式 — 全部為純函式，方便單測。

只做多、System 2（55 日突破，不看「上一筆是否獲利」）。這裡只放「算一個數字/
判一個布林值」的最小單位，不碰 I/O、不依賴 pandas/FastAPI，讓 `test_turtle.py`
可以用手算的小案例逐一驗證。逐日事件驅動的完整模擬在 `scripts/backtest_turtle.py`
與 `api/services/turtle_trade_service.py`。

規則細節與理由見 `docs/TURTLE_STRATEGY.md`。
"""
from __future__ import annotations

import math
from typing import Optional, Sequence


def true_range(high: float, low: float, prev_close: Optional[float]) -> float:
    """單日 True Range。

    `TR = max(high-low, |high-prev_close|, |low-prev_close|)`。
    第一天沒有 prev_close 時退化成當日高低差（無法算跳空幅度）。
    """
    if prev_close is None:
        return float(high) - float(low)
    return max(
        float(high) - float(low),
        abs(float(high) - float(prev_close)),
        abs(float(low) - float(prev_close)),
    )


def n_value(true_ranges: Sequence[float], period: int = 20) -> Optional[float]:
    """N（波動單位）＝最近 `period` 天 True Range 的簡單平均。

    資料不足 `period` 天回傳 None（暖身期間不可用，呼叫端應跳過）。
    """
    if len(true_ranges) < period:
        return None
    window = true_ranges[-period:]
    return sum(window) / period


def donchian_high(closes: Sequence[float], window: int) -> Optional[float]:
    """過去 `window` 個交易日（不含當日）收盤價最高值。

    `closes` 應只包含「當日之前」的收盤序列（呼叫端自行切片，不含當日）。
    資料不足 `window` 天回傳 None。
    """
    if len(closes) < window:
        return None
    return max(closes[-window:])


def donchian_low(closes: Sequence[float], window: int) -> Optional[float]:
    """過去 `window` 個交易日（不含當日）收盤價最低值。同 `donchian_high`。"""
    if len(closes) < window:
        return None
    return min(closes[-window:])


def unit_size(
    equity: float,
    n: float,
    *,
    unit_risk_pct: float,
    lot_size: int,
    price: Optional[float] = None,
    cash: Optional[float] = None,
) -> int:
    """1 個 unit 的股數：`floor(equity × unit_risk_pct / N)`，再無條件捨去到 lot 整數倍。

    - N<=0 或算出來 <1 lot → 回 0（呼叫端視為「跳過」）。
    - 若給了 `price` 與 `cash`（現金上限），股數也不可超過現金買得起的 lot 數。
    """
    if n is None or n <= 0 or equity <= 0:
        return 0
    raw_shares = equity * unit_risk_pct / n
    shares = int(math.floor(raw_shares / lot_size) * lot_size)
    if price is not None and cash is not None and price > 0:
        affordable = int(math.floor(cash / price / lot_size) * lot_size)
        shares = min(shares, affordable)
    return max(shares, 0)


def pyramid_trigger(
    current_price: float,
    last_fill_price: float,
    n: float,
    *,
    add_n_mult: float = 0.5,
) -> bool:
    """判斷是否該加碼：現價 ≥ 最近一次加碼/進場價 + `add_n_mult` × N。"""
    if n is None or n <= 0:
        return False
    return current_price >= last_fill_price + add_n_mult * n


def stop_line_for_unit(fill_price: float, n: float, *, stop_n_mult: float = 2.0) -> float:
    """這次加碼/進場的停損線＝進場/加碼價 − stop_n_mult × N。"""
    return float(fill_price) - stop_n_mult * float(n)


def tighten_stop(current_stop: Optional[float], candidate_stop: float) -> float:
    """停損只升不降：回傳 `max(current_stop, candidate_stop)`。

    首次進場（current_stop 為 None）直接採用 candidate_stop。
    """
    if current_stop is None:
        return candidate_stop
    return max(current_stop, candidate_stop)
