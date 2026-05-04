"""LINE channel — 優先 LINE Messaging API（push），fallback LINE Notify。"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import requests

from api.notify.base import NotificationChannel
from api.notify.digest import truncate_for_line
from api.schemas.notify import ChannelResult, NotificationPayload


LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"
LINE_MESSAGING_PUSH_URL = "https://api.line.me/v2/bot/message/push"


class LineChannel(NotificationChannel):
    name = "line"

    def __init__(
        self,
        notify_token: Optional[str] = None,
        messaging_token: Optional[str] = None,
        default_to: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.notify_token = (
            notify_token if notify_token is not None else os.environ.get("LINE_NOTIFY_TOKEN", "")
        )
        self.messaging_token = (
            messaging_token
            if messaging_token is not None
            else os.environ.get("LINE_MESSAGING_TOKEN", "")
        )
        self.default_to = (
            default_to if default_to is not None else os.environ.get("LINE_MESSAGING_TO", "")
        )
        self.timeout = timeout

    @property
    def mode(self) -> str:
        if self.messaging_token:
            return "messaging"
        if self.notify_token:
            return "notify"
        return "none"

    def is_configured(self) -> bool:
        return self.mode != "none"

    def health_check(self) -> bool:
        return self.is_configured()

    def send(
        self,
        payload: NotificationPayload,
        recipients: list[str],
    ) -> list[ChannelResult]:
        text_full = (payload.title + "\n" + payload.body_text).strip()
        text = truncate_for_line(text_full, 1000)
        now = datetime.utcnow()

        if self.mode == "notify":
            return self._send_notify(text, now)
        if self.mode == "messaging":
            return self._send_messaging(text, recipients, now)
        return [
            ChannelResult(
                channel=self.name,
                ok=False,
                error="LINE channel not configured",
                sent_at=now,
                recipient="line:default",
            )
        ]

    def _send_notify(self, text: str, now: datetime) -> list[ChannelResult]:
        try:
            resp = requests.post(
                LINE_NOTIFY_URL,
                headers={"Authorization": f"Bearer {self.notify_token}"},
                data={"message": text},
                timeout=self.timeout,
            )
            ok = 200 <= resp.status_code < 300
            err = None if ok else f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            ok, err = False, str(e)
        return [
            ChannelResult(
                channel=self.name,
                ok=ok,
                error=err,
                sent_at=datetime.utcnow(),
                recipient="line:default",
            )
        ]

    def _send_messaging(
        self, text: str, recipients: list[str], now: datetime
    ) -> list[ChannelResult]:
        targets = recipients or ([self.default_to] if self.default_to else [])
        if not targets:
            return [
                ChannelResult(
                    channel=self.name,
                    ok=False,
                    error="No LINE recipient (set LINE_MESSAGING_TO or pass recipients)",
                    sent_at=now,
                    recipient="line:default",
                )
            ]
        results: list[ChannelResult] = []
        for to in targets:
            try:
                resp = requests.post(
                    LINE_MESSAGING_PUSH_URL,
                    headers={
                        "Authorization": f"Bearer {self.messaging_token}",
                        "Content-Type": "application/json",
                    },
                    json={"to": to, "messages": [{"type": "text", "text": text}]},
                    timeout=self.timeout,
                )
                ok = 200 <= resp.status_code < 300
                err = None if ok else f"HTTP {resp.status_code}: {resp.text[:200]}"
            except Exception as e:
                ok, err = False, str(e)
            results.append(
                ChannelResult(
                    channel=self.name,
                    ok=ok,
                    error=err,
                    sent_at=datetime.utcnow(),
                    recipient=f"line:{to}",
                )
            )
        return results
