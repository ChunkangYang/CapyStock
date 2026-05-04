"""rules CRUD + preview + run endpoints。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services import notification_service as ns_module
from api.services import rule_store


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(ns_module, "LOG_PATH", tmp_path / "notification_log.csv")
    monkeypatch.setattr(rule_store, "RULES_PATH", tmp_path / "notification_rules.json")
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _payload(**kw):
    base = {
        "name": "每日彙總",
        "mode": "digest",
        "trigger": {"schedule": "daily", "time": "08:00"},
        "filters": {"alert_types": ["exit"], "min_severity": "info", "scope": "all", "codes": []},
        "channels": ["email"],
        "recipients_by_channel": {"email": ["a@b"]},
        "enabled": True,
    }
    base.update(kw)
    return base


def test_rules_crud_full_cycle(client):
    # list 空
    r = client.get("/api/v1/notify/rules")
    assert r.status_code == 200 and r.json() == []

    # create
    r = client.post("/api/v1/notify/rules", json=_payload())
    assert r.status_code == 201
    rule = r.json()
    assert rule["id"].startswith("rule-")
    rid = rule["id"]

    # patch
    r = client.patch(f"/api/v1/notify/rules/{rid}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    # patch 404
    r = client.patch("/api/v1/notify/rules/missing", json={"enabled": False})
    assert r.status_code == 404

    # delete
    r = client.delete(f"/api/v1/notify/rules/{rid}")
    assert r.status_code == 200

    # delete 404
    r = client.delete(f"/api/v1/notify/rules/{rid}")
    assert r.status_code == 404


def test_rule_run_dry_run(client):
    r = client.post("/api/v1/notify/rules", json=_payload())
    rid = r.json()["id"]
    r = client.post(f"/api/v1/notify/rules/{rid}/run", json={"dry_run": True})
    assert r.status_code == 200
    body = r.json()
    assert "preview" in body
    assert "每日彙總" in body["preview"]["title"]


def test_rule_run_404(client):
    r = client.post("/api/v1/notify/rules/missing/run", json={"dry_run": True})
    assert r.status_code == 404


def test_digest_preview_default_no_rule(client):
    r = client.post("/api/v1/notify/digest/preview", json={})
    assert r.status_code == 200
    body = r.json()
    assert "<h1>" in body["body_html"]
    assert "digest" in body["tags"]


def test_digest_preview_with_rule_and_date(client):
    r = client.post("/api/v1/notify/rules", json=_payload())
    rid = r.json()["id"]
    r = client.post(
        "/api/v1/notify/digest/preview",
        json={"rule_id": rid, "date": "2026-04-26"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "2026-04-26" in body["body_text"]
    assert any(t.startswith("rule:") for t in body["tags"])


def test_digest_preview_invalid_date(client):
    r = client.post("/api/v1/notify/digest/preview", json={"date": "bad-date"})
    assert r.status_code == 422


def test_digest_preview_rule_404(client):
    r = client.post("/api/v1/notify/digest/preview", json={"rule_id": "missing"})
    assert r.status_code == 404
