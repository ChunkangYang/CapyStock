"""NotificationRule 規則評估、digest 整合、realtime dedupe 測試。"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from api.notify.base import NotificationChannel
from api.schemas.notify import (
    ChannelResult,
    NotificationRule,
    RuleCreateRequest,
    RuleFilters,
    RuleTrigger,
)
from api.services import notification_service as ns_module
from api.services import rule_store
from api.services.notification_service import (
    NotificationService,
    filter_alert_for_rule,
    should_run_digest,
)


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """把 LOG_PATH 與 RULES_PATH 都導向 tmp_path。"""
    log_path = tmp_path / "notification_log.csv"
    rules_path = tmp_path / "notification_rules.json"
    monkeypatch.setattr(ns_module, "LOG_PATH", log_path)
    monkeypatch.setattr(rule_store, "RULES_PATH", rules_path)
    yield


class FakeChannel(NotificationChannel):
    def __init__(self, name="email", ok=True):
        self.name = name
        self._ok = ok
        self.calls = []

    def send(self, payload, recipients):
        self.calls.append((payload, list(recipients)))
        return [
            ChannelResult(
                channel=self.name, ok=self._ok,
                error=None if self._ok else "boom",
                sent_at=datetime.utcnow(),
                recipient=r,
            )
            for r in (recipients or ["default"])
        ]

    def health_check(self):
        return True

    def is_configured(self):
        return True


def _make_rule(mode="digest", **kw):
    base = dict(
        name="r", mode=mode,
        trigger=RuleTrigger(schedule="daily", time="08:00") if mode == "digest" else RuleTrigger(on_alert=True),
        filters=RuleFilters(scope="all"),
        channels=["email"],
        recipients_by_channel={"email": ["a@b"]},
        enabled=True,
    )
    base.update(kw)
    return rule_store.create_rule(RuleCreateRequest(**base))


def test_filter_alert_for_rule_min_severity():
    rule = NotificationRule(
        id="r1", name="r", mode="realtime",
        trigger=RuleTrigger(on_alert=True),
        filters=RuleFilters(min_severity="critical", scope="all"),
        channels=["email"],
    )
    assert filter_alert_for_rule("stop_loss", "critical", "7203", rule)
    assert not filter_alert_for_rule("stop_loss", "warn", "7203", rule)


def test_filter_alert_types_and_codes():
    rule = NotificationRule(
        id="r2", name="r", mode="realtime",
        trigger=RuleTrigger(on_alert=True),
        filters=RuleFilters(alert_types=["stop_loss"], codes=["7203"], scope="all"),
        channels=["email"],
    )
    assert filter_alert_for_rule("stop_loss", "warn", "7203", rule)
    assert not filter_alert_for_rule("exit", "warn", "7203", rule)
    assert not filter_alert_for_rule("stop_loss", "warn", "9984", rule)


def test_should_run_digest_time_gating():
    rule = NotificationRule(
        id="r3", name="r", mode="digest",
        trigger=RuleTrigger(schedule="daily", time="08:00"),
        filters=RuleFilters(scope="all"),
        channels=["email"],
    )
    today = date(2026, 4, 26)
    assert not should_run_digest(rule, datetime(2026, 4, 26, 7, 59), None)
    assert should_run_digest(rule, datetime(2026, 4, 26, 8, 0), None)
    # 同日已跑過 → 不再跑
    assert not should_run_digest(rule, datetime(2026, 4, 26, 8, 30), datetime(2026, 4, 26, 8, 1))
    # catch-up：時間已過但今日尚未跑過
    assert should_run_digest(rule, datetime(2026, 4, 26, 8, 30), datetime(2026, 4, 25, 8, 1))


def test_digest_filters_alerts_and_sends_once():
    """5 個 alert，rule filter 留 2 → channel.send 被呼叫 1 次（digest 合併）。"""
    rule = _make_rule(
        mode="digest",
        filters=RuleFilters(alert_types=["stop_loss"], min_severity="warn", scope="all"),
    )
    ch = FakeChannel("email")
    svc = NotificationService(channels={"email": ch})
    alerts = {
        "7203": [
            {"alert_type": "stop_loss", "severity": "critical", "message": "stop"},
            {"alert_type": "exit", "severity": "warn", "message": "exit"},
        ],
        "9984": [
            {"alert_type": "stop_loss", "severity": "warn", "message": "stop2"},
            {"alert_type": "accumulation", "severity": "info", "message": "buy"},
        ],
        "6758": [
            {"alert_type": "stop_loss", "severity": "info", "message": "low"},
        ],
    }
    results = svc.process_daily_digest(
        today=date(2026, 4, 26),
        now=datetime(2026, 4, 26, 8, 30),
        alerts_by_code=alerts,
    )
    assert len(ch.calls) == 1
    payload, _ = ch.calls[0]
    assert "7203" in payload.body_text
    assert "9984" in payload.body_text
    assert "6758" not in payload.body_text  # min_severity=warn 過濾掉 info
    assert "exit" not in payload.body_text or "停損警示（2）" in payload.body_text
    assert all(r.ok for r in results)


def test_digest_skip_when_disabled_or_wrong_mode():
    _make_rule(mode="digest", enabled=False)
    _make_rule(mode="realtime")
    ch = FakeChannel("email")
    svc = NotificationService(channels={"email": ch})
    svc.process_daily_digest(
        today=date(2026, 4, 26),
        now=datetime(2026, 4, 26, 8, 30),
        alerts_by_code={"7203": [{"alert_type": "exit", "severity": "warn", "message": "x"}]},
    )
    assert ch.calls == []


def test_realtime_dedupe_within_24h():
    rule = _make_rule(
        mode="realtime",
        filters=RuleFilters(alert_types=["stop_loss"], min_severity="warn", scope="all"),
    )
    ch = FakeChannel("email")
    svc = NotificationService(channels={"email": ch})
    alert = {"alert_type": "stop_loss", "severity": "critical", "message": "drop"}
    r1 = svc.process_realtime_alert(alert, "7203")
    r2 = svc.process_realtime_alert(alert, "7203")
    assert len(r1) == 1 and r1[0].ok
    assert r2 == []  # dedupe → 第二次空


def test_realtime_filter_miss():
    _make_rule(
        mode="realtime",
        filters=RuleFilters(alert_types=["stop_loss"], min_severity="critical", scope="all"),
    )
    ch = FakeChannel("email")
    svc = NotificationService(channels={"email": ch})
    # severity warn < critical → 過濾掉
    r = svc.process_realtime_alert(
        {"alert_type": "stop_loss", "severity": "warn", "message": "m"},
        "7203",
    )
    assert r == []
    assert ch.calls == []


def test_rule_store_crud():
    from api.schemas.notify import RuleUpdateRequest
    rule = _make_rule(mode="digest")
    assert rule_store.get_rule(rule.id) is not None
    updated = rule_store.update_rule(rule.id, RuleUpdateRequest(enabled=False))
    assert updated.enabled is False
    assert rule_store.delete_rule(rule.id) is True
    assert rule_store.delete_rule(rule.id) is False
