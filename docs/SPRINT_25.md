# Sprint 25 — 持倉管理（Portfolio）

依賴：[MILESTONE_06.md](MILESTONE_06.md)（追蹤清單已完成，持倉為獨立新機能）

## 背景

現有「追蹤清單（watchlist）」與 Dashboard 的「持倉狀態」語意混淆：
- **追蹤清單**：關注但尚未買入，作為訊號監控對象
- **持倉（Portfolio）**：已實際買入、持有中，需追蹤成本與損益

## 目標

1. 新增 `data/portfolio.json` 儲存已買入股票
2. CLI `portfolio` 子命令（add / list / close）
3. API `/portfolio` CRUD + 未實現損益計算
4. Dashboard 分區：持倉 vs 追蹤清單 清楚分開
5. `/portfolio` 專屬管理頁面

## 資料模型

```json
{
  "7203": {
    "code": "7203",
    "name": "トヨタ自動車",
    "lots": [
      {
        "id": "uuid4",
        "entry_price": 2800.0,
        "quantity": 100,
        "entry_date": "2026-04-01",
        "exit_price": null,
        "exit_date": null,
        "note": ""
      }
    ]
  }
}
```

- 同一股票可多批買入（lots）
- 賣出時填 `exit_price` + `exit_date`，保留歷史不刪除
- 未實現損益 = `(現價 - entry_price) × quantity`

## 任務清單

- [x] `docs/SPRINT_25.md`
- [ ] `capystock/config.py`：加 `PORTFOLIO_PATH`
- [ ] `capystock/portfolio.py`：load / save / add_lot / close_lot / list_open
- [ ] `capystock/main.py`：`portfolio` 子命令（add / list / close）
- [ ] `api/schemas/portfolio.py`
- [ ] `api/services/portfolio_service.py`：CRUD + 現價取得 + 損益計算
- [ ] `api/routers/portfolio.py`
- [ ] `api/main.py`：register router
- [ ] `frontend/src/lib/types.ts`：PortfolioLot / PortfolioEntry
- [ ] `frontend/src/routes/portfolio/+page.svelte`：持倉管理頁
- [ ] `frontend/src/routes/+page.svelte`：Dashboard 分 4 區塊
- [ ] `frontend/src/routes/+layout.svelte`：加側欄「持倉」連結

## 測試案例

| ID | 步驟 | 預期 |
|---|---|---|
| T25-01 | CLI `portfolio add 7203 2800 100` | portfolio.json 新增 lot |
| T25-02 | CLI `portfolio list` | 顯示持倉 + 未實現損益 |
| T25-03 | CLI `portfolio close 7203 <lot_id> 3000` | lot 標記 exit_price/date |
| T25-04 | GET `/api/v1/portfolio` | 回傳 open lots + 損益 |
| T25-05 | POST `/api/v1/portfolio` | 新增 lot |
| T25-06 | POST `/api/v1/portfolio/{code}/{lot_id}/close` | 平倉 |
| T25-07 | Dashboard 「持倉」區 | 顯示 portfolio open lots |
| T25-08 | Dashboard 「追蹤清單」區 | 顯示 watchlist（已與持倉分開） |
