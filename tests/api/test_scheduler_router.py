"""Scheduler router 整合測試。"""
from __future__ import annotations

import sys
import time
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.services import scheduler_service as ss


@pytest.fixture
def client(tmp_path, monkeypatch):
    runs = tmp_path / "scheduler_runs.csv"
    jobs = tmp_path / "scheduler_jobs.json"
    monkeypatch.setattr(ss, "RUNS_PATH", runs)
    monkeypatch.setattr(ss, "JOBS_PATH", jobs)
    monkeypatch.setenv("CAPYSTOCK_SCHEDULER_DISABLED", "1")
    ss.reset_singleton()

    # 把 default jobs 的 handler 全替換成快速 dummy
    mod = types.ModuleType("_router_handlers")
    mod.fast = lambda: "ok"
    sys.modules["_router_handlers"] = mod
    svc = ss.get_scheduler_service()
    for jid in list(svc._jobs.keys()):
        svc._jobs[jid] = svc._jobs[jid].model_copy(update={"handler": "_router_handlers:fast"})

    from api.main import app
    with TestClient(app) as c:
        yield c
    ss.reset_singleton()


def test_list_jobs(client):
    r = client.get("/api/v1/scheduler/jobs")
    assert r.status_code == 200
    data = r.json()
    ids = {j["id"] for j in data["jobs"]}
    assert "scan_signals" in ids
    assert "daily_pipeline" in ids


def test_patch_job_cron(client):
    r = client.patch("/api/v1/scheduler/jobs/scan_signals", json={"cron": "0 9 * * *"})
    assert r.status_code == 200
    assert r.json()["cron"] == "0 9 * * *"


def test_patch_job_not_found(client):
    r = client.patch("/api/v1/scheduler/jobs/nope", json={"enabled": False})
    assert r.status_code == 404


def test_trigger_job_and_list_runs(client):
    r = client.post("/api/v1/scheduler/jobs/scan_signals/run")
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == "scan_signals"

    # background task — wait briefly
    for _ in range(20):
        rr = client.get("/api/v1/scheduler/runs", params={"job_id": "scan_signals"})
        if rr.status_code == 200 and rr.json()["runs"]:
            break
        time.sleep(0.1)
    else:
        pytest.fail("run never persisted")

    runs = rr.json()["runs"]
    assert len(runs) >= 1
    assert runs[0]["status"] == "success"


def test_trigger_unknown_job(client):
    r = client.post("/api/v1/scheduler/jobs/nope/run")
    assert r.status_code == 404


def test_runs_filter_by_status(client):
    client.post("/api/v1/scheduler/jobs/scan_signals/run")
    for _ in range(20):
        rr = client.get("/api/v1/scheduler/runs", params={"status": "success"})
        if rr.status_code == 200 and rr.json()["runs"]:
            break
        time.sleep(0.1)
    assert all(r["status"] == "success" for r in rr.json()["runs"])
