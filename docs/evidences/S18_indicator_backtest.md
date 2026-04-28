# S18 測試證據 — 訊號回測整合（技術指標接入 simulation 引擎）

**實作日期**：2026-04-28
**實作範圍**：M5 Sprint 18 / S18
**實作人員**：Claude (Sonnet 4.6)

---

## 自動測試結果

```
TC1 PASS: indicator_exit 優先出場
TC2 PASS: indicator_exit=False 不觸發
TC3 PASS: 空條件 → True
TC4 PASS: OR logic 任一成立 → True
TC5 PASS: AND logic 部分成立 → False
TC6 PASS: AND logic 全部成立 → True
TC7 PASS: exit_reason_breakdown + strategy_type 正確

=== 全部測試通過 (7/7) ===
```

## 測試詳情

| # | 測試項目 | 測試描述 | 預期結果 | 測試結果 |
|---|---|---|---|---|
| TC1 | indicator_exit 觸發 | has_indicator_exit=True → decide_exit_reason | 回傳 "indicator_exit" | ✅ 通過 |
| TC2 | indicator_exit 不觸發 | has_indicator_exit=False，無其他條件 | 回傳 None | ✅ 通過 |
| TC3 | 空條件列表 | check_indicator_condition(conds=[]) | 回傳 True（不阻擋） | ✅ 通過 |
| TC4 | OR logic 任一成立 | [macd_golden_cross, rsi_overbought]，只有前者匹配 | 回傳 True | ✅ 通過 |
| TC5 | AND logic 部分成立 | 同上，logic="and" | 回傳 False | ✅ 通過 |
| TC6 | AND logic 全部成立 | [macd_golden_cross, rsi_oversold]，兩者皆匹配 | 回傳 True | ✅ 通過 |
| TC7 | 報告欄位 | exit_reason_breakdown + strategy_type 計算 | breakdown={'indicator_exit':1}, type='signal_indicator' | ✅ 通過 |

## API 驗證

```
API endpoints OK: ['/api/v1/compare/signals', '/api/v1/compare/dividend']
schema import OK
```

## 功能測試（人工驗收用）

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | 建立有指標條件的模擬 | simulation/new → Step 3 勾選 MACD 金叉進場 | 模擬建立成功，config 含 indicator_entry | ⬜ 未測試 | |
| 2 | 回測執行 | 點「建立並回測」 | status=completed，report 含 exit_reason_breakdown | ⬜ 未測試 | |
| 3 | strategy_type 標籤 | 查看 simulation/[id] 報告 | 顯示「訊號 + 指標策略」badge | ⬜ 未測試 | |
| 4 | exit_reason_breakdown | 同上 | 顯示各出場原因計數 | ⬜ 未測試 | |
| 5 | AND/OR radio | Step 3 選多個條件 → 出現 AND/OR | 切換邏輯 radio | ⬜ 未測試 | |

## DoD 驗收清單

- [x] IndicatorCondition schema（7 種 type）
- [x] EntryRule.indicator_entry + indicator_entry_logic
- [x] ExitRule.indicator_exit + indicator_exit_logic
- [x] ClosedTrade.exit_reason 含 "indicator_exit"
- [x] SimulationReport.exit_reason_breakdown + strategy_type
- [x] check_indicator_condition()：空條件→True、OR/AND logic 正確
- [x] decide_exit_reason() indicator_exit 優先於其他條件
- [x] run_backtest 接受並傳遞 indicator_service
- [x] simulation router 注入 get_indicator_service()
- [x] 前端 types.ts 型別同步更新
- [x] simulation/new Step 3 技術指標條件區塊 UI
- [x] simulation/[id] 策略類型標籤 + 出場原因分布
- [ ] 瀏覽器端到端手動驗收

## 整體驗收

| 欄位 | 內容 |
|---|---|
| 測試日期 | 2026-04-28 |
| 測試人員 | Claude Sonnet 4.6（自動測試 7/7 通過）|
| 整體結果 | ✅ 後端邏輯通過 / ⬜ 前端 E2E 待人工驗收 |
| 主要問題 | 無 |
| 後續行動 | 啟動 dev server 後測試完整 backtest 流程（需要 price cache 資料） |
