# Sprint 11 — 排程器（APScheduler + 雙 worker 整合）

依賴：[MILESTONE_04.md](MILESTONE_04.md)

## 目的
把以下排程化、並有 UI / API 可看：
- 每日 06:00 — `scan_worker --kind signals`
- 每日 06:30 — `scan_worker --kind dividend`
- 每日 07:00 — `paper_worker`
- 每日 08:00 — digest 推送
- realtime — alert 觸發即送

## 檔案
- `api/services/scheduler_service.py`
- `api/routers/scheduler.py`
- `api/schemas/scheduler.py`
- `api/workers/daily_pipeline.py`
- `data/scheduler_runs.csv`
- `docs/DEPLOY/scheduler_winTask.xml.template`
- `docs/DEPLOY/scheduler_cron.example`

## SchedulerService

```python
class JobDef(BaseModel):
    id: str                      # "scan_signals", "scan_dividend", "paper_advance", "digest_send"
    name: str
    cron: str                    # "0 6 * * *"
    handler: str                 # dotted path "api.workers.scan_worker:run_signals"
    enabled: bool = True
    timeout_seconds: int = 1800
    max_instances: int = 1

class JobRun(BaseModel):
    run_id: str                  # uuid
    job_id: str
    started_at: datetime
    finished_at: datetime | None
    status: Literal["running", "success", "failed", "timeout", "skipped"]
    duration_seconds: float | None
    error: str | None
    output_summary: str | None

class SchedulerService:
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def list_jobs(self) -> list[JobDef]: ...
    def list_runs(self, job_id=None, days=7) -> list[JobRun]: ...
    def trigger_now(self, job_id: str) -> JobRun: ...
    def update_job(self, job_id: str, **fields) -> JobDef: ...
```

## 預設 jobs

| id | cron | handler |
|---|---|---|
| scan_signals | `0 6 * * 1-5` | `api.workers.scan_worker:run_signals` |
| scan_dividend | `30 6 * * 1` | `api.workers.scan_worker:run_dividend`（每週一） |
| paper_advance | `0 7 * * 1-5` | `api.workers.paper_worker:run_all` |
| daily_pipeline | `0 8 * * 1-5` | `api.workers.daily_pipeline:run` |
| healthcheck_ping | `*/30 * * * *` | `api.workers.healthcheck:ping` |

## daily_pipeline.py

```python
def run(today: date | None=None, dry_run: bool=False) -> dict:
    """
    1. 確保今日 signals scan 已存在（沒有就現跑）
    2. analyze_watchlist → 收集 alerts
    3. process_realtime_alert(每個 critical alert)
    4. process_daily_digest(today)
    5. 回傳 summary {scan_rows, alerts_total, realtime_sent, digest_sent}
    """
```

## Router

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/scheduler/jobs` | 列表 + next_run_time |
| PATCH | `/api/v1/scheduler/jobs/{id}` | 改 cron / enabled |
| POST | `/api/v1/scheduler/jobs/{id}/run` | 立即觸發（背景） |
| GET | `/api/v1/scheduler/runs?job_id=&days=7&status=` | 執行歷史 |
| GET | `/api/v1/scheduler/runs/{run_id}` | 單筆詳情 |

## `data/scheduler_runs.csv` 欄位
```
run_id, job_id, started_at, finished_at, status, duration_seconds, error, output_summary
```

## 啟動方式
- `api/main.py` 在 `lifespan` startup hook：`SchedulerService.start()`
- shutdown hook：`SchedulerService.stop()`
- `CAPYSTOCK_SCHEDULER_DISABLED=1` → 跳過

## Windows Task Scheduler 範本
- `docs/DEPLOY/scheduler_winTask.xml.template`：可 import，系統開機就跑 `uvicorn`
- `<Triggers>` boot trigger + `<Actions>` 啟 PowerShell `cd ... && uvicorn api.main:app --port 8000`

## 驗收（自動化）
- SchedulerService：用 `BackgroundScheduler(timezone='Asia/Tokyo')`，inject `MemoryJobStore` + 加速 clock
- trigger_now：JobRun status=success、duration > 0
- timeout：handler 故意 sleep > timeout_seconds → status=timeout
- 失敗：handler raise → status=failed、error 寫入 csv
- daily_pipeline：mock 各 service，斷言呼叫順序 scan → analyze → realtime → digest
- Router：列表 / patch cron / trigger_now / runs filter
- 重啟持久化：scheduler_runs.csv 仍在；jobs 內存 + 改動寫入 `data/scheduler_jobs.json`

## 給實作者
- APScheduler 用 `BackgroundScheduler`（in-process）
- Job handler 必須是 idempotent
