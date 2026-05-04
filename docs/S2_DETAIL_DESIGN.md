# S2 Detail Design — 全市場掃描 worker + 每日快照（實作紀錄）

依賴：[SPRINT_02.md](SPRINT_02.md)
完成日：2026-04-25

## 實裝產出
- ✅ `data/universe.csv`：TOPIX Core30 約 30 檔股票清單
- ✅ `api/schemas/scan.py`：SignalScanRow、DividendScanRow、SnapshotMeta、JobStatus Pydantic models
- ✅ `api/services/scan_service.py`：掃描服務
  - `run_signals_scan(universe)` — 訊號掃描（score 計算）
  - `run_dividend_scan(universe)` — 配息掃描（殖利率計算）
  - `write_snapshot(kind, rows, date_str)` — 寫 parquet 快照
  - `load_latest_snapshot(kind, date_str)` — 讀快照
  - `list_snapshots(kind)` — 列出所有快照
  - `load_universe(path)` — 讀 universe.csv
- ✅ `api/routers/scan.py`：5 個 scan endpoints
  - `GET /api/v1/scan/signals?date=...`
  - `GET /api/v1/scan/dividend?date=...&min_yield=...&overall=...&order_by=...&desc=...`
  - `GET /api/v1/scan/snapshots`
  - `POST /api/v1/scan/run`
  - `GET /api/v1/scan/jobs/{job_id}`
- ✅ `api/workers/scan_worker.py`：CLI worker
  - `python -m api.workers.scan_worker --kind signals [--limit N]`
  - `python -m api.workers.scan_worker --kind dividend [--limit N]`

## 自動化測試
- `tests/unit/test_scan_service.py` — 10 個單元測試（確定性、覆寫、失敗容忍）
- `tests/api/test_scan_router.py` — 9 個 API 測試（endpoints、篩選排序、job 管理）
- 總計 19 個測試全綠，與 S1 合併覆蓋率 85.58% ≥ 80%
