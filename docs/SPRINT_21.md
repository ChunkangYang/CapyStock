# Sprint 21 — 異常偵測 + 事件研究

依賴：[MILESTONE_06.md](MILESTONE_06.md)

## 目的
- **異常成交量**：今日 volume > N × 過去 20 日均量 → 標記
- **異常價格波動**：今日 |return| > K × 20 日 std → 標記
- **事件研究**：給定一組事件日期（例：法說會、EDINET 5% 申報），計算 CAR

## 檔案
- `api/services/anomaly_service.py`
- `api/services/event_study_service.py`
- `api/routers/analytics.py`
- `api/schemas/analytics.py`

## Anomaly

```python
class AnomalyEvent(BaseModel):
    code: str
    date: date
    type: Literal["volume_spike", "price_jump", "gap_up", "gap_down"]
    value: float       # 倍率或 %
    threshold: float
    severity: Literal["info", "warn", "critical"]

class AnomalyService:
    def scan(self, code: str, days: int=90,
             volume_multiplier: float=3.0, price_sigma: float=2.5,
             gap_pct: float=0.05) -> list[AnomalyEvent]: ...
```

## Event Study

```python
class EventStudyResult(BaseModel):
    code: str
    events: list[date]
    window_days: tuple[int, int]   # (-5, +20)
    aar: list[float]
    car: list[float]
    n_events: int
    benchmark: str

class EventStudyService:
    def run(self, code: str, events: list[date], window: tuple[int,int]=(-5, 20),
            benchmark: Literal["TOPIX", "self_mean"]="self_mean") -> EventStudyResult:
        """
        AR_t = R_stock_t - R_benchmark_t
        AAR = mean over events
        CAR = cumsum(AAR)
        """
```

- benchmark `self_mean`：用該股票過去 60 日平均報酬
- benchmark `TOPIX`：需先有 `data/cache/_topix_price.csv`（暫先實作 self_mean）

## Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/analytics/anomaly/{code}?days=90` | 列出異常事件 |
| POST | `/api/v1/analytics/event-study/{code}` | body `{events: [date], window?: [-5, 20]}` |

## 驗收（自動化）

- Anomaly：人工序列 20 日均量 = 100，第 21 日 = 400 → 觸發 volume_spike value=4.0
- Anomaly：缺資料天 → 不 raise、不誤報
- Event study：構造已知 AR 序列 → CAR 與手算逐 offset 相符
- 0 events → n_events=0，aar/car 空陣列
- API：錯誤 events 格式 → 422
