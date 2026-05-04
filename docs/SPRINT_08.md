# Sprint 8 — 模擬交易 UI

依賴：[MILESTONE_03.md](MILESTONE_03.md)

## 路由
- `/simulation`：列表
- `/simulation/new`：建立精靈
- `/simulation/[id]`：執行 + 報告

## `/simulation` 列表
- 表格：Name / Kind / Status / 期間 / 初始資金 / 當前權益 / 報酬% / 操作（檢視 / 刪除）
- 右上「+ 新模擬」

## `/simulation/new` 三步驟精靈

**Step 1 — 基本設定**
- 名稱、類型（backtest / paper radio）
- 初始資金（JPY）
- backtest：選 start_date / end_date
- paper：start_date 預設 today，end_date 不選

**Step 2 — 候選股票**
- 三種來源：從訊號掃描挑（`scan/signals`，預設 has_accumulation=true）/ 從我的最愛挑（tag=speculative）/ 手動輸入 code list
- 每檔可額外設 `forced_entry_date`

**Step 3 — 規則設定**
- EntryRule：radio `signal_close / next_open / user_specified`（後者出現價格輸入框，per-code）+ `require_signal` checkbox
- ExitRule：所有欄位 form
- PositionSizing：mode 三選一
- CostModel：手續費 / 滑價 / 稅率（預設值帶好）
- 結尾「建立並執行」按鈕

## `/simulation/[id]` 主頁

### 上方
- 名稱 / 類型 / 期間 / status badge
- backtest completed：總報酬、年化、MDD、勝率 KPI 卡片
- paper running：今日權益、持倉數、現金
- 操作按鈕：`Advance Today`（paper）/ `Re-run`（backtest）/ `Delete`

### 主視覺
1. **權益曲線 chart**（EquityCurveChart.svelte，lightweight-charts area）
   - 疊加 initial_capital 水平線
2. **持倉表**：positions（目前未平倉）
3. **交易紀錄表**：closed_trades；可下載 CSV
4. **每筆交易條圖**：bar，藍正紅負，hover 顯示 code

### 互動
- 持倉表每行有「手動平倉」按鈕 → modal 輸入價格 / 日期 → close-position
- 候選表每行可移除（draft 階段才能改）

## 驗收（自動化）

`npm run test:e2e` 通過 `e2e/simulation.spec.ts`：

1. **建立 backtest 流程**：
   - 三步驟全部填完並送出
   - 等候完成（poll status 至 completed）
   - 跳轉 `/simulation/[id]`
   - 斷言：總報酬 KPI 文字 = API `/report` 回傳值（用 `toBeCloseTo`）
   - 點「下載 CSV」→ 行數 = `closed_trades.length` + 1
2. **paper 流程**：建立 paper → 點 Advance Today → equity_curve series 多一點
3. **手動平倉**：在持倉表點按鈕 → modal 輸入 → 提交 → row 從持倉表消失、closed_trades 多一列、reason = `manual`
4. **錯誤處理**：建立模擬時故意送錯 config（缺 user_price）→ 錯誤 toast、不跳頁
5. **截圖回歸**：列表 / 新建三步 / 報告主頁共 5 張
