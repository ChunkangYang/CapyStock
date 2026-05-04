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
| SIG-1 | Tab 切換（全市場訊號 / 我的持倉 / 我的最愛）：按鍵盤 Tab 只會移動 focus，不會真正切換 tab | ✅ 已修復 → ARIA tablist + 方向鍵切換（←/→）；Tab 鍵保留 focus 移動是正確 a11y 行為 |
| SIG-2 | 「我的持倉」讀取需要約 5 秒，速度過慢 | ✅ 已優化 → 改用 `/signals` 批次端點取代 N+1 個別呼叫 |
| SIG-3 | Race condition：在「我的持倉」讀取完成前切換到其他 tab，畫面反而顯示「我的持倉」內容 | ✅ 已修復 → loadSeq guard，stale response 自動捨棄 |
| SIG-4 | Filter（只看吃貨 / 只看出場 / 只看停損 / 最低 score）：出場、停損 filter 後沒有顯示股票（測試快照缺少對應種類訊號） | ⚠️ Filter 邏輯正確，問題在測試快照資料無該類訊號；非 code bug |

---

## UAT Watchlist / 首頁

| # | 回報內容 | 狀態 |
|---|---|---|
| WL-1 | 首頁「追蹤清單」區塊未顯示實際持股明細，只顯示追蹤數 | ✅ 已實作 → 顯示代號/名稱/入場價列表（最多 5 筆 + 超出提示）；Playwright 截圖 uat_fix_homepage_wl1.png |
| WL-2 | UAT 描述「watchlist」與前端「我的最愛」概念混淆，用戶詢問兩者的關係 | ❓ 需釐清定義 |
| WL-3 | UAT 說「點 + 新增按鈕」，但前端 watchlist 頁面沒有按鈕，直接就是表單 UI | ❓ 待確認 UAT 是否要更新 |

---

## UAT 排程（TC-0.2）

| # | 回報內容 | 狀態 |
|---|---|---|
| SCH-1 | 終端機未顯示 `[scheduler] started` → NG | ✅ 已修復 → api/main.py lifespan 加入 `print("[scheduler] started")` |

---

## EDINET（TC-B3 / CLI-03）

| # | 回報內容 | 狀態 |
|---|---|---|
| EDI-1 | `/signals/7203/edinet?days=30` API 回應有問題，EDINET 資料未正確顯示 | ✅ 已修復 → 欄位名稱對齊前端 EdinetEvent 型別（submit_date→date, filer_name→filer, doc_type_code→doc_type）；個股頁右側正確顯示 2 筆申報 |

---

## S24 實作（Haiku session）

| # | 回報內容 | 狀態 |
|---|---|---|
| S24-1 | 用 Haiku 執行 `/impl S24` 後出現 bug，且 Haiku 的修改覆蓋了前一個 session 的未 commit 變更（含 watchlist 明細實作） | ✅ 已補實作 → WL-1 重新實作完成（2026-05-04） |

---

## 備註

- `WL-1`（首頁 watchlist 明細）是本次遺失的主要實作，需優先補上。
- Haiku 執行 `/impl S24` 時未遵守 commit 規則，導致前一 session 的工作被覆蓋。
- 所有 `❓` 狀態的 issue 需在下次 UAT session 中重新驗證。
