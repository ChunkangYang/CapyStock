# Sprint 16 — 比較模式 service + 對比頁

依賴：[MILESTONE_05.md](MILESTONE_05.md)

## 目的
- 投機面板：兩到五檔同期 K 線疊加 + 指標對比
- 金雞面板：3 檔基本面雷達圖疊加 + DPS 趨勢並排

## 檔案
- `api/services/compare_service.py`
- `api/routers/compare.py`
- `api/schemas/compare.py`
- `frontend/src/routes/compare/+page.svelte`（投機）
- `frontend/src/routes/dividend/compare/+page.svelte`（金雞）
- `frontend/src/lib/components/ComparePanel.svelte`

## Service

```python
class CompareSignalsBundle(BaseModel):
    codes: list[str]
    period_days: int
    series_by_code: dict[str, dict]
    correlation_matrix: dict[str, dict[str, float]]

class CompareDividendBundle(BaseModel):
    codes: list[str]
    fundamentals: dict[str, FundamentalReport]
    dividend_history: dict[str, list[DpsRow]]
    radar_normalized: dict[str, dict[str, float]]

class CompareService:
    def signals_bundle(self, codes: list[str], days: int=120) -> CompareSignalsBundle: ...
    def dividend_bundle(self, codes: list[str]) -> CompareDividendBundle: ...
```

## correlation_matrix
- 各 code 計算 daily log return 序列，對齊交易日 → Pearson correlation
- 缺資料對齊：取所有 code 都有的日期交集

## Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/compare/signals?codes=7203,8058,9984&days=120` | 投機對比 |
| GET | `/api/v1/compare/dividend?codes=7203,8058,9984` | 金雞對比 |

## 限制
- codes 最多 5 檔；超過 422
- codes 重複自動去重

## 驗收（自動化）

- 對 3 檔 fixture，correlation_matrix 對角線 = 1.0、對稱、值在 [-1,1]
- 缺一檔資料的日期 → 該日不納入 correlation 計算
- codes=[] → 422；codes=6 檔 → 422
- 重複 codes=[7203,7203,8058] → 回 [7203, 8058]
- radar_normalized 每檔 8 軸 0–100
