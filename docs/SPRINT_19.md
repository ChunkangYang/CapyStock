# Sprint 19 — 信用残自動抓取（多來源 ingest 層）

依賴：[MILESTONE_06.md](MILESTONE_06.md)

## 目的
- 降低使用者手動準備 `data/cache/{CODE}_margin.csv` 的負擔
- source A 失敗自動 fallback 到 source B / C
- 永遠允許手動 CSV 上傳兜底

## 檔案
- `capystock/ingest/base.py`
- `capystock/ingest/yahoo_jp_margin.py` / `minkabu_margin.py` / `manual_csv.py`
- `api/services/ingest_service.py`
- `api/routers/ingest.py`
- `api/schemas/ingest.py`

## IngestionSource 抽象

```python
class IngestionResult(BaseModel):
    code: str
    kind: Literal["margin", "flow", "price"]
    source: str
    rows_fetched: int
    date_range: tuple[date, date]
    written_path: str | None
    ok: bool
    error: str | None

class IngestionSource(ABC):
    name: str
    kind: Literal["margin", "flow", "price"]
    @abstractmethod
    def fetch(self, code: str) -> pd.DataFrame: ...
    @abstractmethod
    def health_check(self) -> bool: ...
```

## Yahoo Japan margin
- URL：`https://finance.yahoo.co.jp/quote/{CODE}.T/credit_balance`
- 解析表格 → 欄位 normalize 到 `week, margin_long, margin_short, ratio`（千株）
- robots.txt 遵守：USER_AGENT = `config.USER_AGENT`，request delay 2s

## Minkabu fallback
- URL：`https://minkabu.jp/stock/{CODE}/`（信用倍率區塊）

## Manual CSV
- 接受多種欄位命名 alias：`margin_long` / `融資残` / `Long`
- 自動轉單位（如果偵測到「株」 而非「千株」）

## IngestService

```python
class IngestService:
    def fetch_margin(self, code: str, force: bool=False) -> IngestionResult:
        """依序試 sources；第一個成功即停。force=True 時繞過 24h cache"""

    def import_manual(self, code: str, kind: str, file_content: bytes) -> IngestionResult: ...

    def cache_age(self, code: str, kind: str) -> timedelta | None: ...
```

## Endpoints

| Method | Path | 說明 |
|---|---|---|
| POST | `/api/v1/ingest/margin/{code}` | body `{force?: false}` |
| POST | `/api/v1/ingest/flow/{code}` | 同上 |
| POST | `/api/v1/ingest/upload` | multipart `file`, form `code`, `kind` |
| GET | `/api/v1/ingest/status/{code}` | 各 kind cache age + last source used |

## 驗收（自動化）

- Yahoo：mock response（fixture HTML）→ parse 後欄位 / 數值正確（千株單位轉換）
- Minkabu：同上
- Manual CSV：上傳 5 種不同欄位名 fixture → 全部 normalize
- IngestService 失敗 fallback：Yahoo mock 拋 → 自動試 Minkabu → 成功；result.source = "minkabu"
- 全部失敗：result.ok=false、error 含每來源錯誤摘要
- API：upload 接收 file → 寫入 `data/cache/`、回 IngestionResult；force=true 時 mtime 更新

## 給實作者
- 爬蟲若 HTTP 403 → 印 warning 並回 ok=false（**不 raise**）
- 任何 ingest 失敗都不應該讓 `signal_service.analyze_one` 整個失敗
