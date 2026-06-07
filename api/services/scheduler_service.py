"""SchedulerService — APScheduler-based 排程。

- 預設 jobs 內建（scan_signals / scan_dividend / paper_advance / daily_pipeline / healthcheck_ping）
- jobs 改動寫入 data/scheduler_jobs.json
- 執行紀錄寫 data/scheduler_runs.csv
"""
from __future__ import annotations

import csv
import importlib
import json
import os
import threading
import traceback
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger

from api.deps import DATA_DIR
from api.schemas.scheduler import JobDef, JobRun


JOBS_PATH = DATA_DIR / "scheduler_jobs.json"
RUNS_PATH = DATA_DIR / "scheduler_runs.csv"
RUNS_HEADER = [
    "run_id", "job_id", "started_at", "finished_at", "status",
    "duration_seconds", "error", "output_summary",
]
DEFAULT_TIMEZONE = "Asia/Tokyo"

_runs_lock = Lock()
_jobs_lock = Lock()


DEFAULT_JOBS: list[JobDef] = [
    JobDef(
        id="scan_signals",
        name="每日 signals 全市場掃描",
        cron="0 6 * * 1-5",
        handler="api.services.scheduler_service:_handler_scan_signals",
        timeout_seconds=1800,
    ),
    JobDef(
        id="scan_dividend",
        name="每週一 dividend 全市場掃描",
        cron="30 6 * * 1",
        handler="api.services.scheduler_service:_handler_scan_dividend",
        timeout_seconds=1800,
    ),
    JobDef(
        id="paper_advance",
        name="paper trading 每日推進",
        cron="0 7 * * 1-5",
        handler="api.services.scheduler_service:_handler_paper_advance",
        timeout_seconds=1800,
    ),
    JobDef(
        id="daily_pipeline",
        name="每日通知管線（analyze + digest）",
        cron="0 8 * * 1-5",
        handler="api.workers.daily_pipeline:run",
        timeout_seconds=1800,
    ),
    JobDef(
        id="weekly_universe_scan",
        name="每週全市場 signals 掃描（包含所有上市股票）",
        cron="0 9 * * 1",
        handler="api.services.scheduler_service:_handler_weekly_universe_scan",
        timeout_seconds=10800,  # 3 小時上限
    ),
    JobDef(
        id="edinet_daily_backfill",
        name="每日 EDINET 全市場申報回補（三盤第一盤輸入）+ 重算口袋名單",
        cron="30 5 * * *",
        handler="api.services.scheduler_service:_handler_edinet_daily_backfill",
        timeout_seconds=3600,
    ),
    JobDef(
        id="healthcheck_ping",
        name="健康檢查 ping",
        cron="*/30 * * * *",
        handler="api.workers.healthcheck:ping",
        timeout_seconds=60,
    ),
]


# ── 預設 handler shims（避免 worker module 引入 argparse 副作用） ──

def _handler_scan_signals():
    from api.services import scan_service
    universe = scan_service.load_universe("data/universe.csv")
    rows, errors = scan_service.run_signals_scan(universe)
    today_str = datetime.now().strftime("%Y-%m-%d")
    scan_service.write_snapshot("signals", rows, today_str, guard=True)
    if errors:
        scan_service.write_errors("signals", errors, today_str)
    return {"rows": len(rows), "errors": len(errors)}


def _handler_scan_dividend():
    from api.services import scan_service
    universe = scan_service.load_universe("data/universe.csv")
    rows, errors = scan_service.run_dividend_scan(universe)
    today_str = datetime.now().strftime("%Y-%m-%d")
    scan_service.write_snapshot("dividend", rows, today_str)
    if errors:
        scan_service.write_errors("dividend", errors, today_str)
    return {"rows": len(rows), "errors": len(errors)}


def _handler_paper_advance():
    from datetime import date
    from api.services import simulation_service, signal_service

    today = date.today()
    advanced = 0
    for sim in simulation_service.list_all():
        if sim.config.kind != "paper" or sim.status == "draft":
            continue
        if sim.state.cursor_date >= today:
            continue
        try:
            price_cache: dict = {}
            for cand in sim.config.candidates:
                try:
                    prices = signal_service.get_price_history(cand.code, days=365)
                    price_cache[cand.code] = {
                        p.date: {"open": p.open, "close": p.close} for p in prices
                    }
                except Exception:
                    pass
            simulation_service.advance_paper(sim.id, today, signal_service, price_cache)
            advanced += 1
        except Exception:
            continue
    return {"advanced": advanced}


def _handler_edinet_daily_backfill():
    """回補全市場 EDINET 每日申報 → 重算三盤口袋名單快照。

    解決 daily 快取（gitignore + named volume）不會隨同步進容器的缺口：
    排程在容器內執行，直接寫進 volume。
    """
    from capystock import edinet
    from api.services import pocket_service

    backfill = edinet.backfill_daily(days=7, refetch_recent=3)
    result = {"backfill": backfill}
    if backfill.get("ok"):
        scan = pocket_service.scan_pocket_list()
        pocket_service.write_snapshot(scan, guard=True)
        result["pocket_funnel"] = scan.get("funnel", {})
    return result


def _handler_weekly_universe_scan():
    """每週全市場掃描（所有上市股票）"""
    from api.services import scan_service
    from datetime import datetime

    print("[weekly_universe_scan] 開始全市場掃描...")
    start_time = datetime.now()

    try:
        universe = scan_service.load_universe("data/universe.csv")
        print(f"  加載 {len(universe)} 檔股票")

        rows, errors = scan_service.run_signals_scan(universe)
        today_str = datetime.now().strftime("%Y-%m-%d")

        scan_service.write_snapshot("signals", rows, today_str, guard=True)
        if errors:
            scan_service.write_errors("signals", errors, today_str)

        elapsed = (datetime.now() - start_time).total_seconds()
        result = {
            "rows": len(rows),
            "errors": len(errors),
            "elapsed_seconds": elapsed,
            "universe_size": len(universe)
        }
        print(f"  完成！耗時 {elapsed:.1f} 秒，掃描 {len(rows)} 檔股票，{len(errors)} 個錯誤")
        return result
    except Exception as e:
        print(f"  ✗ 掃描失敗：{e}")
        return {"error": str(e), "elapsed_seconds": (datetime.now() - start_time).total_seconds()}


# ── helper functions ─────────────────────────────────────────────

def _ensure_runs_file() -> None:
    RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not RUNS_PATH.exists():
        with RUNS_PATH.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(RUNS_HEADER)


def _append_run(run: JobRun) -> None:
    _ensure_runs_file()
    with _runs_lock:
        with RUNS_PATH.open("a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([
                run.run_id,
                run.job_id,
                run.started_at.isoformat(),
                run.finished_at.isoformat() if run.finished_at else "",
                run.status,
                f"{run.duration_seconds:.3f}" if run.duration_seconds is not None else "",
                run.error or "",
                run.output_summary or "",
            ])


def _read_runs(
    job_id: Optional[str] = None,
    days: int = 7,
    status: Optional[str] = None,
) -> list[JobRun]:
    if not RUNS_PATH.exists():
        return []
    cutoff = datetime.utcnow() - timedelta(days=days)
    out: list[JobRun] = []
    with RUNS_PATH.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                started = datetime.fromisoformat(row["started_at"])
            except Exception:
                continue
            if started < cutoff:
                continue
            if job_id and row["job_id"] != job_id:
                continue
            if status and row["status"] != status:
                continue
            finished = None
            if row.get("finished_at"):
                try:
                    finished = datetime.fromisoformat(row["finished_at"])
                except Exception:
                    finished = None
            duration = None
            if row.get("duration_seconds"):
                try:
                    duration = float(row["duration_seconds"])
                except Exception:
                    duration = None
            out.append(JobRun(
                run_id=row["run_id"],
                job_id=row["job_id"],
                started_at=started,
                finished_at=finished,
                status=row["status"],  # type: ignore[arg-type]
                duration_seconds=duration,
                error=row.get("error") or None,
                output_summary=row.get("output_summary") or None,
            ))
    out.sort(key=lambda r: r.started_at, reverse=True)
    return out


def _resolve_handler(dotted: str) -> Callable:
    if ":" not in dotted:
        raise ValueError(f"handler 格式錯誤（需 'module:func'）：{dotted}")
    mod_name, func_name = dotted.split(":", 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, func_name)


def _load_job_overrides() -> dict:
    if not JOBS_PATH.exists():
        return {}
    try:
        with JOBS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_job_overrides(overrides: dict) -> None:
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _jobs_lock:
        with JOBS_PATH.open("w", encoding="utf-8") as f:
            json.dump(overrides, f, ensure_ascii=False, indent=2)


def _apply_overrides(jobs: list[JobDef]) -> list[JobDef]:
    overrides = _load_job_overrides()
    out: list[JobDef] = []
    for j in jobs:
        ov = overrides.get(j.id) or {}
        merged = j.model_copy(update={k: v for k, v in ov.items() if k in JobDef.model_fields})
        out.append(merged)
    return out


def _truncate(s: str, limit: int = 240) -> str:
    s = (s or "").replace("\n", " ").replace("\r", " ")
    return s[:limit]


# ── SchedulerService ──────────────────────────────────────────────

class SchedulerService:
    """In-process APScheduler 包裝。"""

    def __init__(
        self,
        scheduler: Optional[BaseScheduler] = None,
        timezone: str = DEFAULT_TIMEZONE,
        clock: Optional[Callable[[], datetime]] = None,
        write_runs: bool = True,
    ):
        self._scheduler = scheduler or BackgroundScheduler(timezone=timezone)
        self._clock = clock or datetime.utcnow
        self._write_runs = write_runs
        self._jobs: dict[str, JobDef] = {j.id: j for j in _apply_overrides(DEFAULT_JOBS)}
        self._running_runs: dict[str, JobRun] = {}
        self._registered = False

    # ── lifecycle ──
    def start(self) -> None:
        if not self._registered:
            for jdef in self._jobs.values():
                self._register_job(jdef)
            self._registered = True
        if not self._scheduler.running:
            self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler.running:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception:
                pass

    # ── jobs API ──
    def list_jobs(self) -> list[JobDef]:
        out: list[JobDef] = []
        for jdef in self._jobs.values():
            next_run = None
            try:
                aps_job = self._scheduler.get_job(jdef.id)
                if aps_job and aps_job.next_run_time:
                    next_run = aps_job.next_run_time
            except Exception:
                next_run = None
            out.append(jdef.model_copy(update={"next_run_time": next_run}))
        return out

    def get_job(self, job_id: str) -> Optional[JobDef]:
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **fields) -> JobDef:
        jdef = self._jobs.get(job_id)
        if jdef is None:
            raise KeyError(job_id)
        clean = {k: v for k, v in fields.items() if v is not None and k in JobDef.model_fields}
        new_def = jdef.model_copy(update=clean)
        self._jobs[job_id] = new_def

        overrides = _load_job_overrides()
        overrides[job_id] = {**overrides.get(job_id, {}), **clean}
        _save_job_overrides(overrides)

        if self._registered:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass
            self._register_job(new_def)
        return new_def

    def list_runs(
        self,
        job_id: Optional[str] = None,
        days: int = 7,
        status: Optional[str] = None,
    ) -> list[JobRun]:
        return _read_runs(job_id=job_id, days=days, status=status)

    def get_run(self, run_id: str) -> Optional[JobRun]:
        for r in _read_runs(days=365):
            if r.run_id == run_id:
                return r
        return self._running_runs.get(run_id)

    def trigger_now(self, job_id: str) -> JobRun:
        jdef = self._jobs.get(job_id)
        if jdef is None:
            raise KeyError(job_id)
        return self._execute(jdef)

    # ── internals ──
    def _register_job(self, jdef: JobDef) -> None:
        if not jdef.enabled:
            return
        try:
            trigger = CronTrigger.from_crontab(jdef.cron, timezone=self._scheduler.timezone)
        except Exception:
            return
        self._scheduler.add_job(
            func=lambda jd=jdef: self._execute(jd),
            trigger=trigger,
            id=jdef.id,
            name=jdef.name,
            max_instances=jdef.max_instances,
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=300,
        )

    def _execute(self, jdef: JobDef) -> JobRun:
        run_id = uuid.uuid4().hex
        started = self._clock()
        run = JobRun(
            run_id=run_id,
            job_id=jdef.id,
            started_at=started,
            status="running",
        )
        self._running_runs[run_id] = run

        try:
            handler = _resolve_handler(jdef.handler)
        except Exception as e:
            run.status = "failed"
            run.error = f"resolve handler failed: {e}"
            run.finished_at = self._clock()
            run.duration_seconds = max(0.0, (run.finished_at - started).total_seconds())
            self._finalize(run)
            return run

        result_holder: dict = {}

        def _target():
            try:
                result_holder["value"] = handler()
            except Exception as e:
                result_holder["error"] = e
                result_holder["traceback"] = traceback.format_exc()

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=jdef.timeout_seconds)

        finished = self._clock()
        run.finished_at = finished
        run.duration_seconds = max(0.0, (finished - started).total_seconds())

        if thread.is_alive():
            run.status = "timeout"
            run.error = f"timeout after {jdef.timeout_seconds}s"
        elif "error" in result_holder:
            run.status = "failed"
            run.error = _truncate(str(result_holder["error"]))
        else:
            run.status = "success"
            val = result_holder.get("value")
            if val is not None:
                run.output_summary = _truncate(str(val))

        self._finalize(run)
        return run

    def _finalize(self, run: JobRun) -> None:
        self._running_runs.pop(run.run_id, None)
        if self._write_runs:
            try:
                _append_run(run)
            except Exception:
                pass


# ── singleton ─────────────────────────────────────────────────────

_service_singleton: Optional[SchedulerService] = None
_singleton_lock = Lock()


def get_scheduler_service() -> SchedulerService:
    global _service_singleton
    with _singleton_lock:
        if _service_singleton is None:
            _service_singleton = SchedulerService()
        return _service_singleton


def reset_singleton() -> None:
    """測試用：重置 singleton。"""
    global _service_singleton
    with _singleton_lock:
        if _service_singleton is not None:
            try:
                _service_singleton.stop()
            except Exception:
                pass
        _service_singleton = None
