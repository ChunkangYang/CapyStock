# S1 Detail Design — Backend API 骨架 + service 化（實作紀錄）

依賴：[SPRINT_01.md](SPRINT_01.md)
完成日：2026-04-25

## 實裝產出
- ✅ `api/main.py`：FastAPI app 入口，自動化路由註冊
- ✅ `api/services/signal_service.py`：純函式無副作用，供 API 複用
  - `analyze_one(code, start_price)` — 單檔訊號分析
  - `analyze_watchlist()` — 整清單分析
  - `get_price_history(code, days)` — K 線資料
  - `get_flow_history(code, days)` — 投資部門別
  - `get_margin_history(code, weeks)` — 信用殘
  - `get_edinet_events(code, days)` — EDINET 申報
- ✅ `api/services/dividend_service.py`：基本面分析服務
  - `get_fundamental_report(code)` — 8 指標報告
  - `get_dividend_history(code)` — 配當時序

## API endpoints（15 個）
- `/api/v1/health` — 健檢
- `/api/v1/watchlist` — GET/POST/DELETE
- `/api/v1/signals` — 列表 + 單檔分析
- `/api/v1/signals/{code}/{price,flow,margin,edinet}` — 各類歷史資料
- `/api/v1/dividend/{code}` — 基本面報告 + 時序

## 自動化測試
- `tests/unit/test_signal_service.py` — 8 個單元測試
- `tests/unit/test_dividend_service.py` — 4 個單元測試
- `tests/api/test_watchlist_router.py` — 5 個 API 測試
- `tests/api/test_signals_router.py` — 7 個 API 測試
- `tests/api/test_dividend_router.py` — 3 個 API 測試
- 總計 27 個測試全綠，覆蓋率 82.73% ≥ 80%
