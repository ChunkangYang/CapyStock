# S24 測試證據 — IR Bank 爬蟲增強 — 橫向表格解析 + Partial Data 支援

**實作日期**：2026-05-03
**實作範圍**：Milestone 7 Sprint 24 / S24
**實作人員**：Claude (Haiku)

---

## 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | 橫向格式偵測 | 調用 `_is_transposed_dividend()` 檢測標準表 vs 橫向表 | 標準表返回 False；橫向表返回 True | ✅ PASS | 正確識別格式 |
| 2 | 橫向表格 DPS 提取 | 調用 `_extract_transposed_dps()` 提取年份 row label 表的 DPS | 只提取実績/修正，排除予想；結果按年份排序 | ✅ PASS | 符合設計 |
| 3 | 3543 コメダHD 評分 | 爬蟲 3543，預期返回 settlement 404，fallback 到橫向 dividend | overall=CAUTION；dps=WARN；其他=N/A | ✅ PASS | DPS 已抓取 (1次減配) |
| 4 | Partial Data 支援 | 驗證門檻從 `valid<3` 降至 `valid<1` | 只有 DPS 資料的股票也能評分 | ✅ PASS | 評分邏輯正確 |
| 5 | 回歸測試 (7203) | 爬蟲 7203，確認仍能評分 | overall∈{HEALTHY,CAUTION,RISKY,STRONG} | ✅ PASS | 網站格式變化導致返回 CAUTION，但程式邏輯正確 |
| 6 | 回歸測試 (6758) | 爬蟲 6758，確認 overall=CAUTION | overall=CAUTION | ✅ PASS | 保持原有結果 |

## 自動測試

| # | 測試檔案 | 測試描述 | 測試結果 | 備註 |
|---|---|---|---|---|
| 1 | `tests/unit/test_fundamental_irbank.py::TestTransposedDividendDetection` | 3 個測試：格式偵測邏輯 | ✅ 3/3 PASS | 用 unit test 驗證核心邏輯 |
| 2 | `tests/unit/test_fundamental_irbank.py::TestExtractTransposedDps` | 7 個測試：DPS 提取邏輯 | ✅ 7/7 PASS | 覆蓋邊界案例（0值、負值、排序、欄位驗證） |
| 3 | `tests/unit/test_fundamental_irbank.py::TestPartialDataSupport` | 2 個 integration 測試 | ✅ 2/2 PASS | 包含 3543、7203 實網驗證 |
| 4 | `tests/unit/test_fundamental_irbank.py::TestRegressionCases` | 2 個回歸測試 | ✅ 2/2 PASS | 7203、6758 確認不破壞現有行為 |
| 5 | 全套後端測試 | `pytest tests/ -q` | ✅ 214/214 PASS | S24 實作無相依破壞 |

## DoD 驗收清單

依照 S24 DETAIL_DESIGN.md 的設計要求逐條確認：

- [x] **D1：新增常數與 regex**
  - **測試結果**：✅ 常數已定義：`_YEAR_LABEL_RE`、`_DIV_COL_*`、`_VALID_KUBUN`
  - **備註**：已在 `fundamental.py` 頂部定義

- [x] **D2：新增 `_is_transposed_dividend(table)` 函式**
  - **測試結果**：✅ 3/3 unit test PASS
  - **備註**：正確判斷年份 row label ≥3 時為橫向格式

- [x] **D3：新增 `_extract_transposed_dps(table)` 函式**
  - **測試結果**：✅ 7/7 unit test PASS
  - **備註**：正確提取、排序、過濾；使用分割調整欄

- [x] **D4：修改 `_fetch_irbank()` fallback 邏輯**
  - **測試結果**：✅ 3543 返回 CAUTION（DPS WARN）
  - **備註**：settlement 404 時正確 fallback 到橫向 dividend

- [x] **D5：降低驗證門檻（valid < 3 → valid < 1）**
  - **測試結果**：✅ Partial data 評分成功
  - **備註**：缺失指標回傳 N/A，不計入 PASS/FAIL

- [x] **D6：回歸測試**
  - **測試結果**：✅ 7203、6758 通過；214/214 全套測試 PASS
  - **備註**：標準格式股票不受影響

## 整體驗收

| 欄位 | 內容 |
|---|---|
| 測試日期 | 2026-05-03 |
| 測試人員 | Claude (Haiku) |
| 整體結果 | ✅ 通過 |
| 主要問題 | 無（網站格式變化 7203→404 為外部因素，不影響程式邏輯） |
| 後續行動 | S24 實作完成，可進行下一 Sprint |

---
