"""daily_pipeline 單元測試。"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from api.workers import daily_pipeline


class _FakeAlert:
    def __init__(self, alert_type, severity, message=""):
        self.alert_type = alert_type
        self.severity = severity
        self.message = message


def test_run_pipeline_call_order(monkeypatch):
    calls: list[str] = []

    def fake_exists(today):
        calls.append("exists")
        return True

    def fake_analyze(today):
        calls.append("analyze")
        return {
            "7203": [_FakeAlert("exit", "critical", "out")],
            "9984": [_FakeAlert("accumulation", "info", "in")],
        }

    monkeypatch.setattr(daily_pipeline, "_today_signals_exists", fake_exists)
    monkeypatch.setattr(daily_pipeline, "_analyze_watchlist", fake_analyze)

    ns = MagicMock()
    ns.process_realtime_alert.side_effect = lambda *a, **kw: (
        calls.append("realtime"), [MagicMock(ok=True)],
    )[1]
    ns.process_daily_digest.side_effect = lambda *a, **kw: (
        calls.append("digest"), [MagicMock(ok=True)],
    )[1]

    summary = daily_pipeline.run(today=date(2026, 4, 27), notification_service=ns)

    assert summary["alerts_total"] == 2
    assert summary["realtime_sent"] == 1
    assert summary["digest_sent"] == 1
    # critical 才會送 realtime；非 critical 不送
    assert calls.count("realtime") == 1
    # order
    assert calls.index("analyze") < calls.index("realtime") < calls.index("digest")


def test_run_pipeline_dry_run(monkeypatch):
    monkeypatch.setattr(daily_pipeline, "_today_signals_exists", lambda t: True)
    monkeypatch.setattr(daily_pipeline, "_analyze_watchlist", lambda t: {})

    ns = MagicMock()
    ns.process_realtime_alert.return_value = []
    ns.process_daily_digest.return_value = []

    summary = daily_pipeline.run(today=date(2026, 4, 27), dry_run=True, notification_service=ns)
    assert summary["alerts_total"] == 0


def test_skip_scan_when_snapshot_exists(monkeypatch):
    monkeypatch.setattr(daily_pipeline, "_today_signals_exists", lambda t: True)
    monkeypatch.setattr(daily_pipeline, "_analyze_watchlist", lambda t: {})

    ns = MagicMock()
    ns.process_realtime_alert.return_value = []
    ns.process_daily_digest.return_value = []

    summary = daily_pipeline.run(today=date(2026, 4, 27), notification_service=ns)
    assert summary["scan_skipped"] is True
    assert summary["scan_rows"] == 0
