# Sprint 14 — 技術指標計算引擎（核心）

依賴：[MILESTONE_05.md](MILESTONE_05.md)

## 目的
- 純函式可單獨測試（無 IO、無時間依賴）
- 介面接收 numpy array 或 list[float]，回傳同長度 array（不足期間填 NaN）

## 檔案
- `capystock/indicators.py`
- `tests/unit/test_indicators.py`
- `tests/fixtures/indicators_known_values.csv`：人工算好的標準答案

## API 設計

```python
# capystock/indicators.py
import numpy as np

def sma(closes: np.ndarray, period: int) -> np.ndarray: ...
def ema(closes: np.ndarray, period: int) -> np.ndarray: ...
def rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder smoothing；前 period 個 NaN"""
def macd(closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """{'macd': arr, 'signal': arr, 'hist': arr}"""
def bollinger(closes: np.ndarray, period: int = 20, num_std: float = 2.0) -> dict:
    """{'mid', 'upper', 'lower', 'bandwidth', 'percent_b'}"""
def atr(highs, lows, closes, period: int = 14) -> np.ndarray: ...
def stoch_kd(highs, lows, closes, k_period=9, d_period=3) -> dict: ...
```

## 訊號偵測層（基於指標）

```python
class IndicatorSignal(BaseModel):
    name: Literal["rsi_oversold", "rsi_overbought", "macd_golden_cross", "macd_dead_cross",
                  "bb_breakout_up", "bb_breakout_down", "sma_golden_cross_5_20",
                  "sma_dead_cross_5_20"]
    date: date
    value: float
    strength: float  # 0~1

def detect_signals(prices: list[PriceBar], today: date) -> list[IndicatorSignal]:
    """跑全部指標 → 偵測當日 / 前一日交叉與穿越"""
```

## 偵測規則（精確定義）

| Signal | 條件 |
|---|---|
| rsi_oversold | RSI(14) 從 ≥ 30 跌破 30（昨日 ≥30 今日 <30） |
| rsi_overbought | RSI(14) 從 ≤ 70 突破 70 |
| macd_golden_cross | MACD line 由下往上穿越 signal line 且 hist 由負轉正 |
| macd_dead_cross | MACD line 由上往下穿越 signal line |
| bb_breakout_up | close > upper band 且前一日 close ≤ upper |
| bb_breakout_down | close < lower band 且前一日 close ≥ lower |
| sma_golden_cross_5_20 | SMA5 由下穿 SMA20 |
| sma_dead_cross_5_20 | SMA5 由上穿 SMA20 |

## 驗收（自動化）

`pytest tests/unit/test_indicators.py -v`：

- RSI / MACD / BB 與 `pandas-ta` 結果（baseline → 寫入 fixture csv）容忍誤差 1e-6
- 邊界：input length < period → 全 NaN 不 raise
- 持平 input（全 100）→ RSI = 50；BB upper=lower=mid=100；MACD ≈ 0
- detect_signals：人工構造 22 日序列觸發每種訊號各一次，斷言 name + date 完全相符
- 性能：1000 點 RSI/MACD < 5ms

## 給實作者
- RSI 用 Wilder smoothing：`avg_gain = (prev_avg_gain*(p-1) + gain) / p`，不是簡單 SMA
- MACD signal line 是 EMA(MACD, signal_period)，不是 SMA
