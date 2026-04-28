# S11 — APScheduler 排程器 + daily_pipeline 實作紀錄

實作日：2026-04-27

## 交付物

### 程式碼
- `api/schemas/scheduler.py` — JobDef / JobRun / 請求回應 schema
- `api/services/scheduler_service.py` — `SchedulerService`、預設 jobs、CSV / JSON 持久化、threaded timeout
- `api/routers/scheduler.py` — REST endpoints
- `api/workers/daily_pipeline.py` — scan → analyze → realtime → digest 順序管線
- `api/workers/healthcheck.py` — ping handler

### 部署模板
- `docs/DEPLOY/scheduler_winTask.xml.template`
- `docs/DEPLOY/scheduler_cron.example`

### 整合
- `api/main.py` 加入 `lifespan`：startup 啟動 SchedulerService、shutdown 停止
- `CAPYSTOCK_SCHEDULER_DISABLED=1` 旗標可關閉
- `requirements.txt` 加入 `apscheduler>=3.10`

### 預設 jobs（cron Asia/Tokyo）
| id | cron | handler |
|---|---|---|
| scan_signals | `0 6 * * 1-5` | `_handler_scan_signals` |
| scan_dividend | `30 6 * * 1` | `_handler_scan_dividend` |
| paper_advance | `0 7 * * 1-5` | `_handler_paper_advance` |
| daily_pipeline | `0 8 * * 1-5` | `api.workers.daily_pipeline:run` |
| healthcheck_ping | `*/30 * * * *` | `api.workers.healthcheck:ping` |

### 測試
- `tests/unit/test_scheduler_service.py`（10 案例：trigger 成功 / 失敗 / timeout / unknown / persist / 啟停）
- `tests/unit/test_daily_pipeline.py`（3 案例：呼叫順序、dry_run、scan skip）
- `tests/api/test_scheduler_router.py`（6 案例：list / patch / trigger / runs filter / not found）

19 個新測試全數通過。

## 設計決策
- timeout 用 `threading.Thread` + `join(timeout)` 實作（APScheduler 本身不提供 hard kill）；timeout 後 thread 仍在背景跑完才釋放。
- jobs 改動寫入 `data/scheduler_jobs.json`，重啟可恢復；執行歷史寫入 `data/scheduler_runs.csv`。
- `SchedulerService` 提供 singleton (`get_scheduler_service`)，FastAPI lifespan 依賴此 singleton。
- 測試環境用 `CAPYSTOCK_SCHEDULER_DISABLED=1` 跳過 lifespan startup，並用 `reset_singleton()` 隔離。
