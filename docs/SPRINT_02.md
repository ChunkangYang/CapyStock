# Sprint 2 — 全市場掃描 worker + 每日快照

依賴：[MILESTONE_03.md](MILESTONE_03.md)

## 目的
- 投機面板需要「今天有訊號的股票」清單
- 金雞面板需要「全市場高股息排序」清單
- 線上即時掃描不可行（throttle 2s × 4000 檔）→ **離線 worker + parquet 快照**

## 檔案
- `data/universe.csv`：手工準備（先放 TOPIX Core30 / Prime 500；欄位 `code,name,market`）
- `api/workers/scan_worker.py`
- `api/services/scan_service.py`
- `api/routers/scan.py`
- `api/schemas/scan.py`

## Worker 行為

```
python -m api.workers.scan_worker --kind signals [--universe data/universe.csv] [--limit N]
python -m api.workers.scan_worker --kind dividend
```

### signals scan
- 對 universe 每檔執行 `signal_service.analyze_one`
- 篩選條件：`alerts` 內含 `accumulation` **或** EDINET 350 新規（過去 N 日）
- 寫入 `data/scan_snapshots/signals_{YYYY-MM-DD}.parquet`
  - 欄位：`code, name, latest_price, has_accumulation, has_exit, has_stop_loss, edinet_recent_count, score, generated_at`
  - `score` = 內部排序權重（吃貨 +3、EDINET 350 +2、EDINET 360 +1、出場 -2、停損 -3）

### dividend scan
- 對 universe 每檔執行 `dividend_service.get_fundamental_report`
- 計算「估算殖利率」：用 `dps[最新]` / `latest_price`
- 寫入 `data/scan_snapshots/dividend_{YYYY-MM-DD}.parquet`
  - 欄位：`code, name, overall, pass_count, warn_count, fail_count, latest_dps, dps_streak_no_cut, est_yield, payout_avg, equity_ratio_latest, eps_growth, generated_at`

### 失敗處理
- 任一檔失敗：寫入 `data/scan_snapshots/_errors_{kind}_{date}.csv`，繼續下一檔，不中斷
- worker 進度條：`[i/N] code`

## Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/scan/signals?date=YYYY-MM-DD` | 取訊號掃描快照（缺省= 最新） |
| GET | `/api/v1/scan/dividend?date=...&min_yield=0.03&overall=STRONG,HEALTHY&order_by=est_yield&desc=true` | 金雞快照 |
| GET | `/api/v1/scan/snapshots` | 列出可用快照日期 |
| POST | `/api/v1/scan/run` | body `{kind: "signals"|"dividend"}`；query `async=true` 才背景跑 |
| GET | `/api/v1/scan/jobs/{job_id}` | 查 job 狀態（in-memory dict） |

## 驗收（自動化）
- `pytest tests/unit/test_scan_service.py tests/api/test_scan_router.py -v` 全綠
- 確定性測試：給 `tests/fixtures/universe_small.csv`（5 檔）+ mock service → parquet 內容欄位 / row 數 / 排序 / score 精確相等
- 覆寫測試：同一日期跑兩次，parquet 不重複
- 失敗容忍測試：5 檔中第 3 檔 raise，仍寫入其他 4 檔且 `_errors_*.csv` 含失敗那檔
- 篩選/排序測試：`order_by=est_yield&desc=true&min_yield=0.03` 結果順序正確
