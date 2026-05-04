# S25 持倉管理（Portfolio）— 實裝測試證據

**日期**：2026-05-04  
**分支**：feature/s25-portfolio

---

## T25-01 CLI portfolio add

```
python -m capystock.main portfolio add 9432 150 100 --note "UAT test"
```

**輸出**：
```
✓ 持倉新增：9432（ＮＴＴ） 100股 @ 150  lot_id=1a2b7125-6e29-472e-8818-e60f848ad78f
```

**data/portfolio.json**：
```json
{
  "9432": {
    "code": "9432",
    "name": "ＮＴＴ",
    "lots": [
      {
        "id": "1a2b7125-6e29-472e-8818-e60f848ad78f",
        "entry_price": 150.0,
        "quantity": 100,
        "entry_date": "2026-05-04",
        "exit_price": null,
        "exit_date": null,
        "note": "UAT test"
      }
    ]
  }
}
```

**結論**：✅ Pass — 資料正確寫入 portfolio.json

---

## T25-02 CLI portfolio list

```
python -m capystock.main portfolio list
```

**輸出**：
```
| Code | Name | 買入價 | 數量 | 現價 | 未實現損益 | 報酬率  | 買入日      | lot_id(前8) |
|------|------|-------|------|------|---------|-------|------------|------------|
| 9432 | ＮＴＴ |   150 |  100 |  152 |    +200 | +1.3% | 2026-05-04 | 1a2b7125   |
```

**結論**：✅ Pass — 顯示持倉 + 即時現價 + 未實現損益 + 報酬率

---

## T25-03 CLI portfolio close

```
python -m capystock.main portfolio close 9432 1a2b7125-6e29-472e-8818-e60f848ad78f 160
```

**輸出**：
```
✓ 平倉完成：9432 @ 160  損益 +1,000（+6.7%）
```

**結論**：✅ Pass — 平倉正確計算損益，portfolio.json 更新 exit_price/exit_date

---

## T25-04/05 API GET / POST /portfolio

**POST /api/v1/portfolio**：
```json
body: {"code":"9432","entry_price":148,"quantity":200,"note":"api test"}

HTTP 200
{
  "id": "d558e401-...",
  "code": "9432",
  "name": "ＮＴＴ",
  "entry_price": 148.0,
  "quantity": 200,
  "current_price": 152.0,
  "unrealized_pnl": 800.0,
  "return_pct": 2.70
}
```

**GET /api/v1/portfolio**：
```
HTTP 200 — 回傳 PortfolioEntry array，含 lots + total_cost + total_unrealized_pnl
```

**結論**：✅ Pass

---

## T25-06 API close lot

```
POST /api/v1/portfolio/9432/d558e401-.../close
body: {"exit_price": 155}

HTTP 200
{
  "exit_price": 155.0,
  "exit_date": "2026-05-04",
  "unrealized_pnl": null   ← 平倉後無未實現損益
}
```

**結論**：✅ Pass

---

## T25-07/08 Dashboard 分區（需人工驗證）

Frontend 已更新：
- **持倉狀態**：讀取 `/api/v1/portfolio`（已買入）
- **追蹤清單**：讀取 `/api/v1/watchlist`（關注中）
- **今日訊號** / **金雞 Top**：維持原有 snapshot

側欄新增「持倉管理」連結 → `/portfolio`

> 需啟動 frontend dev server 人工確認畫面分區正確 → 記錄於 HUMAN_TODO

---

## 總結

| ID | 項目 | 結論 |
|---|---|---|
| T25-01 | CLI portfolio add | ✅ Pass |
| T25-02 | CLI portfolio list（含即時損益） | ✅ Pass |
| T25-03 | CLI portfolio close | ✅ Pass |
| T25-04 | API GET /portfolio | ✅ Pass |
| T25-05 | API POST /portfolio | ✅ Pass |
| T25-06 | API close lot | ✅ Pass |
| T25-07 | Dashboard 持倉區塊 | ⏳ HUMAN_TODO |
| T25-08 | Dashboard 追蹤清單區塊分離 | ⏳ HUMAN_TODO |
