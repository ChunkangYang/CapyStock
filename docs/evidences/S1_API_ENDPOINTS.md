# Sprint 1 API 端點規格

## 基礎資訊

- **Base URL**：`http://localhost:8000/api/v1`
- **認證**：無（開發版本）
- **格式**：JSON
- **文件**：`http://localhost:8000/docs`（Swagger UI）

---

## 元資訊

### GET /health
健檢端點

**Response (200)**
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## 追蹤清單管理

### GET /watchlist
列出所有追蹤清單

**Response (200)**
```json
[
  {
    "code": "7203",
    "name": "トヨタ自動車",
    "start_price": 2500.0,
    "added_date": "2024-01-01"
  }
]
```

---

### POST /watchlist
加入新的追蹤股票

**Request Body**
```json
{
  "code": "7203",
  "start_price": 2500.0
}
```

**Response (200)**
```json
{
  "code": "7203",
  "name": "トヨタ自動車",
  "start_price": 2500.0,
  "added_date": "2026-04-25"
}
```

**Error (5xx)**
```json
{
  "detail": "股票代碼無效或網路錯誤"
}
```

---

### DELETE /watchlist/{code}
移除追蹤股票

**Path Parameters**
| 名稱 | 型別 | 說明 |
|------|------|------|
| code | string | 股票代碼（e.g., 7203） |

**Response (200)**
```json
{
  "status": "removed",
  "code": "7203"
}
```

**Error (404)**
```json
{
  "detail": "7203 不在追蹤清單"
}
```

---

## 訊號分析

### GET /signals
分析所有追蹤股票的訊號

**Response (200)**
```json
[
  {
    "code": "7203",
    "name": "トヨタ",
    "latest_price": 2500.0,
    "latest_date": "2024-01-02",
    "start_price": 2400.0,
    "price_vs_start_pct": 0.0417,
    "price_vs_recent_low_pct": 0.05,
    "conditions": {
      "cond_inst_sell": false,
      "cond_margin_surge": false,
      "cond_price_rise": true,
      "matched": 1
    },
    "stop_loss_triggered": false,
    "accumulation_signal": false,
    "flow_recent": [100.0, 50.0],
    "margin_trend_note": "",
    "notes": ["缺投資部門別資料"],
    "alerts": []
  }
]
```

---

### GET /signals/{code}
取得單檔股票訊號詳細

**Path Parameters**
| 名稱 | 型別 | 說明 |
|------|------|------|
| code | string | 股票代碼 |

**Response (200)**
結構同上（單筆）

**Error (500)**
```json
{
  "detail": "分析失敗：無股價資料"
}
```

---

### GET /signals/{code}/price
取得 K 線資料

**Path Parameters**
| 名稱 | 型別 | 說明 |
|------|------|------|
| code | string | 股票代碼 |

**Query Parameters**
| 名稱 | 型別 | 預設 | 說明 |
|------|------|------|------|
| days | int | 90 | 回溯天數 |

**Response (200)**
```json
[
  {
    "date": "2024-01-01",
    "open": 100.0,
    "high": 102.0,
    "low": 99.0,
    "close": 101.0,
    "volume": 1000.0
  }
]
```

---

### GET /signals/{code}/flow
取得投資部門別買賣超

**Path Parameters**
| 名稱 | 型別 | 說明 |
|------|------|------|
| code | string | 股票代碼 |

**Query Parameters**
| 名稱 | 型別 | 預設 | 說明 |
|------|------|------|------|
| days | int | 30 | 回溯天數 |

**Response (200)**
```json
[
  {
    "date": "2024-01-01",
    "foreign_net": 100.0,
    "institution_net": 200.0,
    "individual_net": -300.0
  }
]
```

---

### GET /signals/{code}/margin
取得信用殘歷史

**Path Parameters**
| 名稱 | 型別 | 說明 |
|------|------|------|
| code | string | 股票代碼 |

**Query Parameters**
| 名稱 | 型別 | 預設 | 說明 |
|------|------|------|------|
| weeks | int | 12 | 回溯週數 |

**Response (200)**
```json
[
  {
    "week": "2024-01-01",
    "margin_long": 1000.0,
    "margin_short": 500.0,
    "ratio": 0.5
  }
]
```

---

### GET /signals/{code}/edinet
取得 EDINET 5% rule 申報

**Path Parameters**
| 名稱 | 型別 | 說明 |
|------|------|------|
| code | string | 股票代碼 |

**Query Parameters**
| 名稱 | 型別 | 預設 | 說明 |
|------|------|------|------|
| days | int | 30 | 回溯天數 |

**Response (200)**
```json
[
  {
    "sec_code": "7203",
    "submit_date": "2024-01-01",
    "doc_type_code": "350",
    "filer_name": "SomeInvestor",
    "pdf_url": "https://example.com/pdf"
  }
]
```

**Note**: 需要設定 `EDINET_API_KEY` 環境變數（見 `data/.env`）

---

## 基本面分析

### GET /dividend/{code}
取得 8 指標基本面報告

**Path Parameters**
| 名稱 | 型別 | 說明 |
|------|------|------|
| code | string | 股票代碼 |

**Response (200)**
```json
{
  "code": "7203",
  "name": "トヨタ",
  "overall": "STRONG",
  "metrics": [
    {
      "metric": "sales",
      "score": "PASS",
      "note": "穩定成長（+15.0%，3 年）"
    },
    {
      "metric": "eps",
      "score": "PASS",
      "note": "穩定成長（+20.0%，3 年）"
    },
    {
      "metric": "op_margin",
      "score": "PASS",
      "note": "12.0% 平均（≥10%）"
    },
    {
      "metric": "equity_ratio",
      "score": "PASS",
      "note": "65%（≥60%）"
    },
    {
      "metric": "op_cf",
      "score": "PASS",
      "note": "全部 3 年為正"
    },
    {
      "metric": "cash",
      "score": "PASS",
      "note": "穩定成長（+10.0%，3 年）"
    },
    {
      "metric": "dps",
      "score": "PASS",
      "note": "2 次增配，無減配（3 年）"
    },
    {
      "metric": "payout",
      "score": "PASS",
      "note": "40% 平均（30–50%）"
    }
  ]
}
```

**Overall 評等**
| 評等 | 條件 |
|------|------|
| STRONG | ≥ 7 個 PASS |
| HEALTHY | ≥ 5 個 PASS |
| CAUTION | ≥ 1 個 FAIL 或資料不足 |
| RISKY | ≥ 3 個 FAIL |

**Error (404)**
```json
{
  "detail": "無法取得 9999 的基本面資料"
}
```

---

### GET /dividend/{code}/series
取得配當及其他指標時序（供圖表用）

**Path Parameters**
| 名稱 | 型別 | 說明 |
|------|------|------|
| code | string | 股票代碼 |

**Response (200)**
```json
{
  "dps_series": [50.0, 100.0, 150.0],
  "eps_series": [500.0, 600.0, 700.0],
  "payout_series": [10.0, 15.0, 20.0]
}
```

**Response (無快取資料時)**
```json
{
  "dps_series": [],
  "eps_series": [],
  "payout_series": []
}
```

---

## 錯誤處理

### 常見錯誤

| HTTP Code | 說明 | 範例 |
|-----------|------|------|
| 200 | 成功 | 所有正常回應 |
| 404 | 未找到 | DELETE watchlist/{code} 不存在 |
| 500 | 伺服器錯誤 | 分析失敗、網路異常 |

### 範例錯誤回應
```json
{
  "detail": "詳細錯誤訊息"
}
```

---

## 資料型別定義

### PriceBar
| 欄位 | 型別 | 說明 |
|------|------|------|
| date | string (ISO 8601) | 日期（yyyy-mm-dd） |
| open | float | 開盤價（日圓） |
| high | float | 最高價 |
| low | float | 最低價 |
| close | float | 收盤價 |
| volume | float | 成交量（千株） |

### SignalResult
| 欄位 | 型別 | 說明 |
|------|------|------|
| code | string | 股票代碼 |
| name | string | 股票名稱 |
| latest_price | float \| null | 最新收盤價 |
| latest_date | string \| null | 最新日期（ISO 8601） |
| start_price | float \| null | 追蹤起始價 |
| price_vs_start_pct | float \| null | 相對起始漲跌幅 |
| price_vs_recent_low_pct | float \| null | 離近期低點距離 |
| conditions | SignalConditions | 三選二條件狀態 |
| stop_loss_triggered | bool | 是否觸發停損 |
| accumulation_signal | bool | 吃貨訊號 |
| flow_recent | array[float] | 最近投資部門別 |
| margin_trend_note | string | 信用殘趨勢說明 |
| notes | array[string] | 附註 |
| alerts | array[Alert] | 警示清單 |

### FundamentalReport
| 欄位 | 型別 | 說明 |
|------|------|------|
| code | string | 股票代碼 |
| name | string | 股票名稱 |
| overall | enum | STRONG / HEALTHY / CAUTION / RISKY |
| metrics | array[FundamentalMetric] | 8 個指標評分 |

---

## 使用範例

### cURL

```bash
# 列出追蹤清單
curl http://localhost:8000/api/v1/watchlist

# 加入追蹤
curl -X POST http://localhost:8000/api/v1/watchlist \
  -H "Content-Type: application/json" \
  -d '{"code": "7203", "start_price": 2500.0}'

# 取得訊號
curl http://localhost:8000/api/v1/signals/7203

# 取得基本面
curl http://localhost:8000/api/v1/dividend/7203
```

### JavaScript/Fetch

```javascript
const API_BASE = 'http://localhost:8000/api/v1';

// 列出追蹤清單
const watchlist = await fetch(`${API_BASE}/watchlist`).then(r => r.json());

// 加入追蹤
const result = await fetch(`${API_BASE}/watchlist`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ code: '7203', start_price: 2500.0 })
}).then(r => r.json());

// 取得訊號
const signal = await fetch(`${API_BASE}/signals/7203`).then(r => r.json());
```

### Python

```python
import requests

api_base = 'http://localhost:8000/api/v1'

# 列出追蹤清單
watchlist = requests.get(f'{api_base}/watchlist').json()

# 加入追蹤
result = requests.post(
    f'{api_base}/watchlist',
    json={'code': '7203', 'start_price': 2500.0}
).json()

# 取得訊號
signal = requests.get(f'{api_base}/signals/7203').json()
```

---

## CORS 設定（開發版本）

允許的來源：
- `http://localhost:5173`（SvelteKit 前端開發伺服器）
- `http://127.0.0.1:5173`

Prod 部署時應更新。

---

## 版本歷史

| 版本 | 日期 | 異動 |
|------|------|------|
| 0.1.0 | 2026-04-25 | S1 初版發布（15 個 endpoint） |

