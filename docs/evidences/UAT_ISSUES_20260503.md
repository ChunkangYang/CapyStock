# UAT Issues — 2026-05-03 Chat History

從昨天（2026-05-03）各 chat session 的對話紀錄中整理出的問題與回報。

---

## 環境 / 啟動

| # | 回報內容 | 狀態 |
|---|---|---|
| ENV-1 | `uvicorn` 在 PowerShell 無法直接執行（「無法辨識 'uvicorn' 詞彙」） | ✅ 已修復 → `python -m uvicorn` |

---

## UAT Signals 頁面（群組 B / D）

| # | 回報內容 | 狀態 |
|---|---|---|
| SIG-1 | Tab 切換（全市場訊號 / 我的持倉 / 我的最愛）：按鍵盤 Tab 只會移動 focus，不會真正切換 tab | ❓ 待確認是否已修 |
| SIG-2 | 「我的持倉」讀取需要約 5 秒，速度過慢 | ❓ 待確認是否已優化 |
| SIG-3 | Race condition：在「我的持倉」讀取完成前切換到其他 tab，畫面反而顯示「我的持倉」內容 | ❓ 待確認是否已修 |
| SIG-4 | Filter（只看吃貨 / 只看出場 / 只看停損 / 最低 score）：出場、停損 filter 後沒有顯示股票（測試快照缺少對應種類訊號） | ❓ 需確認測試資料 |

---

## UAT Watchlist / 首頁

| # | 回報內容 | 狀態 |
|---|---|---|
| WL-1 | 首頁「追蹤清單」區塊未顯示實際持股明細，只顯示追蹤數 | ❌ 尚未實作 |
| WL-2 | UAT 描述「watchlist」與前端「我的最愛」概念混淆，用戶詢問兩者的關係 | ❓ 需釐清定義 |
| WL-3 | UAT 說「點 + 新增按鈕」，但前端 watchlist 頁面沒有按鈕，直接就是表單 UI | ❓ 待確認 UAT 是否要更新 |

---

## UAT 排程（TC-0.2）

| # | 回報內容 | 狀態 |
|---|---|---|
| SCH-1 | 終端機未顯示 `[scheduler] started` → NG | ❓ 待調查 |

---

## EDINET（TC-B3 / CLI-03）

| # | 回報內容 | 狀態 |
|---|---|---|
| EDI-1 | `/signals/7203/edinet?days=30` API 回應有問題，EDINET 資料未正確顯示 | ❓ 待調查 |

---

## S24 實作（Haiku session）

| # | 回報內容 | 狀態 |
|---|---|---|
| S24-1 | 用 Haiku 執行 `/impl S24` 後出現 bug，且 Haiku 的修改覆蓋了前一個 session 的未 commit 變更（含 watchlist 明細實作） | ❌ 工作遺失，需重新實作 |

---

## 備註

- `WL-1`（首頁 watchlist 明細）是本次遺失的主要實作，需優先補上。
- Haiku 執行 `/impl S24` 時未遵守 commit 規則，導致前一 session 的工作被覆蓋。
- 所有 `❓` 狀態的 issue 需在下次 UAT session 中重新驗證。
