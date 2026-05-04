"""通知規則的持久化（data/notification_rules.json）。"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from threading import Lock
from typing import Optional

from api.deps import DATA_DIR
from api.schemas.notify import NotificationRule, RuleCreateRequest, RuleUpdateRequest


RULES_PATH = DATA_DIR / "notification_rules.json"
_lock = Lock()


def _path() -> Path:
    return RULES_PATH


def _load_raw() -> dict:
    p = _path()
    if not p.exists():
        return {"rules": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"rules": []}


def _save_raw(data: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="rules_", suffix=".json", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def list_rules() -> list[NotificationRule]:
    data = _load_raw()
    out: list[NotificationRule] = []
    for raw in data.get("rules", []):
        try:
            out.append(NotificationRule.model_validate(raw))
        except Exception:
            continue
    return out


def get_rule(rule_id: str) -> Optional[NotificationRule]:
    for r in list_rules():
        if r.id == rule_id:
            return r
    return None


def create_rule(req: RuleCreateRequest) -> NotificationRule:
    with _lock:
        data = _load_raw()
        rule = NotificationRule(
            id=f"rule-{uuid.uuid4().hex[:8]}",
            **req.model_dump(),
        )
        data.setdefault("rules", []).append(rule.model_dump(mode="json"))
        _save_raw(data)
        return rule


def update_rule(rule_id: str, req: RuleUpdateRequest) -> Optional[NotificationRule]:
    with _lock:
        data = _load_raw()
        rules = data.get("rules", [])
        for i, raw in enumerate(rules):
            if raw.get("id") == rule_id:
                current = NotificationRule.model_validate(raw)
                update_data = req.model_dump(exclude_unset=True)
                merged = current.model_dump()
                merged.update(update_data)
                new_rule = NotificationRule.model_validate(merged)
                rules[i] = new_rule.model_dump(mode="json")
                _save_raw(data)
                return new_rule
        return None


def delete_rule(rule_id: str) -> bool:
    with _lock:
        data = _load_raw()
        rules = data.get("rules", [])
        before = len(rules)
        data["rules"] = [r for r in rules if r.get("id") != rule_id]
        if len(data["rules"]) == before:
            return False
        _save_raw(data)
        return True
