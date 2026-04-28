"""LineChannel 測試（mock requests.post）。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.notify.line_channel import LineChannel
from api.schemas.notify import NotificationPayload


@pytest.fixture
def payload():
    return NotificationPayload(title="t", body_text="body", severity="info")


def _mock_post(monkeypatch, status=200, text="ok"):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers", {})
        captured["data"] = kwargs.get("data")
        captured["json"] = kwargs.get("json")
        resp = MagicMock()
        resp.status_code = status
        resp.text = text
        return resp

    monkeypatch.setattr("api.notify.line_channel.requests.post", fake_post)
    return captured


def test_notify_mode_send(monkeypatch, payload):
    captured = _mock_post(monkeypatch)
    ch = LineChannel(notify_token="TOKEN", messaging_token="")
    assert ch.mode == "notify"
    results = ch.send(payload, [])
    assert len(results) == 1
    assert results[0].ok is True
    assert captured["headers"]["Authorization"] == "Bearer TOKEN"
    assert captured["data"]["message"] == "t\nbody"
    assert "notify-api.line.me" in captured["url"]


def test_notify_truncate(monkeypatch):
    captured = _mock_post(monkeypatch)
    ch = LineChannel(notify_token="T", messaging_token="")
    long_body = "x" * 1500
    ch.send(NotificationPayload(title="hi", body_text=long_body), [])
    msg = captured["data"]["message"]
    assert len(msg) <= 1000
    assert msg.endswith("…")


def test_messaging_mode_preferred(monkeypatch, payload):
    captured = _mock_post(monkeypatch)
    ch = LineChannel(notify_token="N", messaging_token="M", default_to="U123")
    assert ch.mode == "messaging"
    results = ch.send(payload, ["U123"])
    assert results[0].ok is True
    assert captured["json"]["to"] == "U123"
    assert captured["json"]["messages"][0]["text"] == "t\nbody"
    assert "api.line.me/v2/bot/message/push" in captured["url"]


def test_messaging_no_recipient_returns_error(monkeypatch, payload):
    _mock_post(monkeypatch)
    ch = LineChannel(messaging_token="M", default_to="")
    results = ch.send(payload, [])
    assert results[0].ok is False
    assert "recipient" in (results[0].error or "").lower()


def test_no_token_not_configured(monkeypatch):
    ch = LineChannel(notify_token="", messaging_token="")
    assert ch.mode == "none"
    assert ch.is_configured() is False
    results = ch.send(NotificationPayload(title="t", body_text="b"), [])
    assert results[0].ok is False


def test_http_error_marks_failed(monkeypatch, payload):
    _mock_post(monkeypatch, status=500, text="boom")
    ch = LineChannel(notify_token="T")
    results = ch.send(payload, [])
    assert results[0].ok is False
    assert "500" in (results[0].error or "")
