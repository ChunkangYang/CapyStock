"""/api/v1/notify/* router 測試。"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.notify.base import NotificationChannel
from api.schemas.notify import ChannelResult, NotificationPayload
from api.services import notification_service as ns_module
from api.services.notification_service import NotificationService


class FakeChannel(NotificationChannel):
    def __init__(self, name, ok=True, configured=True):
        self.name = name
        self._ok = ok
        self._configured = configured

    def send(self, payload, recipients):
        return [
            ChannelResult(
                channel=self.name,
                ok=self._ok,
                error=None if self._ok else "fail",
                sent_at=datetime.utcnow(),
                recipient=r or "default",
            )
            for r in (recipients or ["default"])
        ]

    def health_check(self):
        return self._configured

    def is_configured(self):
        return self._configured


@pytest.fixture
def client_with_fakes(tmp_path, monkeypatch):
    log = tmp_path / "notification_log.csv"
    monkeypatch.setattr(ns_module, "LOG_PATH", log)

    def fake_build():
        return NotificationService(
            channels={
                "email": FakeChannel("email", ok=True, configured=True),
                "line": FakeChannel("line", ok=False, configured=False),
            }
        )

    from api.routers import notify as notify_router

    monkeypatch.setattr(notify_router, "_service", fake_build)
    return TestClient(app)


def test_get_channels(client_with_fakes):
    r = client_with_fakes.get("/api/v1/notify/channels")
    assert r.status_code == 200
    data = r.json()
    names = {c["name"] for c in data}
    assert names == {"email", "line"}


def test_test_channel_ok(client_with_fakes):
    r = client_with_fakes.post(
        "/api/v1/notify/test",
        json={"channel": "email", "recipients": ["a@b.com"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["results"][0]["ok"] is True


def test_test_channel_failure_502(client_with_fakes):
    r = client_with_fakes.post(
        "/api/v1/notify/test",
        json={"channel": "line", "recipients": []},
    )
    assert r.status_code == 502


def test_send_partial_207(client_with_fakes):
    r = client_with_fakes.post(
        "/api/v1/notify/send",
        json={
            "title": "hi",
            "body_text": "b",
            "severity": "warn",
            "tags": ["test"],
            "channels": ["email", "line"],
            "recipients_by_channel": {
                "email": ["a@b.com"],
                "line": [],
            },
        },
    )
    assert r.status_code == 207
    body = r.json()
    assert len(body["results"]) == 2


def test_log_filter(client_with_fakes):
    client_with_fakes.post(
        "/api/v1/notify/send",
        json={
            "title": "x",
            "body_text": "b",
            "severity": "critical",
            "channels": ["email"],
            "recipients_by_channel": {"email": ["a@b.com"]},
        },
    )
    r = client_with_fakes.get("/api/v1/notify/log?days=7&severity=critical")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 1
    assert rows[0]["severity"] == "critical"
