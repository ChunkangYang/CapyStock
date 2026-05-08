"""SMTP Email channel。"""
from __future__ import annotations

import os
import smtplib

import capystock.config  # noqa: F401  ensure _load_env() has run
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from api.notify.base import NotificationChannel
from api.notify.digest import text_to_html
from api.schemas.notify import ChannelResult, NotificationPayload


class EmailChannel(NotificationChannel):
    name = "email"

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        sender: Optional[str] = None,
        dry_run: Optional[bool] = None,
        dry_run_dir: Optional[Path] = None,
    ):
        self.host = host if host is not None else os.environ.get("SMTP_HOST", "")
        self.port = int(port) if port is not None else int(os.environ.get("SMTP_PORT", "587") or 587)
        self.user = user if user is not None else os.environ.get("SMTP_USER", "")
        self.password = password if password is not None else os.environ.get("SMTP_PASS", "")
        self.sender = sender if sender is not None else os.environ.get(
            "SMTP_FROM", self.user or "noreply@localhost"
        )
        if dry_run is None:
            self.dry_run = os.environ.get("SMTP_DRY_RUN", "0") == "1"
        else:
            self.dry_run = bool(dry_run)
        if dry_run_dir is None:
            from api.deps import DATA_DIR

            self.dry_run_dir = DATA_DIR / ".smtp_outbox"
        else:
            self.dry_run_dir = dry_run_dir

    def is_configured(self) -> bool:
        if self.dry_run:
            return True
        return bool(self.host and self.user and self.password)

    def health_check(self) -> bool:
        if self.dry_run:
            return True
        if not self.is_configured():
            return False
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=5) as s:
                    s.noop()
            else:
                with smtplib.SMTP(self.host, self.port, timeout=5) as s:
                    s.ehlo()
            return True
        except Exception:
            return False

    def _build_message(
        self, payload: NotificationPayload, recipient: str
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = payload.title
        msg["From"] = self.sender
        msg["To"] = recipient
        msg.set_content(payload.body_text or "")
        body_html = payload.body_html or text_to_html(payload.body_text or "")
        msg.add_alternative(body_html, subtype="html")
        return msg

    def send(
        self,
        payload: NotificationPayload,
        recipients: list[str],
    ) -> list[ChannelResult]:
        results: list[ChannelResult] = []
        now = datetime.utcnow()

        if self.dry_run:
            self.dry_run_dir.mkdir(parents=True, exist_ok=True)
            for r in recipients:
                msg = self._build_message(payload, r)
                ts = now.strftime("%Y%m%dT%H%M%S%f")
                fname = self.dry_run_dir / f"{ts}_{r.replace('@', '_at_')}.eml"
                fname.write_bytes(bytes(msg))
                results.append(
                    ChannelResult(
                        channel=self.name,
                        ok=True,
                        error=None,
                        sent_at=now,
                        recipient=r,
                    )
                )
            return results

        try:
            if self.port == 465:
                ctx = ssl.create_default_context()
                smtp = smtplib.SMTP_SSL(self.host, self.port, timeout=15, context=ctx)
            else:
                smtp = smtplib.SMTP(self.host, self.port, timeout=15)
                smtp.ehlo()
                if self.port == 587:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
            try:
                if self.user and self.password:
                    smtp.login(self.user, self.password)
                for r in recipients:
                    msg = self._build_message(payload, r)
                    try:
                        smtp.send_message(msg)
                        results.append(
                            ChannelResult(
                                channel=self.name,
                                ok=True,
                                error=None,
                                sent_at=datetime.utcnow(),
                                recipient=r,
                            )
                        )
                    except Exception as e:
                        results.append(
                            ChannelResult(
                                channel=self.name,
                                ok=False,
                                error=str(e),
                                sent_at=datetime.utcnow(),
                                recipient=r,
                            )
                        )
            finally:
                try:
                    smtp.quit()
                except Exception:
                    pass
        except Exception as e:
            for r in recipients:
                results.append(
                    ChannelResult(
                        channel=self.name,
                        ok=False,
                        error=str(e),
                        sent_at=datetime.utcnow(),
                        recipient=r,
                    )
                )
        return results
