"""NotificationService 整合（多 channel + log）。"""
from __future__ import annotations

from datetime import datetime

import pytest

from api.notify.base import NotificationChannel
from api.schemas.notify import ChannelResult, NotificationPayload
from api.services import notification_service as ns_module
from api.services.notification_service import NotificationService


class FakeChannel(NotificationChannel):
    def __init__(self, name, ok=True, configured=True):
        self.name = name
        self._ok = ok
        self._configured = configured
        self.calls = []

    def send(self, payload, recipients):
        self.calls.append((payload, recipients))
        now = datetime.utcnow()
        return [
            ChannelResult(
                channel=self.name,
                ok=self._ok,
                error=None if self._ok else "boom",
                sent_at=now,
                recipient=r,
            )
            for r in (recipients or ["default"])
        ]

    def health_check(self):
        return self._configured

    def is_configured(self):
        return self._configured


@pytest.fixture
def tmp_log(tmp_path, monkeypatch):
    log = tmp_path / "notification_log.csv"
    monkeypatch.setattr(ns_module, "LOG_PATH", log)
    return log


def test_send_multi_channel_one_fail(tmp_log):
    svc = NotificationService(
        channels={
            "email": FakeChannel("email", ok=True),
            "line": FakeChannel("line", ok=False),
        }
    )
    payload = NotificationPayload(title="t", body_text="b", severity="warn", tags=["x"])
    results = svc.send(payload, ["email", "line"], {"email": ["a@b.com"], "line": []})
    assert len(results) == 2
    assert any(r.ok for r in results)
    assert any(not r.ok for r in results)
    # log written 2 lines + header
    text = tmp_log.read_text(encoding="utf-8")
    assert "email" in text and "line" in text
    assert text.count("\n") >= 3  # header + at least 2 rows


def test_unknown_channel_is_failure(tmp_log):
    svc = NotificationService(channels={"email": FakeChannel("email", ok=True)})
    payload = NotificationPayload(title="t", body_text="b")
    results = svc.send(payload, ["nope"], {})
    assert len(results) == 1
    assert results[0].ok is False
    assert "unknown" in (results[0].error or "").lower()


def test_list_channels(tmp_log):
    svc = NotificationService(
        channels={
            "email": FakeChannel("email", configured=True),
            "line": FakeChannel("line", configured=False),
        }
    )
    info = svc.list_channels()
    by_name = {i.name: i for i in info}
    assert by_name["email"].configured is True
    assert by_name["email"].healthy is True
    assert by_name["line"].configured is False
    assert by_name["line"].healthy is False


def test_test_channel_uses_send(tmp_log):
    fc = FakeChannel("email", ok=True)
    svc = NotificationService(channels={"email": fc})
    results = svc.test_channel("email", ["x@y.z"])
    assert results[0].ok is True
    assert len(fc.calls) == 1
    payload, recipients = fc.calls[0]
    assert payload.title.startswith("[CapyStock]")
    assert recipients == ["x@y.z"]


def test_read_log_filters(tmp_log):
    svc = NotificationService(channels={"email": FakeChannel("email", ok=True)})
    svc.send(
        NotificationPayload(title="a", body_text="b", severity="critical"),
        ["email"],
        {"email": ["a@b.com"]},
    )
    svc.send(
        NotificationPayload(title="b", body_text="b", severity="info"),
        ["email"],
        {"email": ["a@b.com"]},
    )
    crit = ns_module.read_log(days=7, severity="critical")
    assert len(crit) == 1
    assert crit[0].title == "a"
    info = ns_module.read_log(days=7, channel="email")
    assert len(info) == 2


def test_channel_raise_caught(tmp_log):
    class BoomChannel(FakeChannel):
        def send(self, payload, recipients):
            raise RuntimeError("kaboom")

    svc = NotificationService(channels={"x": BoomChannel("x")})
    results = svc.send(
        NotificationPayload(title="t", body_text="b"), ["x"], {"x": ["r"]}
    )
    assert results[0].ok is False
    assert "kaboom" in (results[0].error or "")
