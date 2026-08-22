"""自動模擬交易服務 — 每日依「三盤口袋名單」下單，三個閥門出場。

零 LLM：全部是 config 裡的數值門檻，決策可完全重現。

出場閥門（2026-08-22 由單一棘輪停損擴充為三條，見
docs/AUTO_TRADE_LOW_TURNOVER_AUDIT.md）：
  1. trailing_stop — 棘輪移動停損（價格）
  2. time_stop     — 進場後 N 根 K 棒仍在成本帶 ±BAND 內盤整
  3. off_list      — 掉出口袋名單超過 N 個日曆日＝進場理由消失

進場的額度檢查放在所有條件之後，滿倉時仍算出「若有空位會買誰」寫進 log 的
`missed`，避免像過去那樣每天只看到「額度已滿」而不知錯過什麼。

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


def jst_today() -> date:
    """交易日以東京時區為準 — Actions runner 是 UTC，直接用 date.today() 會跨日錯位。"""
    from datetime import timezone, timedelta as _td
    return (datetime.now(timezone.utc) + _td(hours=9)).date()


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
    off_list_exit_days: int = config.AUTO_TRADE_OFF_LIST_EXIT_DAYS
    off_list_cooldown_days: int = config.AUTO_TRADE_OFF_LIST_COOLDOWN_DAYS
    time_stop_days: int = config.AUTO_TRADE_TIME_STOP_DAYS
    time_stop_band_pct: float = config.AUTO_TRADE_TIME_STOP_BAND_PCT
    missed_top_n: int = config.AUTO_TRADE_MISSED_TOP_N


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
) -> tuple[list[dict], list[dict], list[dict]]:
    """從口袋名單挑出今天要進場的交易。回傳 (picks, skipped, missed)。

    規則（依序）：
      1. 排序：gate3.drop_pct 由大到小（融資減最多＝籌碼最乾淨）
      2. 已持有同一 code → 跳過（不加碼、不重複）；出場冷卻中同一 code 也跳過
         （停損/時間停損 20 日，訊號失效 5 日 — 由呼叫端算好塞進 last_exit）
      3. 收盤價資料日期距 today > max_price_age_days → 跳過（不用舊價下單）
      4. 收盤價 < min_price_jpy 或 gate2.premium_pct < min_premium_pct → 跳過（錯價/分割防呆）
      5. 股數 = floor(預算 / 成交價 / lot) × lot，不足 1 單位 → 跳過
      6. **最後**才看額度：持倉達 max_open 或當日達 max_new_per_day → 記為 missed

    額度檢查刻意放在最後（2026-08-22）：原本放在迴圈第一個，滿倉後所有候選的 skip
    理由都被短路成「額度已滿」，其他理由永遠看不到，也不知道錯過了什麼 —
    正是這個一個月沒被發現的原因（見 docs/AUTO_TRADE_LOW_TURNOVER_AUDIT.md §6）。

    picks 每筆：{code, name, entry_price, close, shares, cost_jpy, stop_pct, reason}
    skipped 每筆：{code, name, reason}
    missed 每筆：通過所有條件、只差額度的候選（含 rank/drop_pct），供日報顯示。
    """
    cfg = cfg or AutoTradeConfig()
    picks: list[dict] = []
    skipped: list[dict] = []
    missed: list[dict] = []
    slots = max(0, cfg.max_open - open_count)
    remaining_cash = float(cash)

    rows = sorted(
        pocket_rows,
        key=lambda r: (r.get("gate3") or {}).get("drop_pct") or 0.0,
        reverse=True,
    )

    for rank, r in enumerate(rows, start=1):
        code = str(r.get("code", "")).strip()
        name = r.get("name", "") or ""
        if not code:
            continue
        if code in open_codes:
            skipped.append({"code": code, "name": name, "reason": "已持有同一檔"})
            continue
        prev_exit = (last_exit or {}).get(code)
        if prev_exit is not None and today < prev_exit:
            skipped.append({"code": code, "name": name,
                            "reason": f"出場冷卻中（{prev_exit.isoformat()} 前不買回）"})
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

        # ── 條件全過，最後才看額度 ──
        if len(picks) >= cfg.max_new_per_day or slots <= 0:
            why = ("已達單日上限" if len(picks) >= cfg.max_new_per_day
                   else f"持倉已達上限 {cfg.max_open} 檔")
            skipped.append({"code": code, "name": name, "reason": f"額度已滿（{why}）"})
            if len(missed) < cfg.missed_top_n:
                missed.append({"code": code, "name": name, "rank": rank,
                               "drop_pct": drop, "close": close,
                               "would_cost_jpy": round(cost, 2), "reason": why})
            continue

        remaining_cash -= cost
        slots -= 1
        picks.append({
            "code": code, "name": name, "close": close, "entry_price": entry_price,
            "shares": shares, "cost_jpy": round(cost, 2), "stop_pct": cfg.stop_pct,
            "price_date": px_date.isoformat(), "reason": reason,
        })

    return picks, skipped, missed


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
    """推進 → 出場結算 → 依口袋名單進場 → 寫帳本與當日 log。回傳當日 log dict。

    出場有三個閥門，依序評估：
      1. 棘輪移動停損（價格）
      2. 時間停損（進場後 N 根 K 棒仍在成本帶內盤整）
      3. 訊號失效（掉出口袋名單超過 N 個日曆日）— 進場理由消失就該出場
    """
    cfg = cfg or AutoTradeConfig()
    today = as_of or jst_today()
    ledger = ledger_service.get_or_create_bot_ledger()

    # 0) 先拿口袋名單（訊號失效出場要用，所以必須在出場階段之前）
    if pocket_result is None:
        from api.services import pocket_service
        pocket_result = pocket_service.latest_snapshot() or {}
    pocket_rows = pocket_result.get("pocket", []) or []
    pocket_codes = {str(r.get("code", "")).strip() for r in pocket_rows}

    closed_rows: list[dict] = []

    def _settle(t: Trade) -> None:
        """出場後把價金收回現金並記一列 log。"""
        proceeds = (t.exit_price or 0.0) * t.shares
        proceeds *= (1.0 - _bps(cfg.slippage_bps)) * (1.0 - _bps(cfg.fee_bps))
        ledger.cash_jpy += proceeds
        closed_rows.append({
            "code": t.code, "name": t.name, "shares": t.shares,
            "entry_date": t.entry_date.isoformat(), "entry_price": t.entry_price,
            "exit_date": t.exit_date.isoformat() if t.exit_date else None,
            "exit_price": t.exit_price, "exit_reason": t.exit_reason,
            "exit_reason_label": exit_reason_label(t.exit_reason),
            "pnl_jpy": round(t.pnl_jpy or 0.0, 2), "pnl_pct": t.pnl_pct,
            "proceeds_jpy": round(proceeds, 2),
        })

    # 1) 推進既有持倉（棘輪移動停損 + 時間停損），出場的把現金收回來
    advanced = 0
    for t in ledger.trades:
        if t.status != "open":
            continue
        closes = ledger_service.closes_for(t.code)
        if as_of is not None:
            closes = [(d, c) for d, c in closes if d <= today]
        ledger_service.advance_trade(
            t, closes,
            time_stop_days=cfg.time_stop_days,
            time_stop_band_pct=cfg.time_stop_band_pct,
        )
        advanced += 1
        if t.status == "closed":
            _settle(t)

    # 2) 訊號失效出場：掉出口袋名單超過 off_list_exit_days 個日曆日。
    #    防呆：掃描結果為空（EDINET/margin 資料異常、degraded）時完全不評估，
    #    否則一次壞掃描會把整本帳清空。
    off_list_rows: list[dict] = []
    if pocket_rows and cfg.off_list_exit_days:
        for t in ledger.trades:
            if t.status != "open":
                continue
            if t.code in pocket_codes:
                t.last_on_list_date = today
                continue
            if t.last_on_list_date is None:
                # 舊資料/首次評估 → 從今天開始起算，不追溯（避免部署當天整批出場）
                t.last_on_list_date = today
                continue
            off_days = (today - t.last_on_list_date).days
            if off_days < cfg.off_list_exit_days:
                continue
            closes = [(d, c) for d, c in ledger_service.closes_for(t.code) if d <= today]
            if not closes:
                continue
            d, close = closes[-1]
            ledger_service.close_trade(t, d, close, "off_list")
            off_list_rows.append({"code": t.code, "name": t.name, "off_days": off_days})
            _settle(t)

    # 3) 進場：三盤口袋名單
    open_codes = {t.code for t in ledger.trades if t.status == "open"}
    open_count = len(open_codes)
    # code → 冷卻到期日。停損/時間停損＝「這檔沒搞頭」用長冷卻；訊號失效＝進場理由
    # 消失，若重新入榜就是新訊號，用短冷卻即可，否則等於變相封殺重新合格的好標的。
    cooldown_until: dict[str, date] = {}
    for t in ledger.trades:
        if t.status != "closed" or t.exit_date is None:
            continue
        days = (cfg.off_list_cooldown_days if t.exit_reason == "off_list"
                else cfg.reentry_cooldown_days)
        until = t.exit_date + timedelta(days=days)
        if cooldown_until.get(t.code) is None or until > cooldown_until[t.code]:
            cooldown_until[t.code] = until

    picks, skipped, missed = select_new_trades(
        pocket_rows,
        open_codes=open_codes,
        cash=ledger.cash_jpy,
        open_count=open_count,
        today=today,
        price_lookup=make_price_lookup(as_of),
        last_exit=cooldown_until,
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
        # 推進錨點＝進場價那根 K 棒的日期（不是 entry_date），否則進場後第一根會被跳過
        ledger_service.init_trade_stops(trade, date.fromisoformat(p["price_date"]))
        trade.last_on_list_date = today       # 進場當下必在榜
        ledger.trades.append(trade)
        ledger.cash_jpy -= p["cost_jpy"]
        opened_rows.append({**p, "trade_id": trade.id})

    # 4) 當日權益
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
        "off_list_exits": off_list_rows,
        "skipped": skipped[:50],
        "missed": missed,
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
            "missed": lg.get("missed", []),
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
    end = end or jst_today()
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
    as_of = as_of or jst_today()
    eq = compute_equity(ledger, as_of)
    closed = [
        {"code": t.code, "name": t.name,
         "entry_date": t.entry_date.isoformat(), "entry_price": t.entry_price,
         "exit_date": t.exit_date.isoformat() if t.exit_date else None,
         "exit_price": t.exit_price, "shares": t.shares,
         "pnl_jpy": round(t.pnl_jpy or 0.0, 2), "pnl_pct": t.pnl_pct,
         "exit_reason": t.exit_reason,
         "exit_reason_label": exit_reason_label(t.exit_reason)}
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
        "exit_reason_breakdown": _count_by(closed, "exit_reason"),
        "avg_win_jpy": (sum(c["pnl_jpy"] for c in wins) / len(wins)) if wins else 0.0,
        "avg_loss_jpy": (sum(c["pnl_jpy"] for c in closed if c["pnl_jpy"] <= 0)
                         / max(1, len(closed) - len(wins))) if closed else 0.0,
        "closed_trades": closed,
        **eq,
    }


# ── Telegram 日報文字 ───────────────────────────────────────────────────────

EXIT_REASON_LABEL = {
    "trailing_stop": "移動停損",
    "time_stop": "時間停損",
    "off_list": "訊號失效",
    "manual": "手動平倉",
}


def exit_reason_label(reason: Optional[str]) -> str:
    return EXIT_REASON_LABEL.get(reason or "", reason or "")


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = r.get(key) or "unknown"
        out[k] = out.get(k, 0) + 1
    return out


def _drop(m: dict) -> str:
    """missed 列的融資降幅顯示（可能為 None）。"""
    v = m.get("drop_pct")
    return f"{v:.0%}" if v is not None else "—"


def _w(s: str) -> int:
    """字串顯示寬度（東亞全形算 2）— monospace 表格對齊用。"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s: str, width: int, align: str = "left") -> str:
    s = str(s)
    while _w(s) > width:                    # 過長就截斷（全形逐字砍）
        s = s[:-1]
    fill = " " * max(0, width - _w(s))
    return (fill + s) if align == "right" else (s + fill)


def format_report_html(log: dict) -> str:
    """Telegram HTML 版日報（<pre> 等寬表格）。parse_mode=HTML 送出。"""
    yen = lambda v: f"¥{round(v or 0):,}"
    pct = lambda v: f"{(v or 0) * 100:+.2f}%"
    esc = lambda s: (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    out = [f"🤖 <b>自動模擬交易日報 {log.get('date')}</b>", ""]
    kpi = [
        ("總權益", yen(log.get("equity_jpy")), pct(log.get("total_return_pct"))),
        ("已實現", yen(log.get("realized_pnl_jpy")), f"{log.get('closed_count', 0)} 筆"),
        ("未實現", yen(log.get("unrealized_pnl_jpy")), f"{log.get('open_count', 0)} 檔"),
        ("現金", yen(log.get("cash_jpy")), f"市值 {yen(log.get('market_value_jpy'))}"),
    ]
    out.append("<pre>" + "\n".join(
        f"{_pad(k, 8)}{_pad(v, 12, 'right')}  {s}" for k, v, s in kpi) + "</pre>")

    opened = log.get("opened") or []
    closed = log.get("closed") or []
    holdings = sorted(log.get("holdings") or [],
                      key=lambda h: h.get("unrealized_pnl_jpy", 0), reverse=True)

    if opened:
        rows = [f"{_pad('代碼', 6)}{_pad('名稱', 16)}{_pad('股數', 7, 'right')}{_pad('價格', 11, 'right')}"]
        rows += [f"{_pad(o['code'], 6)}{_pad(o.get('name', ''), 16)}"
                 f"{_pad(str(o['shares']), 7, 'right')}{_pad(yen(o['entry_price']), 11, 'right')}"
                 for o in opened]
        out.append(f"🟢 <b>今日進場 {len(opened)} 檔</b>")
        out.append("<pre>" + esc("\n".join(rows)) + "</pre>")
    else:
        out.append("🟢 <b>今日無新進場</b>")
        for s in (log.get("skipped") or [])[:3]:
            out.append(f"　✗ {esc(s.get('code'))} {esc(s.get('name', ''))}：{esc(s.get('reason', ''))}")

    # 額度滿而錯過的合格候選 — 沒有這段就只會天天看到「額度已滿」而不知錯過什麼
    missed = log.get("missed") or []
    if missed:
        rows = [f"{_pad('#', 4)}{_pad('代碼', 6)}{_pad('名稱', 16)}{_pad('融資降', 9, 'right')}"]
        rows += [f"{_pad(str(m.get('rank', '')), 4)}{_pad(m['code'], 6)}"
                 f"{_pad(m.get('name', ''), 16)}{_pad(_drop(m), 9, 'right')}"
                 for m in missed]
        out.append(f"⚠️ <b>額度滿錯過 {len(missed)} 檔合格候選</b>")
        out.append("<pre>" + esc("\n".join(rows)) + "</pre>")

    if closed:
        rows = [f"{_pad('代碼', 6)}{_pad('名稱', 12)}{_pad('損益', 11, 'right')}"
                f"{_pad('%', 8, 'right')}  {_pad('原因', 8)}"]
        rows += [f"{_pad(c['code'], 6)}{_pad(c.get('name', ''), 12)}"
                 f"{_pad(yen(c.get('pnl_jpy')), 11, 'right')}{_pad(pct(c.get('pnl_pct')), 8, 'right')}"
                 f"  {_pad(exit_reason_label(c.get('exit_reason')), 8)}"
                 for c in closed]
        out.append(f"🔴 <b>今日出場 {len(closed)} 檔</b>")
        out.append("<pre>" + esc("\n".join(rows)) + "</pre>")
    else:
        out.append("🔴 <b>今日無出場</b>")

    if holdings:
        rows = [f"{_pad('代碼', 6)}{_pad('名稱', 14)}{_pad('暫定損益', 12, 'right')}{_pad('%', 9, 'right')}"]
        rows += [f"{_pad(h['code'], 6)}{_pad(h.get('name', ''), 14)}"
                 f"{_pad(yen(h['unrealized_pnl_jpy']), 12, 'right')}"
                 f"{_pad(pct(h['unrealized_pnl_pct']), 9, 'right')}"
                 for h in holdings]
        out.append(f"📊 <b>持倉 {len(holdings)} 檔</b>")
        out.append("<pre>" + esc("\n".join(rows)) + "</pre>")

    out.append(f"<i>口袋名單候選 {log.get('pocket_candidates', 0)} 檔</i>")
    return "\n".join(out)


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
        # 沒進場時把前幾個「為什麼沒買」列出來，避免每天看到空報告卻不知原因
        for s in (log.get("skipped") or [])[:5]:
            lines.append(f"　✗ {s.get('code')} {s.get('name','')}：{s.get('reason','')}")
    missed = log.get("missed") or []
    if missed:
        lines.append(f"⚠️ 額度滿錯過 {len(missed)} 檔合格候選")
        for m in missed:
            lines.append(f"　#{m.get('rank','?')} {m['code']} {m.get('name','')}"
                         f"　融資降 {_drop(m)}（{m.get('reason','')}）")
    if closed:
        lines.append(f"🔴 今日出場 {len(closed)} 檔")
        for c in closed:
            lines.append(f"　{c['code']} {c.get('name','')} @¥{c.get('exit_price')}"
                         f"　損益 {yen(c.get('pnl_jpy'))}（{pct(c.get('pnl_pct'))}）"
                         f" {exit_reason_label(c.get('exit_reason'))}")
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
