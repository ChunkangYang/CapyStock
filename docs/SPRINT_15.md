# Sprint 15 — 指標 API + 服務整合

依賴：[MILESTONE_05.md](MILESTONE_05.md)

## 目的
- 對外暴露指標時序（給前端畫圖）
- 把 indicator_signals 注入 `signal_service.analyze_one`

## 檔案
- `api/services/indicator_service.py`
- `api/services/signal_service.py`：擴 — 將 indicator_signals 加入 SignalResult
- `api/routers/indicators.py`
- `api/schemas/indicator.py`

## Service

```python
class IndicatorSeries(BaseModel):
    name: str          # "rsi" | "macd" | "macd_signal" | "macd_hist" | "bb_upper" ...
    dates: list[date]
    values: list[float | None]   # NaN → None

class IndicatorBundle(BaseModel):
    code: str
    period_days: int
    series: dict[str, IndicatorSeries]
    signals: list[IndicatorSignal]

class IndicatorService:
    def get_bundle(self, code: str, days: int = 120, include: list[str] = None) -> IndicatorBundle: ...
        # include 預設 ["sma_5","sma_20","sma_60","ema_12","ema_26","rsi_14","macd","bollinger_20"]
```

## SignalResult 擴充

```python
class SignalResult(BaseModel):
    # ... 原本欄位
    indicator_signals: list[IndicatorSignal] = []   # ★新增
    technical_score: float = 0.0                    # ★新增 -3~+3
```

## technical_score 計算
- 各 indicator_signal 加權：金叉 +1、死叉 -1；oversold +0.5；overbought -0.5；BB breakout up +0.5；down -0.5
- 截斷到 [-3, +3]

## scan signals score 融合
- 在 `scan_service.run_signals_scan` 中：`score_total = score_existing + technical_score`
- query param `?include_technical=true|false`（預設 true）

## Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/indicators/{code}?days=120&include=rsi,macd,bollinger` | 取 bundle |
| GET | `/api/v1/indicators/{code}/signals?days=30` | 只取訊號清單 |

## 驗收（自動化）

- get_bundle 預設 include 全帶；指定 `include=rsi_14,macd` → series dict 只含這兩組
- 對 fixture price_7203.csv 跑 → series length = price length；NaN → None 序列化正確
- SignalResult 內 indicator_signals 至少包含一筆；technical_score 與算出值一致
- include_technical=false 時 scan score 與舊版相同
