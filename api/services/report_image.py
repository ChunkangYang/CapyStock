"""把每日自動模擬交易 log 畫成一張日報圖（PNG）— Telegram sendPhoto 用。

用 Pillow 直接畫（無 matplotlib 相依），配色比照前端深色主題。
字型：Windows 走 Meiryo、Linux（Actions runner）走 Noto Sans CJK；都找不到就退回預設點陣字
（英數仍可讀，日文會變方框）— 呼叫端可據此決定要不要改送純文字。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# ── 版面 / 配色 ─────────────────────────────────────────────────────────────
W = 980
PAD = 28
BG = (10, 15, 26)
CARD = (17, 26, 43)
LINE = (30, 41, 59)
FG = (226, 232, 240)
MUTED = (127, 145, 168)
POS = (52, 211, 153)
NEG = (248, 113, 113)
ACCENT = (96, 165, 250)
GOLD = (251, 191, 36)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/YuGothM.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]


def _font_path() -> Optional[str]:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _font(size: int, bold: bool = False):
    p = _font_path()
    if p is None:
        return ImageFont.load_default()
    try:
        # ttc 內 index 0 為 Regular；粗體用同字型加大字級近似（避免找不到 Bold 檔案）
        return ImageFont.truetype(p, size)
    except OSError:
        return ImageFont.load_default()


def has_cjk_font() -> bool:
    return _font_path() is not None


def _yen(v) -> str:
    return f"¥{round(v or 0):,}"


def _pct(v) -> str:
    return "—" if v is None else f"{v * 100:+.2f}%"


def _color(v) -> tuple:
    return POS if (v or 0) >= 0 else NEG


def _rrect(d: ImageDraw.ImageDraw, box, radius, fill, outline=None):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline)


def _clip(s: str, max_px: int, font) -> str:
    """依實際像素寬截字（全形/半形混排都準），過長補「…」。"""
    s = str(s)
    if font.getlength(s) <= max_px:
        return s
    while s and font.getlength(s + "…") > max_px:
        s = s[:-1]
    return s + "…"


def render_daily_report(log: dict, curve: Optional[dict] = None,
                        out_path: str | Path = "daily_report.png") -> Path:
    """畫一張日報圖：KPI 卡 → 資金曲線 → 今日進出場 → 持倉暫定損益。"""
    f_title = _font(30)
    f_sub = _font(15)
    f_h = _font(17)
    f_kpi_label = _font(13)
    f_kpi = _font(25)
    f_kpi_sm = _font(17)
    f_row = _font(15)
    f_small = _font(13)

    opened = log.get("opened") or []
    closed = log.get("closed") or []
    holdings = sorted(log.get("holdings") or [],
                      key=lambda h: h.get("unrealized_pnl_jpy", 0), reverse=True)
    skipped = (log.get("skipped") or [])[:3] if not opened else []

    # 依內容估高度
    row_h = 30
    sec_head = 40
    h = 110 + 108 + 24                      # header + KPI + gap
    chart_h = 200 if (curve and curve.get("dates")) else 0
    h += chart_h + (24 if chart_h else 0)
    for rows in (opened, closed, skipped, holdings):
        if rows:
            h += sec_head + row_h * len(rows) + 14
    h += PAD

    img = Image.new("RGB", (W, int(h)), BG)
    d = ImageDraw.Draw(img)
    y = PAD

    # ── Header ──
    d.text((PAD, y), "CapyStock 自動模擬交易日報", font=f_title, fill=FG)
    y += 38
    d.text((PAD, y), f"{log.get('date')}　三盤口袋名單進場 / 棘輪移動停損出場"
                     f"　候選 {log.get('pocket_candidates', 0)} 檔"
                     + ("　（DRY RUN）" if log.get("dry_run") else ""),
           font=f_sub, fill=MUTED)
    y += 34

    # ── KPI 卡 ──
    kpis = [
        ("總權益", _yen(log.get("equity_jpy")), _pct(log.get("total_return_pct")),
         _color(log.get("total_return_pct"))),
        ("已實現損益", _yen(log.get("realized_pnl_jpy")),
         f"{log.get('closed_count', 0)} 筆結算", _color(log.get("realized_pnl_jpy"))),
        ("未實現（暫定）", _yen(log.get("unrealized_pnl_jpy")),
         f"{log.get('open_count', 0)} 檔持倉", _color(log.get("unrealized_pnl_jpy"))),
        ("現金 / 持股市價", _yen(log.get("cash_jpy")), _yen(log.get("market_value_jpy")), FG),
    ]
    cw = (W - PAD * 2 - 12 * 3) / 4
    for i, (label, val, sub, col) in enumerate(kpis):
        x0 = PAD + i * (cw + 12)
        _rrect(d, (x0, y, x0 + cw, y + 96), 10, CARD, LINE)
        d.text((x0 + 14, y + 12), _clip(label, cw - 24, f_kpi_label), font=f_kpi_label, fill=MUTED)
        d.text((x0 + 14, y + 32), val, font=f_kpi if len(val) <= 11 else f_kpi_sm, fill=col)
        d.text((x0 + 14, y + 68), sub, font=f_small, fill=MUTED)
    y += 96 + 24

    # ── 資金曲線 ──
    if chart_h:
        x0, x1 = PAD, W - PAD
        y0, y1 = y, y + chart_h
        _rrect(d, (x0, y0, x1, y1), 10, CARD, LINE)
        eq = [v for v in curve["equity"] if v is not None]
        base = curve.get("initial_cash_jpy") or (eq[0] if eq else 0)
        lo, hi = min(eq + [base]), max(eq + [base])
        span = (hi - lo) or 1
        px0, px1 = x0 + 58, x1 - 14
        py0, py1 = y0 + 16, y1 - 26
        n = len(curve["equity"])

        def px(i): return px0 + (px1 - px0) * (i / max(1, n - 1))
        def py(v): return py1 - (py1 - py0) * ((v - lo) / span)

        # 起始資金基準線
        d.line([(px0, py(base)), (px1 - 34, py(base))], fill=(71, 85, 105), width=1)
        d.text((px1 - 30, py(base) - 8), "起始", font=f_small, fill=MUTED)
        pts = [(px(i), py(v)) for i, v in enumerate(curve["equity"]) if v is not None]
        if len(pts) >= 2:
            d.polygon([(pts[0][0], py1)] + pts + [(pts[-1][0], py1)], fill=(18, 44, 41))
            d.line(pts, fill=POS, width=2)
            d.ellipse([pts[-1][0] - 4, pts[-1][1] - 4, pts[-1][0] + 4, pts[-1][1] + 4], fill=POS)
        elif len(pts) == 1:
            d.ellipse([pts[0][0] - 4, pts[0][1] - 4, pts[0][0] + 4, pts[0][1] + 4], fill=POS)
            d.text(((x0 + x1) / 2 - 90, (y0 + y1) / 2 - 10),
                   "資金曲線：每日累積中（今天是第 1 天）", font=f_sub, fill=MUTED)
        if hi - lo > 1:
            d.text((x0 + 10, py0 - 2), f"{round(hi/10000)}萬", font=f_small, fill=MUTED)
            d.text((x0 + 10, py1 - 12), f"{round(lo/10000)}萬", font=f_small, fill=MUTED)
        if n:
            d.text((px0, py1 + 6), curve["dates"][0], font=f_small, fill=MUTED)
            d.text((px1 - 66, py1 + 6), curve["dates"][-1], font=f_small, fill=MUTED)
        y = y1 + 24

    def section(title: str, color: tuple, rows: list[tuple[str, tuple]]):
        nonlocal y
        d.line([(PAD, y), (W - PAD, y)], fill=LINE, width=1)
        d.text((PAD, y + 10), title, font=f_h, fill=color)
        y += sec_head
        for cells in rows:
            for text, x, col, fnt in cells:
                d.text((x, y + 6), text, font=fnt, fill=col)
            y += row_h
        y += 14

    if opened:
        rows = []
        for o in opened:
            rows.append([
                (str(o["code"]), PAD, ACCENT, f_row),
                (o.get("name", "")[:14], PAD + 62, FG, f_row),
                (f"{o['shares']} 股", PAD + 260, FG, f_row),
                (f"@{_yen(o['entry_price'])}", PAD + 340, FG, f_row),
                (_clip(o.get("reason", ""), W - PAD * 2 - 450, f_small), PAD + 450, MUTED, f_small),
            ])
        section(f"今日進場 {len(opened)} 檔", POS, rows)

    if closed:
        rows = []
        for c in closed:
            rows.append([
                (str(c["code"]), PAD, ACCENT, f_row),
                (c.get("name", "")[:14], PAD + 62, FG, f_row),
                (f"出場 {_yen(c.get('exit_price'))}", PAD + 260, FG, f_row),
                (_yen(c.get("pnl_jpy")), PAD + 400, _color(c.get("pnl_jpy")), f_row),
                (_pct(c.get("pnl_pct")), PAD + 520, _color(c.get("pnl_jpy")), f_row),
                (str(c.get("exit_reason") or ""), PAD + 620, MUTED, f_small),
            ])
        section(f"今日出場 {len(closed)} 檔", NEG, rows)

    if skipped:
        rows = [[(str(s.get("code")), PAD, MUTED, f_row),
                 (str(s.get("name", ""))[:14], PAD + 62, MUTED, f_row),
                 (_clip(s.get("reason", ""), W - PAD * 2 - 260, f_small), PAD + 260, MUTED, f_small)]
                for s in skipped]
        section("今日無進場 — 主要原因", MUTED, rows)

    if holdings:
        rows = [[("代碼", PAD, MUTED, f_small), ("名稱", PAD + 62, MUTED, f_small),
                 ("進場價", PAD + 250, MUTED, f_small), ("現價", PAD + 350, MUTED, f_small),
                 ("暫定損益", PAD + 460, MUTED, f_small), ("%", PAD + 600, MUTED, f_small),
                 ("停損線", PAD + 700, MUTED, f_small)]]
        for hd in holdings:
            rows.append([
                (str(hd["code"]), PAD, ACCENT, f_row),
                (hd.get("name", "")[:12], PAD + 62, FG, f_row),
                (_yen(hd["entry_price"]), PAD + 250, FG, f_row),
                (_yen(hd["last_close"]), PAD + 350, FG, f_row),
                (_yen(hd["unrealized_pnl_jpy"]), PAD + 460, _color(hd["unrealized_pnl_jpy"]), f_row),
                (_pct(hd["unrealized_pnl_pct"]), PAD + 600, _color(hd["unrealized_pnl_jpy"]), f_row),
                (_yen(hd["stop_line"]), PAD + 700, GOLD, f_row),
            ])
        section(f"持倉 {len(holdings)} 檔（暫定收益）", FG, rows)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out
