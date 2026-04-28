"""SchedulerService 單元測試。"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from api.schemas.scheduler import JobDef
from api.services import scheduler_service as ss


@pytest.fixture
def isolated_paths(tmp_path, monkeypatch):
    runs = tmp_path / "scheduler_runs.csv"
    jobs = tmp_path / "scheduler_jobs.json"
    monkeypatch.setattr(ss, "RUNS_PATH", runs)
    monkeypatch.setattr(ss, "JOBS_PATH", jobs)
    yield tmp_path


@pytest.fixture
def svc(isolated_paths):
    s = ss.SchedulerService()
    yield s
    try:
        s.stop()
    except Exception:
        pass


def test_default_jobs_loaded(svc):
    jobs = svc.list_jobs()
    ids = {j.id for j in jobs}
    assert {"scan_signals", "scan_dividend", "paper_advance", "daily_pipeline", "healthcheck_ping"}.issubset(ids)


def test_trigger_now_success(svc, monkeypatch):
    flag = {"called": False}

    def fake():
        flag["called"] = True
        return {"ok": True}

    import sys
    import types
    mod = types.ModuleType("_test_handlers")
    mod.fake = fake
    sys.modules["_test_handlers"] = mod

    svc._jobs["scan_signals"] = svc._jobs["scan_signals"].model_copy(
        update={"handler": "_test_handlers:fake"}
    )

    run = svc.trigger_now("scan_signals")
    assert run.status == "success"
    assert flag["called"]
    assert run.duration_seconds is not None and run.duration_seconds >= 0
    assert "ok" in (run.output_summary or "")


def test_trigger_now_failure(svc):
    import sys
    import types

    def boom():
        raise ValueError("kaboom")

    mod = types.ModuleType("_test_handlers_fail")
    mod.boom = boom
    sys.modules["_test_handlers_fail"] = mod

    svc._jobs["scan_signals"] = svc._jobs["scan_signals"].model_copy(
        update={"handler": "_test_handlers_fail:boom"}
    )

    run = svc.trigger_now("scan_signals")
    assert run.status == "failed"
    assert "kaboom" in (run.error or "")


def test_trigger_now_timeout(svc):
    import sys
    import types

    def slow():
        time.sleep(2.0)

    mod = types.ModuleType("_test_handlers_slow")
    mod.slow = slow
    sys.modules["_test_handlers_slow"] = mod

    svc._jobs["scan_signals"] = svc._jobs["scan_signals"].model_copy(
        update={"handler": "_test_handlers_slow:slow", "timeout_seconds": 1}
    )

    run = svc.trigger_now("scan_signals")
    assert run.status == "timeout"


def test_trigger_unknown_job_raises(svc):
    with pytest.raises(KeyError):
        svc.trigger_now("nonexistent")


def test_runs_persisted_to_csv(svc, isolated_paths):
    import sys, types
    mod = types.ModuleType("_thp")
    mod.ok = lambda: "done"
    sys.modules["_thp"] = mod
    svc._jobs["scan_signals"] = svc._jobs["scan_signals"].model_copy(
        update={"handler": "_thp:ok"}
    )
    svc.trigger_now("scan_signals")
    runs = svc.list_runs(job_id="scan_signals", days=7)
    assert len(runs) == 1
    assert runs[0].status == "success"


def test_update_job_persists(svc, isolated_paths):
    new = svc.update_job("scan_signals", cron="15 9 * * *", enabled=False)
    assert new.cron == "15 9 * * *"
    assert new.enabled is False
    # Re-load via fresh service
    svc2 = ss.SchedulerService()
    j = svc2.get_job("scan_signals")
    assert j.cron == "15 9 * * *"
    assert j.enabled is False


def test_update_unknown_job_raises(svc):
    with pytest.raises(KeyError):
        svc.update_job("nonexistent", cron="0 0 * * *")


def test_list_runs_filter(svc):
    import sys, types
    mod = types.ModuleType("_thp_filter")
    mod.ok = lambda: "x"
    mod.fail = lambda: (_ for _ in ()).throw(RuntimeError("e"))
    sys.modules["_thp_filter"] = mod
    svc._jobs["scan_signals"] = svc._jobs["scan_signals"].model_copy(
        update={"handler": "_thp_filter:ok"}
    )
    svc._jobs["paper_advance"] = svc._jobs["paper_advance"].model_copy(
        update={"handler": "_thp_filter:fail"}
    )
    svc.trigger_now("scan_signals")
    svc.trigger_now("paper_advance")

    success_runs = svc.list_runs(status="success")
    failed_runs = svc.list_runs(status="failed")
    assert all(r.status == "success" for r in success_runs)
    assert all(r.status == "failed" for r in failed_runs)
    assert len(success_runs) >= 1 and len(failed_runs) >= 1


def test_start_stop_idempotent(svc):
    svc.start()
    svc.stop()
    # second stop should not raise
    svc.stop()
