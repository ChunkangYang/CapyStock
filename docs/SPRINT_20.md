# Sprint 20 — 投資部門別 ingest（JPX 週報）

依賴：[MILESTONE_06.md](MILESTONE_06.md)

## 目的
- JPX 每週四發佈「投資部門別売買状況」Excel
- 解析後寫入 `data/cache/{CODE}_flow.csv`（個股別需另解 — 實務上只能對 ETF 用）
- 個股 flow：fallback 用「等比例分配」估算 — 標 estimated=true，UI 上以虛線顯示

## 檔案
- `capystock/ingest/jpx_flow.py`
- `tests/fixtures/jpx_weekly_2026wXX.xlsx`

## 處理流程
1. 下載 `https://www.jpx.co.jp/markets/statistics-equities/investor-type/...`（最新一份）
2. `pandas.read_excel(sheet_name='総合')` → 取「外資」「個人」「投信」三大類週淨買賣（億日圓）
3. 寫入 `data/cache/_market_flow.csv`（不分個股）
4. 對個股：呼叫時若 `_flow.csv` 缺，用市場 flow × (個股成交額 / 市場成交額) 估算，標 estimated=true

## Endpoints

| Method | Path | 說明 |
|---|---|---|
| POST | `/api/v1/ingest/jpx-weekly` | 抓取最新週報；body `{week?: "2026-W17"}` |
| GET | `/api/v1/ingest/market-flow?weeks=12` | 市場層級 flow |

## 驗收
- Fixture xlsx → parse 後欄位齊全；億日圓單位
- 估算個股 flow：給定市場 = (1000, -500, 300) 億，個股佔 0.5% → 個股 = (5, -2.5, 1.5) 億
- API：抓取 JPX mock 後 `_market_flow.csv` 出現
