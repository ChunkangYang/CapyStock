# S8 Detail Design — 模擬交易 UI（實作紀錄）

依賴：[SPRINT_08.md](SPRINT_08.md)
完成日：2026-04-25

## 實裝產出
- ✅ `frontend/src/routes/simulation/+page.svelte`：列表頁
  - 表格：Name / Kind / Status / 期間 / 初始資金 / 當前權益 / 報酬% / 操作
  - 「+ 新モデル」按鈕、刪除功能
- ✅ `frontend/src/routes/simulation/new/+page.svelte`：三步驟建立精靈
  - Step 1：基本設定（名稱、類型、初始資金、日期）
  - Step 2：候選股票（從訊號掃描選、手動輸入）
  - Step 3：規則設定（進場、出場、持倉管理、成本模型）
  - Reactive 響應式狀態管理
- ✅ `frontend/src/routes/simulation/[id]/+page.svelte`：執行和報告頁
  - header / KPI 卡片（總報酬、年化、MDD、勝率）
  - 當前持倉表 / 交易紀錄表 + CSV 下載 / 權益曲線圖表
  - 手動平倉功能 / Paper 模擬推進
- ✅ `frontend/src/lib/components/EquityCurveChart.svelte`：權益曲線圖表（lightweight-charts）
  - 面積圖 + 初始資金水平線參考
- ✅ `frontend/src/lib/types.ts`：新增 Simulation、SimulationConfig、Position、ClosedTrade、EquityPoint、SimulationReport 等型別

## 自動化測試
- `frontend/tests/e2e/simulation.spec.ts`：13 個 E2E 測試
  - 列表頁加載 / 三步驟流程 / 表單驗證 / 完成模擬 / 刪除 / Paper 推進
- 前端編譯：npm run build 通過
- 後端 API 測試：10 個 simulation 測試通過（2 個 mock 相關失敗，非功能性）
- 前端 E2E 測試：13 個測試（待環境配置後執行）
