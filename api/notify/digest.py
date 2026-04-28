"""digest / HTML 組裝 helper（S9 階段只提供 markdown→HTML、純文字）。

S10 會擴充 build_digest()。
"""
from __future__ import annotations

import html
import re


def text_to_html(body_text: str) -> str:
    """把純文字（含 `# `, `## `, `- ` 等簡單 markdown）轉成最小 HTML。

    避免引入 markdown library 依賴；只支援標題、無序清單、段落。
    """
    lines = body_text.splitlines()
    out: list[str] = []
    in_ul = False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_ul()
            continue

        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            close_ul()
            level = len(h.group(1))
            out.append(f"<h{level}>{html.escape(h.group(2))}</h{level}>")
            continue

        if line.lstrip().startswith(("- ", "* ")):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            content = line.lstrip()[2:]
            out.append(f"<li>{html.escape(content)}</li>")
            continue

        close_ul()
        out.append(f"<p>{html.escape(line)}</p>")

    close_ul()
    return "\n".join(out)


def build_digest(
    target_date,
    alerts_by_code: dict,
    snapshot_summary: dict | None = None,
    scope: str = "watchlist",
):
    """組裝每日彙總 NotificationPayload。

    alerts_by_code: {code: [Alert | dict]}（Alert 物件需有 .alert_type/.severity/.message，
    或 dict 同 key）
    snapshot_summary: 額外 metric（例如 {"signals_total": 30, "paper_sims": [...]}）
    """
    from api.schemas.notify import NotificationPayload

    date_str = target_date.isoformat() if hasattr(target_date, "isoformat") else str(target_date)

    def _atype(a):
        return getattr(a, "alert_type", None) or (a.get("alert_type") if isinstance(a, dict) else None)

    def _msg(a):
        return getattr(a, "message", None) or (a.get("message", "") if isinstance(a, dict) else "")

    def _sev(a):
        return getattr(a, "severity", None) or (a.get("severity") if isinstance(a, dict) else "info")

    buckets: dict[str, list[tuple[str, str, str]]] = {
        "exit": [],
        "stop_loss": [],
        "accumulation": [],
        "info": [],
    }
    for code, alerts in alerts_by_code.items():
        for a in alerts:
            t = _atype(a) or "info"
            buckets.setdefault(t, []).append((code, _sev(a), _msg(a)))

    section_titles = {
        "exit": "持倉警示",
        "stop_loss": "停損警示",
        "accumulation": "吃貨訊號",
        "info": "其他訊息",
    }

    text_lines: list[str] = [f"# CapyStock 每日彙總 — {date_str}", ""]
    html_parts: list[str] = [
        f"<h1>CapyStock 每日彙總 — {html.escape(date_str)}</h1>",
        f"<p>scope: {html.escape(scope)}</p>",
    ]

    for key in ["exit", "stop_loss", "accumulation", "info"]:
        rows = buckets.get(key, [])
        title = f"{section_titles[key]}（{len(rows)}）"
        text_lines.append(f"## {title}")
        html_parts.append(f"<h2>{html.escape(title)}</h2>")
        if not rows:
            text_lines.append("(無)")
            html_parts.append("<p>(無)</p>")
        else:
            html_parts.append("<ul>")
            for code, sev, msg in rows:
                line = f"- {code} [{sev}] {msg}"
                text_lines.append(line)
                html_parts.append(
                    f"<li><b>{html.escape(code)}</b> "
                    f"[{html.escape(sev)}] {html.escape(msg)}</li>"
                )
            html_parts.append("</ul>")
        text_lines.append("")

    if snapshot_summary:
        text_lines.append("## 模擬交易摘要")
        html_parts.append("<h2>模擬交易摘要</h2>")
        html_parts.append("<ul>")
        for k, v in snapshot_summary.items():
            text_lines.append(f"- {k}: {v}")
            html_parts.append(f"<li>{html.escape(str(k))}: {html.escape(str(v))}</li>")
        html_parts.append("</ul>")

    body_text = "\n".join(text_lines).rstrip() + "\n"
    body_html = "\n".join(html_parts)

    total = sum(len(v) for v in buckets.values())
    severity = "info"
    if any(s == "critical" for _, sev_list in buckets.items() for _, s, _ in sev_list):
        severity = "critical"
    elif any(s == "warn" for _, sev_list in buckets.items() for _, s, _ in sev_list):
        severity = "warn"

    return NotificationPayload(
        title=f"[CapyStock] 每日彙總 {date_str}（{total} alerts）",
        body_text=body_text,
        body_html=body_html,
        severity=severity,  # type: ignore[arg-type]
        tags=["digest", scope],
        metadata={"date": date_str, "scope": scope, "alerts_total": total},
    )


def truncate_for_line(text: str, limit: int = 1000) -> str:
    """LINE Notify 1000 字元限制；超過 truncate 並結尾加 `…`。"""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
