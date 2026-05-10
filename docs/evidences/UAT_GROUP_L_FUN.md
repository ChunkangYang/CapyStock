# UAT 群組 L — 基本面（TC-FUN-01 ~ TC-FUN-02）

**日期**：2026-05-10  
**測試者**：Claude（CLI 自動測試）  
**執行方式**：`$env:PYTHONIOENCODING="utf-8"; python -m capystock.main fundamental <code>`

---

## TC-FUN-01 IR Bank 橫向表格解析

**步驟**：`python -m capystock.main fundamental 3543`（コメダHD）

**實際輸出**：
```
=== Fundamental Analysis: 3543（コメダホールディングス）===
| Metric        | Score   | Value / Trend         |
|---------------|---------|-----------------------|
| Sales         | N/A     | 資料不足                  |
| EPS           | PASS    | 穩定成長（+106%，13 年）      |
| Op. Margin    | PASS    | 23.2% 平均（≥10%）        |
| Equity Ratio  | WARN    | 45%（40–60%）           |
| Operating CF  | PASS    | 全部 12 年為正             |
| Cash & Equiv. | WARN    | 不穩定（+88%，上升 7/11 年）   |
| DPS           | WARN    | 1 次減配（11 年中）          |
| Payout Ratio  | FAIL    | 284% 平均（>70% 或 >100%） |

Overall: CAUTION (3 PASS / 3 WARN / 1 FAIL / 1 N/A)
```

**驗證項目**：
- ✅ 顯示完整 8 指標列
- ✅ 評等為 CAUTION（STRONG / HEALTHY / CAUTION / RISKY 之一）
- ✅ 部分缺值（Sales N/A）仍正常輸出，不整體失敗

**結果**：✅ Pass

---

## TC-FUN-02 Partial Data

**步驟**：`python -m capystock.main fundamental 4883`（モダリス）—— 生技新藥，歷史短、無配息

**實際輸出**：
```
=== Fundamental Analysis: 4883（モダリス）===
| Metric        | Score   | Value / Trend      |
|---------------|---------|--------------------|
| Sales         | N/A     | 資料不足               |
| EPS           | FAIL    | 衰退趨勢（-659%）        |
| Op. Margin    | FAIL    | -23638.2% 平均（<5%） |
| Equity Ratio  | PASS    | 93%（≥60%）          |
| Operating CF  | FAIL    | 7 年為負（頻繁）          |
| Cash & Equiv. | WARN    | 不穩定（+98%，上升 3/8 年）|
| DPS           | N/A     | 資料不足               |
| Payout Ratio  | N/A     | 資料不足               |

Overall: RISKY (1 PASS / 1 WARN / 3 FAIL / 3 N/A)
```

**可解析指標數**：5 項（EPS / Op.Margin / Equity Ratio / Operating CF / Cash & Equiv.）  
**缺值指標數**：3 項（Sales / DPS / Payout Ratio）

**驗證項目**：
- ✅ 缺值指標標 N/A，不輸出錯誤
- ✅ 仍輸出加權評等（RISKY），非整體 crash
- ✅ PASS/WARN/FAIL/N/A 計數正確

**結果**：✅ Pass

---

## 附注

Windows cp950 console 執行需加 `PYTHONIOENCODING=utf-8`，否則日文股名觸發 UnicodeEncodeError。  
此為已知限制 IMP-WIN-001（非阻斷），與 TC-CLI-02 相同。
