"""EmailChannel 測試（dry-run + smtplib mock）。"""
from __future__ import annotations

from email import message_from_bytes
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from api.notify.email_channel import EmailChannel
from api.schemas.notify import NotificationPayload


@pytest.fixture
def payload():
    return NotificationPayload(
        title="hello",
        body_text="# heading\n\nbody line",
        severity="info",
        tags=["test"],
    )


def test_dry_run_writes_eml(tmp_path, payload):
    ch = EmailChannel(
        host="ignored",
        user="from@example.com",
        password="p",
        sender="CapyStock <from@example.com>",
        dry_run=True,
        dry_run_dir=tmp_path,
    )
    results = ch.send(payload, ["to@example.com"])
    assert len(results) == 1
    assert results[0].ok is True
    files = list(tmp_path.glob("*.eml"))
    assert len(files) == 1
    raw = files[0].read_bytes()
    msg = message_from_bytes(raw)
    assert msg["Subject"] == "hello"
    assert msg["From"] == "CapyStock <from@example.com>"
    assert msg["To"] == "to@example.com"
    # multipart with html part
    parts = list(msg.walk())
    assert any(p.get_content_type() == "text/html" for p in parts)
    html_part = next(p for p in parts if p.get_content_type() == "text/html")
    assert "<h1>heading</h1>" in html_part.get_payload(decode=True).decode()


def test_dry_run_via_env(monkeypatch, tmp_path, payload):
    monkeypatch.setenv("SMTP_DRY_RUN", "1")
    ch = EmailChannel(
        host="x", user="u", password="p", sender="u@x", dry_run_dir=tmp_path
    )
    assert ch.dry_run is True
    ch.send(payload, ["a@b.com"])
    assert list(tmp_path.glob("*.eml"))


def test_is_configured_false_when_no_host(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.delenv("SMTP_DRY_RUN", raising=False)
    ch = EmailChannel(host="", user="", password="", dry_run=False)
    assert ch.is_configured() is False


def test_real_send_uses_smtplib(monkeypatch, tmp_path, payload):
    """實際走 smtplib 路徑（mock SMTP class）。"""
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            self.host = host
            self.port = port

        def ehlo(self):
            pass

        def starttls(self, context=None):
            pass

        def login(self, u, p):
            self.u = u

        def send_message(self, msg):
            sent.append(msg)

        def quit(self):
            pass

    monkeypatch.setattr("api.notify.email_channel.smtplib.SMTP", FakeSMTP)
    ch = EmailChannel(
        host="smtp.example.com",
        port=587,
        user="u@x",
        password="p",
        sender="u@x",
        dry_run=False,
        dry_run_dir=tmp_path,
    )
    results = ch.send(payload, ["to@example.com"])
    assert len(results) == 1
    assert results[0].ok is True
    assert len(sent) == 1
    assert sent[0]["Subject"] == "hello"
