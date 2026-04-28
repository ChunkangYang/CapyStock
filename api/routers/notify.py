"""通知 API。"""
from datetime import date as _date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from api.schemas.notify import (
    ChannelInfo,
    ChannelResult,
    DigestPreviewRequest,
    NotificationLogEntry,
    NotificationPayload,
    NotificationRule,
    RuleCreateRequest,
    RuleRunRequest,
    RuleUpdateRequest,
    SendRequest,
    TestRequest,
)
from api.services import notification_service as ns_module
from api.services import rule_store

router = APIRouter()


def _service():
    return ns_module.build_default_service()


@router.get("/notify/channels", response_model=list[ChannelInfo])
def list_channels():
    return _service().list_channels()


@router.post("/notify/test")
def test_channel(req: TestRequest):
    results = _service().test_channel(req.channel, req.recipients)
    return _multi_status(results)


@router.post("/notify/send")
def send(req: SendRequest):
    payload = NotificationPayload(
        title=req.title,
        body_text=req.body_text,
        body_html=req.body_html,
        severity=req.severity,
        tags=req.tags,
    )
    results = _service().send(payload, req.channels, req.recipients_by_channel)
    return _multi_status(results)


@router.get("/notify/log", response_model=list[NotificationLogEntry])
def read_log(
    days: int = Query(7, ge=1, le=90),
    channel: Optional[str] = None,
    severity: Optional[str] = None,
):
    return ns_module.read_log(days=days, channel=channel, severity=severity)


# ── S10: rules CRUD ─────────────────────────────────────────
@router.get("/notify/rules", response_model=list[NotificationRule])
def list_rules():
    return rule_store.list_rules()


@router.post("/notify/rules", response_model=NotificationRule, status_code=201)
def create_rule(req: RuleCreateRequest):
    if req.mode not in ("digest", "realtime"):
        raise HTTPException(status_code=422, detail="invalid mode")
    return rule_store.create_rule(req)


@router.patch("/notify/rules/{rule_id}", response_model=NotificationRule)
def update_rule(rule_id: str, req: RuleUpdateRequest):
    updated = rule_store.update_rule(rule_id, req)
    if updated is None:
        raise HTTPException(status_code=404, detail="rule not found")
    return updated


@router.delete("/notify/rules/{rule_id}")
def delete_rule(rule_id: str):
    ok = rule_store.delete_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="rule not found")
    return {"ok": True}


@router.post("/notify/rules/{rule_id}/run")
def run_rule(rule_id: str, req: RuleRunRequest | None = None):
    rule = rule_store.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    dry_run = bool(req.dry_run) if req else False
    svc = _service()
    today = _date.today()
    if rule.mode == "digest":
        payload = svc.build_digest_for_rule(rule, today, alerts_by_code={}, snapshot_summary=None)
        if dry_run:
            return {"results": [], "preview": payload.model_dump(mode="json")}
        results = svc.send(payload, rule.channels, rule.recipients_by_channel)
        return _multi_status(results)
    return JSONResponse(status_code=200, content={"results": [], "note": "realtime rules trigger only on alerts"})


@router.post("/notify/digest/preview")
def digest_preview(req: DigestPreviewRequest):
    svc = _service()
    target = _date.today()
    if req.date:
        try:
            target = _date.fromisoformat(req.date)
        except Exception:
            raise HTTPException(status_code=422, detail="invalid date")
    if req.rule_id:
        rule = rule_store.get_rule(req.rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="rule not found")
        payload = svc.build_digest_for_rule(rule, target, alerts_by_code={}, snapshot_summary=None)
    else:
        from api.notify.digest import build_digest as _bd
        payload = _bd(target, {}, None, "all")
    return payload.model_dump(mode="json")


def _multi_status(results: list[ChannelResult]):
    """成功 200、全失敗 502、部分失敗 207。"""
    oks = [r.ok for r in results]
    body = {"results": [r.model_dump(mode="json") for r in results]}
    if not results:
        return JSONResponse(status_code=200, content=body)
    if all(oks):
        return JSONResponse(status_code=200, content=body)
    if not any(oks):
        return JSONResponse(status_code=502, content=body)
    return JSONResponse(status_code=207, content=body)
