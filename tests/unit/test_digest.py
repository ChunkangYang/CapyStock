"""build_digest 測試。"""
from __future__ import annotations

from datetime import date

from api.notify.digest import build_digest


def _alert(t, sev="warn", msg="x"):
    return {"alert_type": t, "severity": sev, "message": msg}


def test_build_digest_sections_and_counts():
    alerts = {
        "7203": [_alert("exit", "warn", "exit 條件三選二"), _alert("accumulation", "info", "外資連買")],
        "9984": [_alert("stop_loss", "critical", "停損觸發 -5%")],
    }
    payload = build_digest(date(2026, 4, 26), alerts, {"signals_total": 30}, "watchlist")
    assert "每日彙總" in payload.title
    assert "2026-04-26" in payload.body_text
    assert "<h2>" in payload.body_html
    # 標題與 row 數
    assert "持倉警示（1）" in payload.body_text
    assert "停損警示（1）" in payload.body_text
    assert "吃貨訊號（1）" in payload.body_text
    assert "7203" in payload.body_html
    assert "9984" in payload.body_html
    # severity = critical（最大）
    assert payload.severity == "critical"
    assert payload.metadata["alerts_total"] == 3
    assert "模擬交易摘要" in payload.body_text


def test_build_digest_empty():
    payload = build_digest(date(2026, 4, 26), {}, None, "all")
    assert "(無)" in payload.body_text
    assert payload.severity == "info"
    assert payload.metadata["alerts_total"] == 0
    assert "digest" in payload.tags
