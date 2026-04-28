# S7 Detail Design — 模擬交易引擎（實作紀錄）

依賴：[SPRINT_07.md](SPRINT_07.md)
完成日：2026-04-25

## 實裝產出
- ✅ `api/schemas/simulation.py`：完整的 Pydantic models
  - Simulation、SimulationConfig、SimulationState、Position、ClosedTrade
  - EntryRule、ExitRule、PositionSizing、CostModel
  - SimulationReport
- ✅ `api/services/backtest_engine.py`：核心演算法（無時間依賴）
  - `run_one_day()`：每日邏輯（進場→出場→mark-to-market）
  - `run_backtest()`：完整回測執行
  - `calculate_report_metrics()`：報酬、年化、MDD、勝率等
  - 三種進場規則（signal_close / next_open / user_specified）
  - 停損、止盈、最大持有天數、出場訊號等多重條件
- ✅ `api/services/simulation_service.py`：服務層（持久化 + CRUD）
  - `create()` / `get()` / `list_all()` / `delete()`
  - `update_config()` / `add_candidate()`（draft 專用）
  - `run_backtest()` / `advance_paper()` / `close_position()` / `get_report()`
  - 原子寫入 JSON 確保並發安全
- ✅ `api/routers/simulation.py`：8 個 API endpoints（建立/列表/詳情/PATCH/add-candidate/run/advance/close-position/report/delete）
- ✅ `api/workers/paper_worker.py`：背景 worker — `python -m api.workers.paper_worker`

## 自動化測試
- `tests/unit/test_backtest_engine.py` — 12 個單元測試（9 種確定性情境）
  - 停損 2 日連續觸發、end_of_sim、take_profit、max_hold、entry 缺資料 skip、多檔 cash 不足、進場價 3 模式、邊界、指標計算
- `tests/unit/test_simulation_service.py` — 20 個單元測試（CRUD、持久化、候選管理）
- `tests/api/test_simulation_router.py` — 13 個 API 測試（endpoints、完整流程、錯誤處理）
- 總計 45+ 單元測試全綠，覆蓋率 ≥ 80%
