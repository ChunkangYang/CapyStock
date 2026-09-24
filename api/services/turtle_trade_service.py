"""海龜投資法（Turtle Trading）每日模擬交易服務 — 與舊三盤模型平行、獨立帳本。

零 LLM，全部是 config 裡的數值門檻（`capystock.config` 的 `TURTLE_*`），決策可
完全重現。策略規格與理由見 `docs/TURTLE_STRATEGY.md`；回測見
`scripts/backtest_turtle.py` 與 `docs/TURTLE_BACKTEST_REPORT.md`。

每日流程（`run_daily()`）：
  1. 出場（停損優先於 Donchian 20 日突破出場）
  2. 金字塔加碼（同一檔股票，價格從最近一次進場/加碼價再漲 0.5N，最多 4 個 unit）
  3. 新突破進場（55 日收盤突破，依超出幅度/N 排序，套用每日與總量上限）
  4. 回撤節流（權益跌破歷史高點 20% → 新單位縮手一半；回升到 -10% 以內恢復）
  5. 寫帳本（`data/ledgers/auto-turtle.json`）與當日 log（`data/auto_trade_log_turtle/YYYY-MM-DD.json`）

金字塔加碼在帳本內以「同一 code 多筆 Trade」表示（`unit_index` 標示第幾個 unit），
停損線是「整批」概念：加碼時把該檔所有 open Trade 的 `stop_line` 一起收緊到新值
（只升不降），出場時整批一起關閉。

寫入者：`scripts/run_turtle_trade.py`（供 `.github/workflows/paper-trade-turtle.yml`
排程呼叫）。這是全新、平行的帳本與 log 目錄，不會讀寫舊三盤模型的任何檔案。
"""
from __future__ import annotations

import glob
import json
import math
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from api.deps import DATA_DIR
from api.schemas.ledger import Ledger, Trade
from api.services import ledger_service
from capystock import config, turtle as tt

DAILY_LOG_DIR = DATA_DIR / "auto_trade_log_turtle"


def jst_today() -> date:
    from datetime import timezone, timedelta as _td
    return (datetime.now(timezone.utc) + _td(hours=9)).date()


# ── 參數 ────────────────────────────────────────────────────────────────────

@dataclass
class TurtleConfig:
    n_period: int = config.TURTLE_N_PERIOD
    entry_breakout_days: int = config.TURTLE_ENTRY_BREAKOUT_DAYS
    exit_breakout_days: int = config.TURTLE_EXIT_BREAKOUT_DAYS
    unit_risk_pct: float = config.TURTLE_UNIT_RISK_PCT
    stop_n_mult: float = config.TURTLE_STOP_N_MULT
    pyramid_add_n_mult: float = config.TURTLE_PYRAMID_ADD_N_MULT
    max_units_per_market: int = config.TURTLE_MAX_UNITS_PER_MARKET
    max_total_units: int = config.TURTLE_MAX_TOTAL_UNITS
    max_new_units_per_day: int = config.TURTLE_MAX_NEW_UNITS_PER_DAY
    drawdown_throttle_pct: float = config.TURTLE_DRAWDOWN_THROTTLE_PCT
    drawdown_recover_pct: float = config.TURTLE_DRAWDOWN_RECOVER_PCT
    reentry_cooldown_days: int = config.TURTLE_REENTRY_COOLDOWN_DAYS
    min_price_jpy: float = config.TURTLE_MIN_PRICE_JPY
    max_price_age_days: int = config.TURTLE_MAX_PRICE_AGE_DAYS
    lot_size: int = config.TURTLE_LOT_SIZE
    ledger_id: str = config.TURTLE_LEDGER_ID
    ledger_name: str = config.TURTLE_LEDGER_NAME
    initial_cash_jpy: float = config.TURTLE_INITIAL_CASH_JPY


@dataclass
class TurtleSignal:
    """某代碼在某日的海龜訊號快照（收盤、N、Donchian 上/下軌）。"""
    code: str
    date: date
    close: float
    n: Optional[float]
    dhigh_entry: Optional[float]
    dlow_exit: Optional[float]


# ── 訊號計算（純函式，可單測）────────────────────────────────────────────────

def compute_signal(bars: list, cfg: Optional[TurtleConfig] = None) -> Optional[TurtleSignal]:
    """從一段「日期升冪排序」的 K 線（需有 .date/.high/.low/.close）算出當日訊號。

    `bars` 最後一筆＝「今天」。資料不足（暖身不夠）回傳 None。
    """
    cfg = cfg or TurtleConfig()
    need = max(cfg.entry_breakout_days + 1, cfg.exit_breakout_days + 1, cfg.n_period + 1)
    if len(bars) < need:
        return None

    closes = [float(b.close) for b in bars]
    highs = [float(b.high) for b in bars]
    lows = [float(b.low) for b in bars]

    trs = []
    for i in range(len(bars)):
        prev_close = closes[i - 1] if i > 0 else None
        trs.append(tt.true_range(highs[i], lows[i], prev_close))

    n = tt.n_value(trs, period=cfg.n_period)
    closes_before_today = closes[:-1]
    dhigh_entry = tt.donchian_high(closes_before_today, window=cfg.entry_breakout_days)
    dlow_exit = tt.donchian_low(closes_before_today, window=cfg.exit_breakout_days)

    return TurtleSignal(
        code="", date=bars[-1].date, close=closes[-1],
        n=n, dhigh_entry=dhigh_entry, dlow_exit=dlow_exit,
    )


# ── 部位狀態（帳本內同一 code 的多筆 open Trade 視為一組）────────────────────

def open_trades_by_code(ledger: Ledger) -> dict[str, list[Trade]]:
    out: dict[str, list[Trade]] = {}
    for t in ledger.trades:
        if t.status == "open":
            out.setdefault(t.code, []).append(t)
    return out


def group_stop_line(trades: list[Trade]) -> float:
    """一批 unit 只有一條停損線，理論上全部相同；取 max 以防手動編輯造成不一致。"""
    return max((t.stop_line for t in trades), default=0.0)


def group_last_fill(trades: list[Trade]) -> Trade:
    """最近一次進場/加碼＝unit_index 最大者。"""
    return max(trades, key=lambda t: (t.unit_index or 1))


# ── 出場（純函式）────────────────────────────────────────────────────────────

def evaluate_exit(
    trades: list[Trade], signal: Optional[TurtleSignal],
) -> Optional[str]:
    """回傳出場理由（"turtle_stop" / "turtle_donchian_exit"）或 None（不出場）。

    停損優先於 Donchian 出場；當日無訊號（無資料）不評估、維持持有。
    """
    if signal is None:
        return None
    stop_line = group_stop_line(trades)
    if signal.close < stop_line:
        return "turtle_stop"
    if signal.dlow_exit is not None and signal.close < signal.dlow_exit:
        return "turtle_donchian_exit"
    return None


# ── 金字塔加碼候選（純函式）──────────────────────────────────────────────────

def select_pyramid_adds(
    open_positions: dict[str, list[Trade]],
    signals: dict[str, TurtleSignal],
    *,
    cfg: Optional[TurtleConfig] = None,
) -> list[dict]:
    """從目前持倉找出「今天該加碼」的候選，依 (close-last_fill)/N 由大到小排序。

    每組 dict：{code, close, n, last_fill_price, unit_index(下一個編號)}
    不含額度檢查（額度由 `run_daily` 依序消耗）。
    """
    cfg = cfg or TurtleConfig()
    out = []
    for code, trades in open_positions.items():
        if len(trades) >= cfg.max_units_per_market:
            continue
        sig = signals.get(code)
        if sig is None or sig.n is None:
            continue
        last = group_last_fill(trades)
        if not tt.pyramid_trigger(sig.close, last.entry_price, sig.n,
                                  add_n_mult=cfg.pyramid_add_n_mult):
            continue
        score = (sig.close - last.entry_price) / sig.n
        out.append({
            "code": code, "close": sig.close, "n": sig.n,
            "last_fill_price": last.entry_price,
            "unit_index": (last.unit_index or len(trades)) + 1,
            "score": score,
        })
    out.sort(key=lambda r: r["score"], reverse=True)
    return out


# ── 新突破進場候選（純函式）──────────────────────────────────────────────────

def select_new_entries(
    universe: list[str],
    signals: dict[str, TurtleSignal],
    *,
    held_codes: set[str],
    cooldown_until: dict[str, date],
    today: date,
    cfg: Optional[TurtleConfig] = None,
) -> tuple[list[dict], list[dict]]:
    """回傳 (candidates, skipped)。candidates 依突破強度 (close-dhigh)/N 由大到小排序。

    候選 dict：{code, close, n, score}
    """
    cfg = cfg or TurtleConfig()
    candidates: list[dict] = []
    skipped: list[dict] = []
    for code in universe:
        if code in held_codes:
            continue
        until = cooldown_until.get(code)
        if until is not None and today < until:
            skipped.append({"code": code, "reason": f"再進場冷卻中（{until.isoformat()} 前不進場）"})
            continue
        sig = signals.get(code)
        if sig is None:
            continue
        age = (today - sig.date).days
        if age > cfg.max_price_age_days:
            skipped.append({"code": code, "reason": f"價格資料過舊（{sig.date.isoformat()}）"})
            continue
        if sig.close < cfg.min_price_jpy:
            skipped.append({"code": code, "reason": f"股價過低（¥{sig.close}）"})
            continue
        if sig.n is None or sig.dhigh_entry is None:
            continue
        if sig.close <= sig.dhigh_entry:
            continue
        score = (sig.close - sig.dhigh_entry) / sig.n
        candidates.append({"code": code, "close": sig.close, "n": sig.n, "score": score})
    candidates.sort(key=lambda r: r["score"], reverse=True)
    return candidates, skipped


# ── 資金曲線 / 回撤節流 ──────────────────────────────────────────────────────

def compute_equity(ledger: Ledger, price_lookup: Callable[[str], Optional[tuple]]) -> dict:
    """以目前持倉最新收盤估算帳戶權益（tuple(date, close) 或 None）。"""
    holdings: list[dict] = []
    market_value = 0.0
    unrealized = 0.0
    by_code = open_trades_by_code(ledger)
    for code, trades in by_code.items():
        quote = price_lookup(code)
        for t in trades:
            px = float(quote[1]) if quote else t.entry_price
            mv = px * t.shares
            pnl = (px - t.entry_price) * t.shares
            market_value += mv
            unrealized += pnl
            holdings.append({
                "trade_id": t.id, "code": t.code, "unit_index": t.unit_index,
                "entry_date": t.entry_date.isoformat(), "entry_price": t.entry_price,
                "shares": t.shares, "last_close": round(px, 2),
                "stop_line": round(t.stop_line, 2),
                "unrealized_pnl_jpy": round(pnl, 2),
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
        "open_units": len(holdings),
        "open_codes": len(by_code),
        "closed_count": sum(1 for t in ledger.trades if t.status == "closed"),
        "holdings": holdings,
    }


def next_risk_pct(
    *, throttled: bool, equity: float, peak_equity: float, cfg: Optional[TurtleConfig] = None,
) -> tuple[bool, float]:
    """回撤節流狀態機：回傳 (新的 throttled 狀態, 這次要用的 unit_risk_pct)。"""
    cfg = cfg or TurtleConfig()
    if not throttled and peak_equity > 0 and equity <= peak_equity * (1 - cfg.drawdown_throttle_pct):
        throttled = True
    elif throttled and peak_equity > 0 and equity >= peak_equity * (1 - cfg.drawdown_recover_pct):
        throttled = False
    risk_pct = cfg.unit_risk_pct / 2.0 if throttled else cfg.unit_risk_pct
    return throttled, risk_pct


# ── 全市場代碼清單 / 價格資料 ────────────────────────────────────────────────

def discover_universe() -> list[str]:
    """全市場候選代碼 — 掃 `data/cloud-cache/*_price.csv`（缺檔 fallback `data/cache`）。"""
    codes = set()
    for d in (DATA_DIR / "cloud-cache", DATA_DIR / "cache"):
        if not d.exists():
            continue
        for fp in glob.glob(str(d / "*_price.csv")):
            codes.add(os.path.basename(fp)[: -len("_price.csv")])
    return sorted(codes)


def make_signal_provider(cfg: TurtleConfig, as_of: Optional[date] = None):
    """回傳 code → TurtleSignal（None＝資料不足或無當日資料）的查詢函式，帶快取。"""
    from api.services import signal_service
    cache: dict[str, Optional[TurtleSignal]] = {}

    def provider(code: str) -> Optional[TurtleSignal]:
        if code in cache:
            return cache[code]
        bars = signal_service.get_price_history(code, days=max(120, cfg.entry_breakout_days + 30))
        if as_of is not None:
            bars = [b for b in bars if b.date <= as_of]
        sig = compute_signal(bars, cfg) if bars else None
        if sig is not None:
            sig.code = code
        cache[code] = sig
        return sig

    return provider


def make_price_lookup(as_of: Optional[date] = None):
    from api.services import auto_trade_service as ats
    return ats.make_price_lookup(as_of)


# ── 每日執行 ────────────────────────────────────────────────────────────────

def run_daily(
    *,
    as_of: Optional[date] = None,
    universe: Optional[list[str]] = None,
    signal_provider: Optional[Callable[[str], Optional[TurtleSignal]]] = None,
    dry_run: bool = False,
    cfg: Optional[TurtleConfig] = None,
) -> dict:
    """推進（出場）→ 金字塔加碼 → 新突破進場 → 回撤節流 → 寫帳本與當日 log。"""
    cfg = cfg or TurtleConfig()
    today = as_of or jst_today()
    ledger = ledger_service.get_or_create_bot_ledger(
        cfg.ledger_id, cfg.ledger_name, cfg.initial_cash_jpy)

    universe = universe if universe is not None else discover_universe()
    signal_provider = signal_provider or make_signal_provider(cfg, as_of)

    signals: dict[str, TurtleSignal] = {}
    for code in set(universe) | {t.code for t in ledger.trades if t.status == "open"}:
        sig = signal_provider(code)
        if sig is not None:
            signals[code] = sig

    # ── 1) 出場：停損優先於 Donchian ──
    closed_rows: list[dict] = []
    last_exit_date: dict[str, date] = {}
    for t in ledger.trades:
        if t.status != "closed" or t.exit_date is None:
            continue
        if last_exit_date.get(t.code) is None or t.exit_date > last_exit_date[t.code]:
            last_exit_date[t.code] = t.exit_date

    by_code = open_trades_by_code(ledger)
    for code, trades in by_code.items():
        sig = signals.get(code)
        reason = evaluate_exit(trades, sig)
        if reason is None:
            continue
        exit_price = sig.close
        for t in trades:
            ledger_service.close_trade(t, today, exit_price, reason)
            proceeds = exit_price * t.shares
            ledger.cash_jpy += proceeds
            closed_rows.append({
                "code": t.code, "unit_index": t.unit_index, "shares": t.shares,
                "entry_date": t.entry_date.isoformat(), "entry_price": t.entry_price,
                "exit_date": today.isoformat(), "exit_price": exit_price,
                "exit_reason": reason, "pnl_jpy": round(t.pnl_jpy or 0.0, 2),
                "pnl_pct": t.pnl_pct, "proceeds_jpy": round(proceeds, 2),
            })
        last_exit_date[code] = today

    # ── 2) 金字塔加碼 + 3) 新突破進場：依序消耗每日/總量額度 ──
    open_positions = open_trades_by_code(ledger)  # 出場後重新讀一次（已排除剛出場的）
    held_codes = set(open_positions.keys())
    total_units_open = sum(len(v) for v in open_positions.values())

    pyramid_candidates = select_pyramid_adds(open_positions, signals, cfg=cfg)
    entry_candidates, skipped = select_new_entries(
        universe, signals, held_codes=held_codes, cooldown_until={
            code: d + timedelta(days=cfg.reentry_cooldown_days) for code, d in last_exit_date.items()
        }, today=today, cfg=cfg)

    equity_now = compute_equity(ledger, make_price_lookup(as_of))["equity_jpy"]
    peak_equity = max(equity_now, ledger.initial_cash_jpy)
    throttled, risk_pct = next_risk_pct(
        throttled=False, equity=equity_now, peak_equity=peak_equity, cfg=cfg)

    new_units_today = 0
    opened_rows: list[dict] = []
    missed: list[dict] = []

    for cand in pyramid_candidates:
        if new_units_today >= cfg.max_new_units_per_day or total_units_open >= cfg.max_total_units:
            missed.append({**cand, "action": "pyramid", "reason": "額度已滿"})
            continue
        shares = tt.unit_size(equity_now, cand["n"], unit_risk_pct=risk_pct,
                              lot_size=cfg.lot_size, price=cand["close"], cash=ledger.cash_jpy)
        if shares < cfg.lot_size:
            missed.append({**cand, "action": "pyramid", "reason": "資金不足"})
            continue
        trade = Trade(
            id=str(uuid.uuid4()), code=cand["code"], name="",
            entry_date=today, entry_price=cand["close"], shares=shares,
            stop_pct=0.0, status="open", entry_reason="海龜加碼",
            unit_index=cand["unit_index"], n_at_fill=cand["n"],
        )
        ledger_service.init_trade_stops(trade, today)
        candidate_stop = tt.stop_line_for_unit(cand["close"], cand["n"], stop_n_mult=cfg.stop_n_mult)
        group = open_positions.get(cand["code"], [])
        new_stop = tt.tighten_stop(group_stop_line(group) if group else None, candidate_stop)
        trade.stop_line = new_stop
        for existing in group:
            existing.stop_line = new_stop
        ledger.trades.append(trade)
        ledger.cash_jpy -= shares * cand["close"]
        open_positions.setdefault(cand["code"], []).append(trade)
        total_units_open += 1
        new_units_today += 1
        opened_rows.append({"code": cand["code"], "action": "pyramid", "unit_index": cand["unit_index"],
                            "shares": shares, "entry_price": cand["close"],
                            "cost_jpy": round(shares * cand["close"], 2), "trade_id": trade.id})

    for cand in entry_candidates:
        if new_units_today >= cfg.max_new_units_per_day or total_units_open >= cfg.max_total_units:
            missed.append({**cand, "action": "entry", "reason": "額度已滿"})
            continue
        shares = tt.unit_size(equity_now, cand["n"], unit_risk_pct=risk_pct,
                              lot_size=cfg.lot_size, price=cand["close"], cash=ledger.cash_jpy)
        if shares < cfg.lot_size:
            missed.append({**cand, "action": "entry", "reason": "資金不足"})
            continue
        trade = Trade(
            id=str(uuid.uuid4()), code=cand["code"], name="",
            entry_date=today, entry_price=cand["close"], shares=shares,
            stop_pct=0.0, status="open", entry_reason="海龜 55 日突破",
            unit_index=1, n_at_fill=cand["n"],
        )
        ledger_service.init_trade_stops(trade, today)
        trade.stop_line = tt.stop_line_for_unit(cand["close"], cand["n"], stop_n_mult=cfg.stop_n_mult)
        ledger.trades.append(trade)
        ledger.cash_jpy -= shares * cand["close"]
        open_positions[cand["code"]] = [trade]
        total_units_open += 1
        new_units_today += 1
        opened_rows.append({"code": cand["code"], "action": "entry", "unit_index": 1,
                            "shares": shares, "entry_price": cand["close"],
                            "cost_jpy": round(shares * cand["close"], 2), "trade_id": trade.id})

    equity = compute_equity(ledger, make_price_lookup(as_of))

    log = {
        "date": today.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "params": asdict(cfg),
        "universe_size": len(universe),
        "throttled": throttled,
        "unit_risk_pct_used": risk_pct,
        "opened": opened_rows,
        "closed": closed_rows,
        "missed": missed[:50],
        "skipped": skipped[:50],
        **equity,
    }

    if not dry_run:
        ledger_service.save_ledger(ledger)
        write_daily_log(log)
    return log


# ── 每日 log ────────────────────────────────────────────────────────────────

def daily_log_path(d) -> Path:
    ds = d if isinstance(d, str) else d.isoformat()
    return DAILY_LOG_DIR / f"{ds}.json"


def write_daily_log(log: dict) -> Path:
    DAILY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = daily_log_path(log["date"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    return path


def read_daily_log(d) -> Optional[dict]:
    path = daily_log_path(d)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def latest_log_date() -> Optional[str]:
    """最近一筆 log 的日期字串（無 log 回 None）。供日報腳本找預設日期用。"""
    if not DAILY_LOG_DIR.exists():
        return None
    files = sorted(glob.glob(str(DAILY_LOG_DIR / "*.json")))
    return Path(files[-1]).stem if files else None


# ── Telegram 日報 ───────────────────────────────────────────────────────────
# 標籤固定帶「🐢 海龜模型」，跟舊三盤模型（🤖 三盤模型）的日報並存時一眼能分辨
# 是哪個模型送的（兩本帳本 auto-pocket / auto-turtle 平行跑，互不影響）。

EXIT_REASON_LABEL = {
    "turtle_stop": "停損（2N）",
    "turtle_donchian_exit": "Donchian 出場（20日低）",
    "manual": "手動平倉",
}


def exit_reason_label(reason: Optional[str]) -> str:
    return EXIT_REASON_LABEL.get(reason or "", reason or "")


def _w(s: str) -> int:
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s: str, width: int, align: str = "left") -> str:
    s = str(s)
    while _w(s) > width:
        s = s[:-1]
    fill = " " * max(0, width - _w(s))
    return (fill + s) if align == "right" else (s + fill)


ACTION_LABEL = {"entry": "新倉", "pyramid": "加碼"}


def _score_str(v) -> str:
    return f"{v:.2f}" if isinstance(v, (int, float)) else "—"


def format_report_html(log: dict) -> str:
    """Telegram HTML 版日報（<pre> 等寬表格）。parse_mode=HTML 送出。"""
    yen = lambda v: f"¥{round(v or 0):,}"
    pct = lambda v: f"{(v or 0) * 100:+.2f}%"
    esc = lambda s: (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    out = [f"🐢 <b>海龜模型 自動模擬交易日報 {log.get('date')}</b>", ""]
    if log.get("throttled"):
        out.append(f"⚠️ <b>回撤節流中</b>（unit 風險比例已減半至 {log.get('unit_risk_pct_used', 0):.2%}）")

    kpi = [
        ("總權益", yen(log.get("equity_jpy")), pct(log.get("total_return_pct"))),
        ("已實現", yen(log.get("realized_pnl_jpy")), f"{log.get('closed_count', 0)} unit"),
        ("未實現", yen(log.get("unrealized_pnl_jpy")), f"{log.get('open_units', 0)} unit / {log.get('open_codes', 0)} 檔"),
        ("現金", yen(log.get("cash_jpy")), f"市值 {yen(log.get('market_value_jpy'))}"),
    ]
    out.append("<pre>" + "\n".join(
        f"{_pad(k, 8)}{_pad(v, 12, 'right')}  {s}" for k, v, s in kpi) + "</pre>")

    opened = log.get("opened") or []
    closed = log.get("closed") or []
    holdings = sorted(log.get("holdings") or [],
                      key=lambda h: h.get("unrealized_pnl_jpy", 0), reverse=True)

    if opened:
        rows = [f"{_pad('代碼', 6)}{_pad('動作', 6)}{_pad('unit', 5, 'right')}{_pad('股數', 7, 'right')}{_pad('價格', 11, 'right')}"]
        rows += [f"{_pad(o['code'], 6)}{_pad(ACTION_LABEL.get(o.get('action'), o.get('action', '')), 6)}"
                 f"{_pad(str(o.get('unit_index', '')), 5, 'right')}{_pad(str(o['shares']), 7, 'right')}"
                 f"{_pad(yen(o['entry_price']), 11, 'right')}"
                 for o in opened]
        out.append(f"🟢 <b>今日新增 {len(opened)} unit</b>")
        out.append("<pre>" + esc("\n".join(rows)) + "</pre>")
    else:
        out.append("🟢 <b>今日無新增 unit</b>")

    missed = [m for m in (log.get("missed") or []) if m.get("reason") == "額度已滿"][:5]
    if missed:
        rows = [f"{_pad('代碼', 6)}{_pad('動作', 6)}{_pad('score', 8, 'right')}"]
        rows += [f"{_pad(m['code'], 6)}{_pad(ACTION_LABEL.get(m.get('action'), m.get('action', '')), 6)}"
                 f"{_pad(_score_str(m.get('score')), 8, 'right')}"
                 for m in missed]
        out.append(f"⚠️ <b>額度滿錯過候選（前 5）</b>")
        out.append("<pre>" + esc("\n".join(rows)) + "</pre>")

    if closed:
        rows = [f"{_pad('代碼', 6)}{_pad('損益', 11, 'right')}{_pad('%', 8, 'right')}  {_pad('原因', 14)}"]
        rows += [f"{_pad(c['code'], 6)}{_pad(yen(c.get('pnl_jpy')), 11, 'right')}{_pad(pct(c.get('pnl_pct')), 8, 'right')}"
                 f"  {_pad(exit_reason_label(c.get('exit_reason')), 14)}"
                 for c in closed]
        out.append(f"🔴 <b>今日出場 {len(closed)} unit</b>")
        out.append("<pre>" + esc("\n".join(rows)) + "</pre>")
    else:
        out.append("🔴 <b>今日無出場</b>")

    if holdings:
        rows = [f"{_pad('代碼', 6)}{_pad('unit', 5, 'right')}{_pad('暫定損益', 12, 'right')}{_pad('停損線', 10, 'right')}"]
        rows += [f"{_pad(h['code'], 6)}{_pad(str(h.get('unit_index', '')), 5, 'right')}"
                 f"{_pad(yen(h['unrealized_pnl_jpy']), 12, 'right')}{_pad(yen(h['stop_line']), 10, 'right')}"
                 for h in holdings]
        out.append(f"📊 <b>持倉 {len(holdings)} unit</b>")
        out.append("<pre>" + esc("\n".join(rows)) + "</pre>")

    out.append(f"<i>候選宇宙 {log.get('universe_size', 0)} 檔</i>")
    return "\n".join(out)


def format_report(log: dict) -> str:
    """把當日 log 轉成 Telegram 純文字日報（🐢 海龜模型）。"""
    yen = lambda v: f"¥{round(v or 0):,}"
    pct = lambda v: f"{(v or 0) * 100:+.2f}%"
    lines = [
        f"🐢 CapyStock 海龜模型 自動模擬交易日報 {log.get('date')}",
        "",
    ]
    if log.get("throttled"):
        lines.append(f"⚠️ 回撤節流中（unit 風險比例已減半至 {log.get('unit_risk_pct_used', 0):.2%}）")
    lines += [
        f"總權益 {yen(log.get('equity_jpy'))}（起始 {yen(log.get('initial_cash_jpy'))}，"
        f"報酬 {pct(log.get('total_return_pct'))}）",
        f"現金 {yen(log.get('cash_jpy'))}｜持倉 {log.get('open_units', 0)} unit / {log.get('open_codes', 0)} 檔"
        f" {yen(log.get('market_value_jpy'))}",
        f"已實現 {yen(log.get('realized_pnl_jpy'))}｜未實現 {yen(log.get('unrealized_pnl_jpy'))}",
        "",
    ]
    opened = log.get("opened") or []
    closed = log.get("closed") or []
    if opened:
        lines.append(f"🟢 今日新增 {len(opened)} unit")
        for o in opened:
            lines.append(f"　{o['code']}（{ACTION_LABEL.get(o.get('action'), o.get('action', ''))}"
                         f" unit{o.get('unit_index', '')}）{o['shares']}股@¥{o['entry_price']}")
    else:
        lines.append("🟢 今日無新增 unit")
    if closed:
        lines.append(f"🔴 今日出場 {len(closed)} unit")
        for c in closed:
            lines.append(f"　{c['code']} @¥{c.get('exit_price')}　損益 {yen(c.get('pnl_jpy'))}"
                         f"（{pct(c.get('pnl_pct'))}） {exit_reason_label(c.get('exit_reason'))}")
    else:
        lines.append("🔴 今日無出場")

    holdings = log.get("holdings") or []
    if holdings:
        lines.append("")
        lines.append("📊 持倉暫定損益")
        for h in sorted(holdings, key=lambda x: x.get("unrealized_pnl_jpy", 0), reverse=True):
            lines.append(f"　{h['code']} unit{h.get('unit_index', '')} @¥{h['last_close']}"
                         f"（進 ¥{h['entry_price']}）{yen(h['unrealized_pnl_jpy'])}｜停損 ¥{h['stop_line']}")
    lines.append("")
    lines.append(f"候選宇宙 {log.get('universe_size', 0)} 檔"
                 + ("（DRY RUN，未寫入帳本）" if log.get("dry_run") else ""))
    return "\n".join(lines)
