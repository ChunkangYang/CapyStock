"""通知相關 Pydantic models。"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


Severity = Literal["info", "warn", "critical"]


class NotificationPayload(BaseModel):
    title: str
    body_text: str
    body_html: Optional[str] = None
    severity: Severity = "info"
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class ChannelResult(BaseModel):
    channel: str
    ok: bool
    error: Optional[str] = None
    sent_at: datetime
    recipient: str


class ChannelInfo(BaseModel):
    name: str
    configured: bool
    healthy: bool


class TestRequest(BaseModel):
    channel: str
    recipients: Optional[list[str]] = None


class SendRequest(BaseModel):
    title: str
    body_text: str
    body_html: Optional[str] = None
    severity: Severity = "info"
    tags: list[str] = Field(default_factory=list)
    channels: list[str]
    recipients_by_channel: dict[str, list[str]] = Field(default_factory=dict)


class NotificationLogEntry(BaseModel):
    ts: datetime
    channel: str
    recipient: str
    severity: Severity
    title: str
    ok: bool
    error: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


# ── S10: rules ─────────────────────────────────────────────
RuleMode = Literal["digest", "realtime"]
RuleScope = Literal["watchlist", "favorites", "all"]
AlertType = Literal["exit", "stop_loss", "accumulation", "info"]


class RuleTrigger(BaseModel):
    schedule: Optional[Literal["daily", "weekly"]] = None
    time: Optional[str] = None  # "HH:MM"
    on_alert: Optional[bool] = None


class RuleFilters(BaseModel):
    alert_types: list[AlertType] = Field(default_factory=list)
    min_severity: Severity = "info"
    scope: RuleScope = "watchlist"
    codes: list[str] = Field(default_factory=list)


class NotificationRule(BaseModel):
    id: str
    name: str
    mode: RuleMode
    trigger: RuleTrigger = Field(default_factory=RuleTrigger)
    filters: RuleFilters = Field(default_factory=RuleFilters)
    channels: list[str] = Field(default_factory=list)
    recipients_by_channel: dict[str, list[str]] = Field(default_factory=dict)
    enabled: bool = True


class RuleCreateRequest(BaseModel):
    name: str
    mode: RuleMode
    trigger: RuleTrigger = Field(default_factory=RuleTrigger)
    filters: RuleFilters = Field(default_factory=RuleFilters)
    channels: list[str] = Field(default_factory=list)
    recipients_by_channel: dict[str, list[str]] = Field(default_factory=dict)
    enabled: bool = True


class RuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    mode: Optional[RuleMode] = None
    trigger: Optional[RuleTrigger] = None
    filters: Optional[RuleFilters] = None
    channels: Optional[list[str]] = None
    recipients_by_channel: Optional[dict[str, list[str]]] = None
    enabled: Optional[bool] = None


class RuleRunRequest(BaseModel):
    dry_run: bool = False


class DigestPreviewRequest(BaseModel):
    rule_id: Optional[str] = None
    date: Optional[str] = None  # YYYY-MM-DD
