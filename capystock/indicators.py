"""技術指標計算引擎 — 純 NumPy 實作，無 IO 副作用。

所有函式接收 np.ndarray（或可轉換的 list），回傳同長度陣列，
不足 warm-up 期的位置填 np.nan。
JSON 序列化時 NaN → None（呼叫端負責）。
"""
from __future__ import annotations

from datetime import date
from typing import Literal

import numpy as np
from pydantic import BaseModel


# ─────────────────────────── 基礎指標函式 ────────────────────────────

def sma(closes: np.ndarray, period: int) -> np.ndarray:
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    out = np.full(n, np.nan)
    if period > n:
        return out
    for i in range(period - 1, n):
        out[i] = closes[i - period + 1 : i + 1].mean()
    return out


def ema(closes: np.ndarray, period: int) -> np.ndarray:
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    out = np.full(n, np.nan)
    if period > n:
        return out
    k = 2.0 / (period + 1)
    # 以第一個完整 SMA 作為種子
    out[period - 1] = closes[:period].mean()
    for i in range(period, n):
        out[i] = closes[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder smoothing RSI；前 period 個位置為 NaN。"""
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # 第一個平均（SMA seed）
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()

    if avg_loss == 0:
        out[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[period] = 100.0 - 100.0 / (1.0 + rs)

    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - 100.0 / (1.0 + rs)

    return out


def macd(
    closes: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, np.ndarray]:
    """回傳 {'macd': arr, 'signal': arr, 'hist': arr}。"""
    closes = np.asarray(closes, dtype=float)
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)
    macd_line = fast_ema - slow_ema  # NaN where either is NaN

    # signal line = EMA(macd_line, signal)
    # 需要從第一個有效 macd 值開始算
    first_valid = slow - 1  # index of first non-NaN in slow_ema
    n = len(closes)
    sig_line = np.full(n, np.nan)
    hist = np.full(n, np.nan)

    # 取出有效段落做 EMA
    if n > first_valid + signal:
        valid_macd = macd_line[first_valid:]
        sig_segment = _ema_from_array(valid_macd, signal)
        sig_line[first_valid:] = sig_segment
        hist[first_valid:] = macd_line[first_valid:] - sig_segment

    return {"macd": macd_line, "signal": sig_line, "hist": hist}


def _ema_from_array(arr: np.ndarray, period: int) -> np.ndarray:
    """對完整陣列（無前置 NaN）計算 EMA。"""
    n = len(arr)
    out = np.full(n, np.nan)
    if period > n:
        return out
    k = 2.0 / (period + 1)
    out[period - 1] = arr[:period].mean()
    for i in range(period, n):
        out[i] = arr[i] * k + out[i - 1] * (1 - k)
    return out


def bollinger(
    closes: np.ndarray,
    period: int = 20,
    num_std: float = 2.0,
) -> dict[str, np.ndarray]:
    """回傳 {'mid', 'upper', 'lower', 'bandwidth', 'percent_b'}。"""
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    mid = sma(closes, period)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    bandwidth = np.full(n, np.nan)
    percent_b = np.full(n, np.nan)

    for i in range(period - 1, n):
        std = closes[i - period + 1 : i + 1].std(ddof=1)
        upper[i] = mid[i] + num_std * std
        lower[i] = mid[i] - num_std * std
        bw = upper[i] - lower[i]
        bandwidth[i] = bw / mid[i] if mid[i] != 0 else np.nan
        percent_b[i] = (closes[i] - lower[i]) / bw if bw != 0 else np.nan

    return {
        "mid": mid,
        "upper": upper,
        "lower": lower,
        "bandwidth": bandwidth,
        "percent_b": percent_b,
    }


def atr(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    out = np.full(n, np.nan)
    if n < 2:
        return out

    tr = np.full(n, np.nan)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    if period > n:
        return out

    # Wilder smoothing
    out[period - 1] = tr[:period].mean()
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period

    return out


def stoch_kd(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    k_period: int = 9,
    d_period: int = 3,
) -> dict[str, np.ndarray]:
    """Stochastic KD；回傳 {'k': arr, 'd': arr}。"""
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    raw_k = np.full(n, np.nan)

    for i in range(k_period - 1, n):
        hh = highs[i - k_period + 1 : i + 1].max()
        ll = lows[i - k_period + 1 : i + 1].min()
        denom = hh - ll
        raw_k[i] = (closes[i] - ll) / denom * 100 if denom != 0 else 50.0

    k = sma(raw_k, d_period)  # %K smoothed
    d = sma(k, d_period)       # %D = SMA(K, d_period)

    return {"k": k, "d": d}


# ─────────────────────── 訊號偵測層 ──────────────────────────────────

SignalName = Literal[
    "rsi_oversold",
    "rsi_overbought",
    "macd_golden_cross",
    "macd_dead_cross",
    "bb_breakout_up",
    "bb_breakout_down",
    "sma_golden_cross_5_20",
    "sma_dead_cross_5_20",
]


class IndicatorSignal(BaseModel):
    name: SignalName
    date: date
    value: float
    strength: float  # 0~1


class PriceBar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def detect_signals(
    prices: list[PriceBar], today: date, lookback_days: int = 14
) -> list[IndicatorSignal]:
    """偵測最近 lookback_days 天內觸發的技術訊號（非僅當日）。"""
    if len(prices) < 27:
        return []

    closes = np.array([p.close for p in prices], dtype=float)
    dates = [p.date for p in prices]

    rsi_arr = rsi(closes)
    macd_d = macd(closes)
    bb = bollinger(closes)
    sma5 = sma(closes, 5)
    sma20 = sma(closes, 20)

    signals: list[IndicatorSignal] = []

    def _ok(*vals: float) -> bool:
        return all(not np.isnan(v) for v in vals)

    # 掃最近 lookback_days 天
    try:
        end_idx = dates.index(today)
    except ValueError:
        end_idx = len(dates) - 1

    start_idx = max(1, end_idx - lookback_days + 1)

    for idx in range(start_idx, end_idx + 1):
        d = dates[idx]

        # RSI
        if _ok(rsi_arr[idx], rsi_arr[idx - 1]):
            if rsi_arr[idx - 1] >= 30 and rsi_arr[idx] < 30:
                signals.append(IndicatorSignal(
                    name="rsi_oversold", date=d,
                    value=float(rsi_arr[idx]),
                    strength=min(1.0, (30 - rsi_arr[idx]) / 30),
                ))
            if rsi_arr[idx - 1] <= 70 and rsi_arr[idx] > 70:
                signals.append(IndicatorSignal(
                    name="rsi_overbought", date=d,
                    value=float(rsi_arr[idx]),
                    strength=min(1.0, (rsi_arr[idx] - 70) / 30),
                ))

        # MACD
        m, s, h = macd_d["macd"], macd_d["signal"], macd_d["hist"]
        if _ok(m[idx], s[idx], m[idx - 1], s[idx - 1], h[idx], h[idx - 1]):
            if m[idx - 1] <= s[idx - 1] and m[idx] > s[idx] and h[idx] > 0:
                signals.append(IndicatorSignal(
                    name="macd_golden_cross", date=d,
                    value=float(h[idx]), strength=min(1.0, abs(h[idx]) / (abs(m[idx]) + 1e-9)),
                ))
            if m[idx - 1] >= s[idx - 1] and m[idx] < s[idx]:
                signals.append(IndicatorSignal(
                    name="macd_dead_cross", date=d,
                    value=float(h[idx]), strength=min(1.0, abs(h[idx]) / (abs(m[idx]) + 1e-9)),
                ))

        # Bollinger
        if _ok(bb["upper"][idx], bb["lower"][idx], bb["upper"][idx - 1], bb["lower"][idx - 1]):
            if closes[idx] > bb["upper"][idx] and closes[idx - 1] <= bb["upper"][idx - 1]:
                signals.append(IndicatorSignal(
                    name="bb_breakout_up", date=d,
                    value=float(closes[idx]),
                    strength=min(1.0, (closes[idx] - bb["upper"][idx]) / (bb["upper"][idx] * 0.02 + 1e-9)),
                ))
            if closes[idx] < bb["lower"][idx] and closes[idx - 1] >= bb["lower"][idx - 1]:
                signals.append(IndicatorSignal(
                    name="bb_breakout_down", date=d,
                    value=float(closes[idx]),
                    strength=min(1.0, (bb["lower"][idx] - closes[idx]) / (bb["lower"][idx] * 0.02 + 1e-9)),
                ))

        # SMA 5/20
        if _ok(sma5[idx], sma20[idx], sma5[idx - 1], sma20[idx - 1]):
            if sma5[idx - 1] <= sma20[idx - 1] and sma5[idx] > sma20[idx]:
                signals.append(IndicatorSignal(
                    name="sma_golden_cross_5_20", date=d,
                    value=float(sma5[idx]),
                    strength=min(1.0, (sma5[idx] - sma20[idx]) / (sma20[idx] * 0.01 + 1e-9)),
                ))
            if sma5[idx - 1] >= sma20[idx - 1] and sma5[idx] < sma20[idx]:
                signals.append(IndicatorSignal(
                    name="sma_dead_cross_5_20", date=d,
                    value=float(sma5[idx]),
                    strength=min(1.0, (sma20[idx] - sma5[idx]) / (sma20[idx] * 0.01 + 1e-9)),
                ))

    # 同日同訊號只保留最後一筆，按日期降序
    seen: set[tuple] = set()
    deduped: list[IndicatorSignal] = []
    for sig in reversed(signals):
        key = (sig.name, sig.date)
        if key not in seen:
            seen.add(key)
            deduped.append(sig)
    return sorted(deduped, key=lambda s: s.date, reverse=True)
