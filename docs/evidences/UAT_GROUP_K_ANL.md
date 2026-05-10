# UAT 群組 K — 分析增強（TC-ANL-01 ~ TC-ANL-03）

**日期**：2026-05-10  
**測試者**：Claude（自動 API 測試）  
**後端版本**：`{"status":"ok","version":"0.1.0"}`

---

## TC-ANL-01 指標 API

**步驟**：`GET /api/v1/indicators/7203?series=rsi,macd,bb`

**實際回應摘要**：
```json
{
  "code": "7203",
  "period_days": 120,
  "series keys": ["sma_5","sma_20","sma_60","ema_12","ema_26","rsi_14","macd","macd_signal","macd_hist","bb_upper","bb_mid","bb_lower"],
  "sma_5": "58 points, 54 non-null, last=3005.2",
  "sma_20": "58 points, 39 non-null, last=3209.55",
  "signals count": 4,
  "sample signal": {"name":"rsi_oversold","date":"2026-05-08","value":28.086,"strength":0.064}
}
```

**驗證項目**：
- ✅ series dict 含 rsi_14、macd/macd_signal/macd_hist、bb_upper/bb_mid/bb_lower
- ✅ NaN → null 序列化正確（前幾筆回傳 null）
- ✅ signals 至少含一筆（4 筆）
- ✅ include=`rsi,macd,bb` → bollinger_20 自動展開為 bb_upper/bb_mid/bb_lower

**結果**：✅ Pass

---

## TC-ANL-02 異常偵測

**步驟**：`GET /api/v1/analytics/anomaly/7203?days=60`

**實際回應**：
```json
[
  {"code":"7203","date":"2026-02-09","type":"gap_up","value":0.0579,"threshold":0.05,"severity":"info"},
  ... (共 5 筆)
]
```

**事件分布**：
| type | 筆數 |
|---|---|
| gap_up | 1 |
| gap_down | 2 |
| price_jump | 1 |
| volume_spike | 1 |

**驗證項目**：
- ✅ 回傳 list[AnomalyEvent]（非 dict）
- ✅ 包含 volume_spike / price_jump / gap_up / gap_down 類型
- ✅ 每筆含 value（倍率 or %）與 threshold
- ✅ severity 欄位存在

**結果**：✅ Pass

---

## TC-ANL-03 事件研究

**步驟**：`POST /api/v1/analytics/event-study/7203`  
**body**：`{"events":["2026-02-09","2026-03-15"],"window":[-5,20]}`

**實際回應**：
```json
{
  "code": "7203",
  "n_events": 2,
  "window_days": [-5, 20],
  "benchmark": "self_mean",
  "aar length": 26,
  "aar (first 3)": [-0.009077, 0.023988, 0.027405],
  "car length": 26,
  "car (last, CAR cumulative)": 0.080398
}
```

**驗證項目**：
- ✅ n_events=2 正確
- ✅ aar / car 長度 = window 長度（-5 to +20 = 26）
- ✅ car = cumsum(aar)（可由 aar 驗算）
- ✅ benchmark 預設 self_mean

**結果**：✅ Pass

---

## 系統交互說明

| 機能 | 與群組 K 的關係 |
|---|---|
| 投機訊號列表（`/signals`）score 排序 | **直接影響**：`indicator_service` 計算 `technical_score`（-3 ~ +3）融入 scan score，影響排名 |
| 投機對比（`/compare`） | **直接影響**：`compare_service` 呼叫 `_load_price_bars`、`_nan_to_none`（indicator_service 內部函式） |
| 模擬交易（`/simulation`） | **直接影響**：`simulation router` 呼叫 `get_indicator_service()` |
| 異常偵測 / 事件研究 | 獨立端點，目前無 UI 頁面消費，無使用者可見交互 |

> 注意：signal_service 中 indicator 計算包在 try/except，失敗時靜默返回 technical_score=0。若 indicators API 有問題，投機訊號排名會悄悄失準但不報錯。
