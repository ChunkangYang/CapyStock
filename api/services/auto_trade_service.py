"""自動模擬交易服務 — 每日依「三盤口袋名單」下單、依棘輪移動停損出場。

零 LLM：全部是 config 裡的數值門檻，決策可完全重現。

寫入者只有一個：GitHub Actions 的 paper-trade.yml（或本地手動 `POST /auto-trade/run`）。
本地排程 `ledger_service.advance_all()` 預設跳過 owner="bot" 的帳本，避免雙寫衝突。

產出：
  - `data/ledgers/auto-pocket.json`：帳本本體（現金 + 每筆交易 + 出場結算）
  - `data/auto_trade_log/YYYY-MM-DD.json`：當日決策 log（買了什麼、為何沒買、當日權益）
"""
from __future__ import annotations

import glob
import json
import logging
import math
import os
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from api.deps import DATA_DIR
from api.schemas.ledger import Ledger, Trade
from api.services import ledger_service
from capystock import config

logger = logging.getLogger(__name__)

DAILY_LOG_DIR = DATA_DIR / "auto_trade_log"


# ── 參數 ────────────────────────────────────────────────────────────────────

@dataclass
class AutoTradeConfig:
    position_jpy: float = config.AUTO_TRADE_POSITION_JPY
    max_open: int = config.AUTO_TRADE_MAX_OPEN
    max_new_per_day: int = config.AUTO_TRADE_MAX_NEW_PER_DAY
    stop_pct: float = config.AUTO_TRADE_STOP_PCT
    lot_size: int = config.AUTO_TRADE_LOT_SIZE
    fee_bps: float = config.AUTO_TRADE_FEE_BPS
    slippage_bps: float = config.AUTO_TRADE_SLIPPAGE_BPS
    max_price_age_days: int = config.AUTO_TRADE_MAX_PRICE_AGE_DAYS
    min_premium_pct: float = config.AUTO_TRADE_MIN_PREMIUM_PCT
    min_price_jpy: float = config.AUTO_TRADE_MIN_PRICE_JPY
    reentry_cooldown_days: int = config.AUTO_TRADE_REENTRY_COOLDOWN_DAYS


def _bps(v: float) -> float:
    return float(v) / 10_000.0


# ── 選股（純函式，可單測）──────────────────────────────────────────────────

def select_new_trades(
    pocket_rows: list[dict],
    *,
    open_codes: set[str],
    cash: float,
    open_count: int,
    today: date,
    price_lookup: Callable[[str], Optional[tuple[date, float]]],
    last_exit: Optional[dict[str, date]] = None,
    cfg: Optional[AutoTradeConfig] = None,
) -> tuple[list[dict], list[dict]]:
    """從口袋名單挑出今天要進場的交易。回傳 (picks, skipped)。

    規則（依序）：
      1. 排序：gate3.drop_pct 由大到小（融資減最多＝籌碼最乾淨）
      2. 已持有同一 code → 跳過（不加碼、不重複）；停損出場後 reentry_cooldown_days
         日內同一 code 也跳過（口袋名單條件是週頻的，隔天就買回會被同一段跌勢反覆巴）
      3. 收盤價資料日期距 today > max_price_age_days → 跳過（不用舊價下單）
      4. 收盤價 < min_price_jpy 或 gate2.premium_pct < min_premium_pct → 跳過（錯價/分割防呆）
      5. 股數 = floor(position_jpy / 成交價 / lot) × lot，不足 1 單位 → 跳過
      6. 現金不足 → 跳過；持倉檔數達 max_open 或當日達 max_new_per_day → 停止

    picks 每筆：{code, name, entry_price, close, shares, cost_jpy, stop_pct, reason}
    skipped 每筆：{code, name, reason}
    """
    cfg = cfg or AutoTradeConfig()
    picks: list[dict] = []
    skipped: list[dict] = []
    slots = max(0, cfg.max_open - open_count)
    remaining_cash = float(cash)

    rows = sorted(
        pocket_rows,
        key=lambda r: (r.get("gate3") or {}).get("drop_pct") or 0.0,
        reverse=True,
    )

    for r in rows:
        code = str(r.get("code", "")).strip()
        name = r.get("name", "") or ""
        if not code:
            continue
        if len(picks) >= cfg.max_new_per_day or slots <= 0:
            skipped.append({"code": code, "name": name, "reason": "額度已滿（單日上限或持倉上限）"})
            continue
        if code in open_codes:
            skipped.append({"code": code, "name": name, "reason": "已持有同一檔"})
            continue
        prev_exit = (last_exit or {}).get(code)
        if prev_exit is not None and (today - prev_exit).days < cfg.reentry_cooldown_days:
            skipped.append({"code": code, "name": name,
                            "reason": f"停損冷卻中（{prev_exit.isoformat()} 出場，"
                                      f"{cfg.reentry_cooldown_days} 日內不買回）"})
            continue

        quote = price_lookup(code)
        if quote is None:
            skipped.append({"code": code, "name": name, "reason": "無收盤價資料"})
            continue
        px_date, close = quote
        age = (today - px_date).days
        if age > cfg.max_price_age_days:
            skipped.append({"code": code, "name": name,
                            "reason": f"價格資料過舊（{px_date.isoformat()}，{age} 日前）"})
            continue
        if close < cfg.min_price_jpy:
            skipped.append({"code": code, "name": name, "reason": f"股價過低（¥{close}）"})
            continue
        premium = (r.get("gate2") or {}).get("premium_pct")
        if premium is not None and premium < cfg.min_premium_pct:
            skipped.append({"code": code, "name": name,
                            "reason": f"折價異常 {premium:.1%}（疑似分割/錯價）"})
            continue

        entry_price = round(close * (1.0 + _bps(cfg.slippage_bps)), 2)
        # 預算＝每筆固定金額，但不超過剩餘現金（尾盤資金不足時買得起多少買多少）
        budget = min(cfg.position_jpy, remaining_cash / (1.0 + _bps(cfg.fee_bps)))
        shares = int(math.floor(budget / entry_price / cfg.lot_size) * cfg.lot_size)
        if shares < cfg.lot_size:
            reason = ("現金不足（買不起 1 單位）" if budget < cfg.position_jpy
                      else f"每筆金額不足 1 單位（{cfg.lot_size} 股 × ¥{entry_price}）")
            skipped.append({"code": code, "name": name, "reason": reason})
            continue
        cost = entry_price * shares * (1.0 + _bps(cfg.fee_bps))

        drop = (r.get("gate3") or {}).get("drop_pct")
        filer = (r.get("gate1") or {}).get("lead_filer") or "?"
        reason = (f"三盤全過｜申報人 {filer}×{(r.get('gate1') or {}).get('filing_count')}"
                  f"｜溢價 {premium:.1%}" if premium is not None else "三盤全過")
        if drop is not None:
            reason += f"｜融資降 {drop:.0%}"

        remaining_cash -= cost
        slots -= 1
        picks.append({
            "code": code, "name": name, "close": close, "entry_price": entry_price,
            "shares": shares, "cost_jpy": round(cost, 2), "stop_pct": cfg.stop_pct,
            "price_date": px_date.isoformat(), "reason": reason,
        })

    return picks, skipped


# ── 價格存取 ────────────────────────────────────────────────────────────────

def _closes_map(code: str, days: int = 420) -> dict[date, float]:
    return dict(ledger_service.closes_for(code, days=days))


def make_price_lookup(as_of: Optional[date] = None) -> Callable[[str], Optional[tuple[date, float]]]:
    """回傳 code → (最後收盤日, 收盤價)；as_of 有值時只看 <= as_of 的收盤（重放用）。"""
    cache: dict[str, Optional[tuple[date, float]]] = {}

    def lookup(code: str) -> Optional[tuple[date, float]]:
        if code in cache:
            return cache[code]
        closes = ledger_service.closes_for(code, days=420)
        if as_of is not None:
            closes = [(d, c) for d, c in closes if d <= as_of]
        cache[code] = (closes[-1][0], float(closes[-1][1])) if closes else None
        return cache[code]

    return lookup


# ── 每日執行 ────────────────────────────────────────────────────────────────

def run_daily(
    *,
    as_of: Optional[date] = None,
    pocket_result: Optional[dict] = None,
    dry_run: bool = False,
    cfg: Optional[AutoTradeConfig] = None,
) -> dict:
    """推進 → 出場結算 → 依口袋名單進場 → 寫帳本與當日 log。回傳當日 log dict。"""
    cfg = cfg or AutoTradeConfig()
    today = as_of or date.today()
    ledger = ledger_service.get_or_create_bot_ledger()

    # 1) 推進既有持倉（棘輪移動停損），出場的把現金收回來
    closed_rows: list[dict] = []
    advanced = 0
    for t in ledger.trades:
        if t.status != "open":
            continue
        closes = ledger_service.closes_for(t.code)
        if as_of is not None:
            closes = [(d, c) for d, c in closes if d <= today]
        before = t.status
        ledger_service.advance_trade(t, closes)
        advanced += 1
        if before == "open" and t.status == "closed":
            proceeds = (t.exit_price or 0.0) * t.shares
            proceeds *= (1.0 - _bps(cfg.slippage_bps)) * (1.0 - _bps(cfg.fee_bps))
            ledger.cash_jpy += proceeds
            closed_rows.append({
                "code": t.code, "name": t.name, "shares": t.shares,
                "entry_date": t.entry_date.isoformat(), "entry_price": t.entry_price,
                "exit_date": t.exit_date.isoformat() if t.exit_date else None,
                "exit_price": t.exit_price, "exit_reason": t.exit_reason,
                "pnl_jpy": round(t.pnl_jpy or 0.0, 2), "pnl_pct": t.pnl_pct,
                "proceeds_jpy": round(proceeds, 2),
            })

    # 2) 進場：三盤口袋名單
    if pocket_result is None:
        from api.services import pocket_service
        pocket_result = pocket_service.latest_snapshot() or {}
    pocket_rows = pocket_result.get("pocket", []) or []

    open_codes = {t.code for t in ledger.trades if t.status == "open"}
    open_count = len(open_codes)
    last_exit: dict[str, date] = {}
    for t in ledger.trades:
        if t.status == "closed" and t.exit_date is not None:
            prev = last_exit.get(t.code)
            if prev is None or t.exit_date > prev:
                last_exit[t.code] = t.exit_date
    picks, skipped = select_new_trades(
        pocket_rows,
        open_codes=open_codes,
        cash=ledger.cash_jpy,
        open_count=open_count,
        today=today,
        price_lookup=make_price_lookup(as_of),
        last_exit=last_exit,
        cfg=cfg,
    )

    opened_rows: list[dict] = []
    for p in picks:
        import uuid
        trade = Trade(
            id=str(uuid.uuid4()),
            code=p["code"], name=p["name"],
            entry_date=today, entry_price=p["entry_price"], shares=p["shares"],
            stop_pct=p["stop_pct"], status="open", entry_reason=p["reason"],
        )
        ledger_service.init_trade_stops(trade)
        ledger.trades.append(trade)
        ledger.cash_jpy -= p["cost_jpy"]
        opened_rows.append({**p, "trade_id": trade.id})

    # 3) 當日權益
    equity = compute_equity(ledger, today)

    log = {
        "date": today.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "params": asdict(cfg),
        "pocket_candidates": len(pocket_rows),
        "advanced_trades": advanced,
        "opened": opened_rows,
        "closed": closed_rows,
        "skipped": skipped[:50],
        **equity,
    }

    if not dry_run:
        ledger_service.save_ledger(ledger)
        write_daily_log(log)
    return log


def compute_equity(ledger: Ledger, as_of: date) -> dict:
    """以 as_of（含）為止的最後收盤估算帳戶權益。"""
    holdings: list[dict] = []
    market_value = 0.0
    unrealized = 0.0
    for t in ledger.trades:
        if t.status != "open":
            continue
        closes = [(d, c) for d, c in ledger_service.closes_for(t.code) if d <= as_of]
        last = closes[-1] if closes else None
        px = float(last[1]) if last else t.entry_price
        mv = px * t.shares
        pnl = (px - t.entry_price) * t.shares
        market_value += mv
        unrealized += pnl
        holdings.append({
            "trade_id": t.id, "code": t.code, "name": t.name,
            "entry_date": t.entry_date.isoformat(), "entry_price": t.entry_price,
            "shares": t.shares, "last_close": round(px, 2),
            "last_close_date": last[0].isoformat() if last else None,
            "stop_line": round(t.stop_line, 2), "high_water": round(t.high_water, 2),
            "market_value_jpy": round(mv, 2),
            "unrealized_pnl_jpy": round(pnl, 2),
            "unrealized_pnl_pct": (px - t.entry_price) / t.entry_price if t.entry_price else 0.0,
        })
    realized = sum((t.pnl_jpy or 0.0) for t in ledger.trades if t.status == "closed")
    equity = ledger.cash_jpy + market_value
    initial = ledger.initial_cash_jpy or 0.0
    return {
        "cash_jpy": round(ledger.cash_jpy, 2),
        "market_value_jpy": round(market_value, 2),
        "equity_jpy": round(equity, 2),
        "initial_cash_jpy": initial,
        "realized_pnl_jpy": round(realized, 2),
        "unrealized_pnl_jpy": round(unrealized, 2),
        "total_return_pct": (equity - initial) / initial if initial else 0.0,
        "open_count": len(holdings),
        "closed_count": sum(1 for t in ledger.trades if t.status == "closed"),
        "holdings": holdings,
    }


# ── 每日 log ────────────────────────────────────────────────────────────────

def daily_log_path(d: date | str) -> Path:
    ds = d if isinstance(d, str) else d.isoformat()
    return DAILY_LOG_DIR / f"{ds}.json"


def write_daily_log(log: dict) -> Path:
    DAILY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = daily_log_path(log["date"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    return path


def read_daily_log(d: date | str) -> Optional[dict]:
    path = daily_log_path(d)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_daily_logs(days: int = 30) -> list[dict]:
    """最近 N 個交易日的 log（新到舊），holdings/skipped 已裁剪成摘要。"""
    DAILY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(glob.glob(str(DAILY_LOG_DIR / "*.json")))[-days:]
    out: list[dict] = []
    for fp in reversed(files):
        try:
            with open(fp, encoding="utf-8") as f:
                lg = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        out.append({
            "date": lg.get("date"),
            "equity_jpy": lg.get("equity_jpy"),
            "cash_jpy": lg.get("cash_jpy"),
            "realized_pnl_jpy": lg.get("realized_pnl_jpy"),
            "unrealized_pnl_jpy": lg.get("unrealized_pnl_jpy"),
            "total_return_pct": lg.get("total_return_pct"),
            "open_count": lg.get("open_count"),
            "opened": [{"code": o["code"], "name": o.get("name", ""), "shares": o["shares"],
                        "entry_price": o["entry_price"], "reason": o.get("reason", "")}
                       for o in lg.get("opened", [])],
            "closed": [{"code": c["code"], "name": c.get("name", ""),
                        "pnl_jpy": c.get("pnl_jpy"), "pnl_pct": c.get("pnl_pct"),
                        "exit_price": c.get("exit_price"), "exit_reason": c.get("exit_reason")}
                       for c in lg.get("closed", [])],
            "pocket_candidates": lg.get("pocket_candidates"),
        })
    return out


# ── 資金曲線（由帳本 + 價格 CSV 決定性重算，不依賴 log）────────────────────

def build_equity_curve(ledger: Optional[Ledger] = None, end: Optional[date] = None) -> dict:
    """從第一筆交易日到今天的日曆軸權益曲線。

    某日 equity = 當日現金 + 持倉市值（用 <= 當日的最後收盤；非交易日沿用前一收盤）。
    現金 = 起始資金 − 已發生的進場成本 + 已發生的出場價金。
    """
    ledger = ledger or ledger_service.get_or_create_bot_ledger()
    end = end or date.today()
    trades = ledger.trades
    if not trades:
        return {"dates": [], "equity": [], "cash": [], "market_value": [],
                "realized": [], "initial_cash_jpy": ledger.initial_cash_jpy,
                "start": None, "end": end.isoformat()}

    start = min(t.entry_date for t in trades)
    closes_by_code = {t.code: _closes_map(t.code) for t in {tr.code: tr for tr in trades}.values()}

    dates: list[str] = []
    equity_s: list[float] = []
    cash_s: list[float] = []
    mv_s: list[float] = []
    realized_s: list[float] = []

    last_px: dict[str, float] = {}
    d = start
    one = timedelta(days=1)
    while d <= end:
        cash = ledger.initial_cash_jpy
        mv = 0.0
        realized = 0.0
        for t in trades:
            if t.entry_date > d:
                continue
            cash -= t.entry_price * t.shares
            closed_before = t.status == "closed" and t.exit_date is not None and t.exit_date <= d
            if closed_before:
                cash += (t.exit_price or 0.0) * t.shares
                realized += t.pnl_jpy or 0.0
            else:
                px = closes_by_code.get(t.code, {}).get(d)
                if px is None:
                    px = last_px.get(t.code, t.entry_price)
                else:
                    last_px[t.code] = px
                mv += px * t.shares
        dates.append(d.isoformat())
        cash_s.append(round(cash, 2))
        mv_s.append(round(mv, 2))
        equity_s.append(round(cash + mv, 2))
        realized_s.append(round(realized, 2))
        d += one

    return {
        "dates": dates, "equity": equity_s, "cash": cash_s,
        "market_value": mv_s, "realized": realized_s,
        "initial_cash_jpy": ledger.initial_cash_jpy,
        "start": start.isoformat(), "end": end.isoformat(),
    }


def summary(as_of: Optional[date] = None) -> dict:
    """帳戶總覽（現金/市值/已實現/未實現/持倉明細）+ 最新一筆 log 日期。"""
    ledger = ledger_service.get_or_create_bot_ledger()
    as_of = as_of or date.today()
    eq = compute_equity(ledger, as_of)
    closed = [
        {"code": t.code, "name": t.name,
         "entry_date": t.entry_date.isoformat(), "entry_price": t.entry_price,
         "exit_date": t.exit_date.isoformat() if t.exit_date else None,
         "exit_price": t.exit_price, "shares": t.shares,
         "pnl_jpy": round(t.pnl_jpy or 0.0, 2), "pnl_pct": t.pnl_pct,
         "exit_reason": t.exit_reason}
        for t in ledger.trades if t.status == "closed"
    ]
    closed.sort(key=lambda r: r["exit_date"] or "", reverse=True)
    wins = [c for c in closed if (c["pnl_jpy"] or 0) > 0]
    logs = sorted(os.path.basename(p)[:-5] for p in glob.glob(str(DAILY_LOG_DIR / "*.json"))) \
        if DAILY_LOG_DIR.exists() else []
    return {
        "ledger_id": ledger.id, "ledger_name": ledger.name,
        "as_of": as_of.isoformat(),
        "last_log_date": logs[-1] if logs else None,
        "log_count": len(logs),
        "win_rate": (len(wins) / len(closed)) if closed else None,
        "avg_win_jpy": (sum(c["pnl_jpy"] for c in wins) / len(wins)) if wins else 0.0,
        "avg_loss_jpy": (sum(c["pnl_jpy"] for c in closed if c["pnl_jpy"] <= 0)
                         / max(1, len(closed) - len(wins))) if closed else 0.0,
        "closed_trades": closed,
        **eq,
    }


# ── Telegram 日報文字 ───────────────────────────────────────────────────────

def format_report(log: dict) -> str:
    """把當日 log 轉成 Telegram 純文字日報。"""
    yen = lambda v: f"¥{round(v or 0):,}"
    pct = lambda v: f"{(v or 0) * 100:+.2f}%"
    lines = [
        f"🤖 CapyStock 自動模擬交易日報 {log.get('date')}",
        "",
        f"總權益 {yen(log.get('equity_jpy'))}（起始 {yen(log.get('initial_cash_jpy'))}，"
        f"報酬 {pct(log.get('total_return_pct'))}）",
        f"現金 {yen(log.get('cash_jpy'))}｜持倉 {log.get('open_count', 0)} 檔 "
        f"{yen(log.get('market_value_jpy'))}",
        f"已實現 {yen(log.get('realized_pnl_jpy'))}｜未實現 {yen(log.get('unrealized_pnl_jpy'))}",
    ]
    opened = log.get("opened") or []
    closed = log.get("closed") or []
    lines.append("")
    if opened:
        lines.append(f"🟢 今日進場 {len(opened)} 檔")
        for o in opened:
            lines.append(f"　{o['code']} {o.get('name','')} {o['shares']}股 @¥{o['entry_price']}"
                         f"　{o.get('reason','')}")
    else:
        lines.append("🟢 今日無新進場")
    if closed:
        lines.append(f"🔴 今日出場 {len(closed)} 檔")
        for c in closed:
            lines.append(f"　{c['code']} {c.get('name','')} @¥{c.get('exit_price')}"
                         f"　損益 {yen(c.get('pnl_jpy'))}（{pct(c.get('pnl_pct'))}）"
                         f" {c.get('exit_reason','')}")
    else:
        lines.append("🔴 今日無出場")

    holdings = log.get("holdings") or []
    if holdings:
        lines.append("")
        lines.append("📊 持倉暫定損益")
        for h in sorted(holdings, key=lambda x: x.get("unrealized_pnl_jpy", 0), reverse=True):
            lines.append(f"　{h['code']} {h.get('name','')} @¥{h['last_close']}"
                         f"（進 ¥{h['entry_price']}）{yen(h['unrealized_pnl_jpy'])}"
                         f" {pct(h['unrealized_pnl_pct'])}｜停損 ¥{h['stop_line']}")
    lines.append("")
    lines.append(f"口袋名單候選 {log.get('pocket_candidates', 0)} 檔"
                 + ("（DRY RUN，未寫入帳本）" if log.get("dry_run") else ""))
    return "\n".join(lines)
