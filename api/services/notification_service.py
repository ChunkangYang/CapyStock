"""NotificationService — 編排多通道、寫 log、規則評估。

S9：channel registry + send / test_channel / list_channels / log。
S10：build_digest / evaluate_rules / process_daily_digest / process_realtime_alert。
"""
from __future__ import annotations

import csv
import os
from datetime import date as _date, datetime, timedelta, time as _time
from pathlib import Path
from threading import Lock
from typing import Iterable, Optional

from api.deps import DATA_DIR
from api.notify.base import NotificationChannel
from api.notify.digest import build_digest as _build_digest
from api.notify.email_channel import EmailChannel
from api.notify.line_channel import LineChannel
from api.schemas.notify import (
    ChannelInfo,
    ChannelResult,
    NotificationLogEntry,
    NotificationPayload,
    NotificationRule,
)


LOG_PATH = DATA_DIR / "notification_log.csv"
LOG_HEADER = ["ts", "channel", "recipient", "severity", "title", "ok", "error", "tags"]

_log_lock = Lock()


def _ensure_log() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        with LOG_PATH.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(LOG_HEADER)


def append_log(
    payload: NotificationPayload, results: list[ChannelResult]
) -> None:
    _ensure_log()
    with _log_lock:
        with LOG_PATH.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            for r in results:
                w.writerow(
                    [
                        r.sent_at.isoformat(),
                        r.channel,
                        r.recipient,
                        payload.severity,
                        payload.title,
                        "1" if r.ok else "0",
                        r.error or "",
                        ";".join(payload.tags),
                    ]
                )


def read_log(
    days: int = 7,
    channel: Optional[str] = None,
    severity: Optional[str] = None,
) -> list[NotificationLogEntry]:
    if not LOG_PATH.exists():
        return []
    cutoff = datetime.utcnow() - timedelta(days=days)
    out: list[NotificationLogEntry] = []
    with LOG_PATH.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                ts = datetime.fromisoformat(row["ts"])
            except Exception:
                continue
            if ts < cutoff:
                continue
            if channel and row["channel"] != channel:
                continue
            if severity and row["severity"] != severity:
                continue
            out.append(
                NotificationLogEntry(
                    ts=ts,
                    channel=row["channel"],
                    recipient=row["recipient"],
                    severity=row["severity"],  # type: ignore[arg-type]
                    title=row["title"],
                    ok=row["ok"] == "1",
                    error=row.get("error") or None,
                    tags=[t for t in row.get("tags", "").split(";") if t],
                )
            )
    out.sort(key=lambda e: e.ts, reverse=True)
    return out


class NotificationService:
    def __init__(self, channels: dict[str, NotificationChannel]):
        self.channels = channels

    def list_channels(self) -> list[ChannelInfo]:
        out: list[ChannelInfo] = []
        for name, ch in self.channels.items():
            out.append(
                ChannelInfo(
                    name=name,
                    configured=ch.is_configured(),
                    healthy=ch.health_check() if ch.is_configured() else False,
                )
            )
        return out

    def send(
        self,
        payload: NotificationPayload,
        channel_names: list[str],
        recipients_by_channel: dict[str, list[str]],
    ) -> list[ChannelResult]:
        all_results: list[ChannelResult] = []
        for name in channel_names:
            ch = self.channels.get(name)
            if ch is None:
                all_results.append(
                    ChannelResult(
                        channel=name,
                        ok=False,
                        error=f"unknown channel '{name}'",
                        sent_at=datetime.utcnow(),
                        recipient="",
                    )
                )
                continue
            recipients = recipients_by_channel.get(name, [])
            try:
                results = ch.send(payload, recipients)
            except Exception as e:
                results = [
                    ChannelResult(
                        channel=name,
                        ok=False,
                        error=str(e),
                        sent_at=datetime.utcnow(),
                        recipient=recipients[0] if recipients else "",
                    )
                ]
            all_results.extend(results)
        append_log(payload, all_results)
        return all_results

    def test_channel(
        self, channel_name: str, recipients: Optional[list[str]] = None
    ) -> list[ChannelResult]:
        payload = NotificationPayload(
            title="[CapyStock] Test",
            body_text="This is a test notification from CapyStock.",
            severity="info",
            tags=["test"],
        )
        recipients = recipients or self._default_recipients(channel_name)
        return self.send(
            payload,
            [channel_name],
            {channel_name: recipients},
        )

    # ── S10 ──────────────────────────────────────────────
    def build_digest_for_rule(
        self,
        rule: NotificationRule,
        target_date: _date,
        alerts_by_code: Optional[dict] = None,
        snapshot_summary: Optional[dict] = None,
    ) -> NotificationPayload:
        """根據 rule.filters 過濾 alerts，組裝 digest payload。"""
        alerts_by_code = alerts_by_code if alerts_by_code is not None else {}
        scope_codes = _scope_codes(rule.filters.scope)
        filtered: dict[str, list] = {}
        for code, alerts in alerts_by_code.items():
            if scope_codes is not None and code not in scope_codes:
                continue
            keep = []
            for a in alerts:
                t = getattr(a, "alert_type", None) or (a.get("alert_type") if isinstance(a, dict) else "info")
                s = getattr(a, "severity", None) or (a.get("severity") if isinstance(a, dict) else "info")
                if filter_alert_for_rule(t, s, code, rule):
                    keep.append(a)
            if keep:
                filtered[code] = keep
        payload = _build_digest(target_date, filtered, snapshot_summary, rule.filters.scope)
        payload.tags = list(payload.tags) + [f"rule:{rule.id}"]
        payload.metadata = dict(payload.metadata)
        payload.metadata["rule_id"] = rule.id
        return payload

    def process_daily_digest(
        self,
        today: _date,
        now: Optional[datetime] = None,
        dry_run: bool = False,
        alerts_by_code: Optional[dict] = None,
        snapshot_summary: Optional[dict] = None,
    ) -> list[ChannelResult]:
        """掃過 enabled mode=digest rules，依 trigger.time 與 last_run 判斷是否該跑。"""
        from api.services import rule_store

        now = now or datetime.now()
        all_results: list[ChannelResult] = []
        for rule in rule_store.list_rules():
            if rule.mode != "digest" or not rule.enabled:
                continue
            last = _last_digest_run(rule.id)
            if not should_run_digest(rule, now, last):
                continue
            payload = self.build_digest_for_rule(
                rule, today, alerts_by_code=alerts_by_code, snapshot_summary=snapshot_summary,
            )
            if dry_run:
                all_results.append(
                    ChannelResult(
                        channel="dry_run",
                        ok=True,
                        sent_at=datetime.utcnow(),
                        recipient=f"rule:{rule.id}",
                    )
                )
                continue
            results = self.send(payload, rule.channels, rule.recipients_by_channel)
            all_results.extend(results)
        return all_results

    def process_realtime_alert(
        self,
        alert,
        code: str,
        dry_run: bool = False,
    ) -> list[ChannelResult]:
        """對 enabled mode=realtime rules 評估命中、24h dedupe、送出。"""
        from api.services import rule_store

        atype = getattr(alert, "alert_type", None) or alert.get("alert_type")
        sev = getattr(alert, "severity", None) or alert.get("severity", "info")
        msg = getattr(alert, "message", None) or alert.get("message", "")

        all_results: list[ChannelResult] = []
        for rule in rule_store.list_rules():
            if rule.mode != "realtime" or not rule.enabled:
                continue
            if not rule.trigger.on_alert:
                continue
            scope_codes = _scope_codes(rule.filters.scope)
            if scope_codes is not None and code not in scope_codes:
                continue
            if not filter_alert_for_rule(atype, sev, code, rule):
                continue
            if _realtime_already_sent(rule.id, code, atype):
                continue
            title = f"[CapyStock] {atype.upper()} — {code}"
            body_text = f"{code} {atype} [{sev}]\n{msg}"
            payload = NotificationPayload(
                title=title,
                body_text=body_text,
                severity=sev,
                tags=["realtime", f"rule:{rule.id}", f"code:{code}", f"type:{atype}"],
                metadata={"rule_id": rule.id, "code": code, "alert_type": atype},
            )
            if dry_run:
                all_results.append(
                    ChannelResult(
                        channel="dry_run",
                        ok=True,
                        sent_at=datetime.utcnow(),
                        recipient=f"rule:{rule.id}",
                    )
                )
                continue
            results = self.send(payload, rule.channels, rule.recipients_by_channel)
            all_results.extend(results)
        return all_results

    @staticmethod
    def _default_recipients(channel_name: str) -> list[str]:
        if channel_name == "email":
            raw = os.environ.get("NOTIFY_DEFAULT_RECIPIENTS", "")
            return [x.strip() for x in raw.split(",") if x.strip()]
        return []


SEVERITY_ORDER = {"info": 0, "warn": 1, "critical": 2}


def _meets_min_severity(sev: str, min_sev: str) -> bool:
    return SEVERITY_ORDER.get(sev, 0) >= SEVERITY_ORDER.get(min_sev, 0)


def filter_alert_for_rule(alert_type: str, severity: str, code: str, rule: NotificationRule) -> bool:
    """判斷單筆 alert 是否符合 rule 過濾條件。"""
    f = rule.filters
    if f.alert_types and alert_type not in f.alert_types:
        return False
    if not _meets_min_severity(severity, f.min_severity):
        return False
    if f.codes and code not in f.codes:
        return False
    return True


def _scope_codes(scope: str) -> Optional[set[str]]:
    """回傳 scope 對應的股票代碼集合；'all' 回傳 None 代表不限制。"""
    if scope == "all":
        return None
    if scope == "watchlist":
        try:
            from capystock import storage
            return set(storage.load_watchlist().keys())
        except Exception:
            return set()
    if scope == "favorites":
        try:
            from api.services import favorite_service
            favs = favorite_service.list_favorites()
            return {f.code for f in favs}
        except Exception:
            return set()
    return None


def should_run_digest(rule: NotificationRule, now: datetime, last_run: Optional[datetime]) -> bool:
    """判斷一條 digest rule 在 now 是否應該執行。

    - schedule=daily：當 now.time() >= trigger.time 且今日尚未跑過 → True
    - last_run 為 None 視為從未跑過
    """
    if not rule.enabled or rule.mode != "digest":
        return False
    trig = rule.trigger
    if trig.schedule != "daily":
        return False
    if not trig.time:
        return False
    try:
        hh, mm = [int(x) for x in trig.time.split(":")]
        target = _time(hour=hh, minute=mm)
    except Exception:
        return False
    if now.time() < target:
        return False
    if last_run is not None and last_run.date() == now.date():
        return False
    return True


def _last_digest_run(rule_id: str) -> Optional[datetime]:
    """從 notification_log.csv 找該 rule 最後一次成功送 digest 的時間。"""
    if not LOG_PATH.exists():
        return None
    tag = f"rule:{rule_id}"
    last: Optional[datetime] = None
    with LOG_PATH.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if tag not in (row.get("tags") or ""):
                continue
            try:
                ts = datetime.fromisoformat(row["ts"])
            except Exception:
                continue
            if last is None or ts > last:
                last = ts
    return last


def _realtime_already_sent(rule_id: str, code: str, alert_type: str, within_hours: int = 24) -> bool:
    """過去 N 小時內同 (rule_id, code, alert_type) 是否已成功送過。"""
    if not LOG_PATH.exists():
        return False
    cutoff = datetime.utcnow() - timedelta(hours=within_hours)
    needle_rule = f"rule:{rule_id}"
    needle_code = f"code:{code}"
    needle_type = f"type:{alert_type}"
    with LOG_PATH.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            tags = row.get("tags", "") or ""
            if needle_rule not in tags or needle_code not in tags or needle_type not in tags:
                continue
            if row.get("ok") != "1":
                continue
            try:
                ts = datetime.fromisoformat(row["ts"])
            except Exception:
                continue
            if ts >= cutoff:
                return True
    return False


def build_default_service() -> NotificationService:
    """根據環境變數組裝預設通道。"""
    return NotificationService(
        channels={
            "email": EmailChannel(),
            "line": LineChannel(),
        }
    )
