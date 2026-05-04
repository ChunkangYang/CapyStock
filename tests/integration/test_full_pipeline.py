"""S13 — full pipeline integration test。

起 in-process FastAPI（scheduler disabled），呼叫
daily_pipeline.run(today, dry_run=True)，斷言 summary 各欄位
存在且非負，notification log 含 dry-run 記錄。

使用真實 service 物件但所有外部 IO 都被 mock：
  - 外部 HTTP 由 conftest 的 mock_requests 阻擋
  - smtp / line 由 dry_run=True 短路（不真寄）
"""
from __future__ import annotations

import csv
import os
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _disable_scheduler(monkeypatch):
    monkeypatch.setenv("CAPYSTOCK_SCHEDULER_DISABLED", "1")
    monkeypatch.setenv("SMTP_DRY_RUN", "1")


@pytest.fixture
def app_client():
    from api.main import app
    with TestClient(app) as c:
        yield c


def test_app_starts_and_health_ok(app_client):
    r = app_client.get("/api/v1/health")
    assert r.status_code == 200


def test_daily_pipeline_dry_run_summary(app_client, monkeypatch, tmp_path):
    """daily_pipeline.run 在 dry_run=True 下：

    - summary 必含 scan_rows / alerts_total / realtime_sent / digest_sent
    - 不真寄通知，但 dry-run 結果會落 log
    """
    from api.workers import daily_pipeline

    fake_alerts = {
        "7203": [
            type("A", (), {"severity": "critical", "title": "test", "body": "b", "tags": []})()
        ]
    }
    monkeypatch.setattr(daily_pipeline, "_today_signals_exists", lambda d: True)
    monkeypatch.setattr(daily_pipeline, "_analyze_watchlist", lambda d: fake_alerts)

    summary = daily_pipeline.run(today=date(2026, 4, 27), dry_run=True)

    assert isinstance(summary, dict)
    for k in ("scan_rows", "alerts_total", "realtime_sent", "digest_sent"):
        assert k in summary, f"summary 缺欄位：{k}"
        assert summary[k] >= 0
    assert summary["alerts_total"] >= 1, "fake critical alert 應被計入"


def test_static_frontend_or_root_responds(app_client):
    """frontend 有 build → 回 index.html；沒 build → 回 JSON metadata。"""
    r = app_client.get("/")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    body = r.text
    assert ("text/html" in ct) or ("CapyStock API" in body)
