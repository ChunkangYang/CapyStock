#!/usr/bin/env python
"""海龜投資法（Turtle Trading）全歷史回測 — 逐日事件驅動模擬。

讀取 `data/cloud-cache/*_price.csv`（缺檔 fallback `data/cache/`），對全市場所有
代碼（暖身資料 >=60 列）做 System 2（55 日突破）逐日模擬：

  每日：算全部代碼的 N/Donchian → 先出場（停損優先於 Donchian）→ 金字塔加碼
        → 掃描新突破進場（依超出幅度/N 排序，套用每日與總量上限）→ 記錄當日權益

輸出：
  - docs/EVIDENCES/turtle_backtest_2026-09-24.json：逐筆交易 + 逐日權益曲線 + 彙總指標
  - docs/TURTLE_BACKTEST_REPORT.md：人類可讀報告，含與舊三盤模型的比較

用法：
  python scripts/backtest_turtle.py
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capystock import config, turtle as tt  # noqa: E402

CLOUD_CACHE = PROJECT_ROOT / "data" / "cloud-cache"
LOCAL_CACHE = PROJECT_ROOT / "data" / "cache"
EVIDENCES_DIR = PROJECT_ROOT / "docs" / "EVIDENCES"
REPORT_PATH = PROJECT_ROOT / "docs" / "TURTLE_BACKTEST_REPORT.md"
BACKTEST_JSON_PATH = EVIDENCES_DIR / "turtle_backtest_2026-09-24.json"

MIN_ROWS = 60
WARMUP_TRADING_DAYS = 60


# ── 資料載入 ─────────────────────────────────────────────────────────────

def _price_file_for(code: str) -> Optional[Path]:
    cloud = CLOUD_CACHE / f"{code}_price.csv"
    if cloud.exists():
        return cloud
    local = LOCAL_CACHE / f"{code}_price.csv"
    if local.exists():
        return local
    return None


def discover_codes() -> list[str]:
    codes = set()
    for pattern_dir in (CLOUD_CACHE, LOCAL_CACHE):
        if not pattern_dir.exists():
            continue
        for fp in glob.glob(str(pattern_dir / "*_price.csv")):
            codes.add(os.path.basename(fp)[: -len("_price.csv")])
    return sorted(codes)


@dataclass
class CodeSeries:
    """單一代碼的預先算好逐日序列，dict[date] → row，方便 O(1) 查每日資料。"""
    code: str
    rows: dict  # date -> dict(close, high, low, n, dhigh_entry, dlow_exit)
    dates: list  # 排序後的日期 list


def load_code_series(code: str) -> Optional[CodeSeries]:
    fp = _price_file_for(code)
    if fp is None:
        return None
    try:
        df = pd.read_csv(fp, usecols=["date", "high", "low", "close"], parse_dates=["date"])
    except (ValueError, OSError):
        return None
    df = df.dropna(subset=["date", "high", "low", "close"]).sort_values("date")
    df = df.drop_duplicates(subset="date", keep="last")
    if len(df) < MIN_ROWS:
        return None

    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    tr.iloc[0] = df["high"].iloc[0] - df["low"].iloc[0]

    n = tr.rolling(config.TURTLE_N_PERIOD, min_periods=config.TURTLE_N_PERIOD).mean()
    dhigh_entry = (df["close"].shift(1)
                   .rolling(config.TURTLE_ENTRY_BREAKOUT_DAYS,
                            min_periods=config.TURTLE_ENTRY_BREAKOUT_DAYS).max())
    dlow_exit = (df["close"].shift(1)
                 .rolling(config.TURTLE_EXIT_BREAKOUT_DAYS,
                          min_periods=config.TURTLE_EXIT_BREAKOUT_DAYS).min())

    rows = {}
    dates = []
    for i, d in enumerate(df["date"]):
        dd = d.date()
        dates.append(dd)
        rows[dd] = {
            "close": float(df["close"].iloc[i]),
            "high": float(df["high"].iloc[i]),
            "low": float(df["low"].iloc[i]),
            "n": None if pd.isna(n.iloc[i]) else float(n.iloc[i]),
            "dhigh_entry": None if pd.isna(dhigh_entry.iloc[i]) else float(dhigh_entry.iloc[i]),
            "dlow_exit": None if pd.isna(dlow_exit.iloc[i]) else float(dlow_exit.iloc[i]),
        }
    return CodeSeries(code=code, rows=rows, dates=dates)


# ── 帳本狀態 ─────────────────────────────────────────────────────────────

@dataclass
class Unit:
    fill_date: date
    fill_price: float
    shares: int
    n_at_fill: float


@dataclass
class Position:
    code: str
    units: list = field(default_factory=list)
    stop_line: float = 0.0
    last_fill_price: float = 0.0

    @property
    def total_shares(self) -> int:
        return sum(u.shares for u in self.units)

    @property
    def cost_basis(self) -> float:
        return sum(u.shares * u.fill_price for u in self.units)

    @property
    def entry_date(self) -> date:
        return self.units[0].fill_date


@dataclass
class ClosedTrade:
    code: str
    entry_date: str
    exit_date: str
    units: int
    shares: int
    cost_basis_jpy: float
    exit_price: float
    proceeds_jpy: float
    pnl_jpy: float
    pnl_pct: float
    exit_reason: str
    holding_days: int


def run_backtest() -> dict:
    codes = discover_codes()
    print(f"[load] 發現 {len(codes)} 檔代碼，讀取並預先計算 N/Donchian ...")
    t0 = time.time()
    series_by_code: dict[str, CodeSeries] = {}
    for code in codes:
        cs = load_code_series(code)
        if cs is not None:
            series_by_code[code] = cs
    print(f"[load] {len(series_by_code)} 檔資料量足夠（>= {MIN_ROWS} 列），"
          f"耗時 {time.time() - t0:.1f}s")

    # 全市場日曆軸：所有代碼交易日聯集
    all_dates: set = set()
    for cs in series_by_code.values():
        all_dates.update(cs.dates)
    calendar = sorted(all_dates)
    if len(calendar) <= WARMUP_TRADING_DAYS:
        raise SystemExit("資料量不足以跑過暖身期")
    sim_dates = calendar[WARMUP_TRADING_DAYS:]
    print(f"[calendar] 全市場日曆軸 {len(calendar)} 個交易日，"
          f"回測區間 {sim_dates[0]} ~ {sim_dates[-1]}（{len(sim_dates)} 日）")

    cash = float(config.TURTLE_INITIAL_CASH_JPY)
    positions: dict[str, Position] = {}
    last_exit_date: dict[str, date] = {}
    last_known_close: dict[str, float] = {}
    peak_equity = cash
    throttled = False
    closed_trades: list[ClosedTrade] = []
    equity_curve: list[dict] = []
    concurrent_units_daily: list[int] = []
    market_value_ratio_daily: list[float] = []

    total_units_open = 0

    def current_risk_pct() -> float:
        return config.TURTLE_UNIT_RISK_PCT / 2.0 if throttled else config.TURTLE_UNIT_RISK_PCT

    for d in sim_dates:
        # ── 1) 出場：停損優先於 Donchian ──
        for code in list(positions.keys()):
            cs = series_by_code.get(code)
            row = cs.rows.get(d) if cs else None
            if row is None:
                continue  # 當日無資料（非交易日/暫停），沿用既有部位，不評估出場
            close = row["close"]
            last_known_close[code] = close
            pos = positions[code]
            exit_reason = None
            if close < pos.stop_line:
                exit_reason = "turtle_stop"
            elif row["dlow_exit"] is not None and close < row["dlow_exit"]:
                exit_reason = "turtle_donchian_exit"
            if exit_reason:
                shares = pos.total_shares
                proceeds = close * shares
                cost_basis = pos.cost_basis
                cash += proceeds
                total_units_open -= len(pos.units)
                closed_trades.append(ClosedTrade(
                    code=code, entry_date=pos.entry_date.isoformat(),
                    exit_date=d.isoformat(), units=len(pos.units), shares=shares,
                    cost_basis_jpy=round(cost_basis, 2), exit_price=close,
                    proceeds_jpy=round(proceeds, 2),
                    pnl_jpy=round(proceeds - cost_basis, 2),
                    pnl_pct=(proceeds - cost_basis) / cost_basis if cost_basis else 0.0,
                    exit_reason=exit_reason,
                    holding_days=(d - pos.entry_date).days,
                ))
                del positions[code]
                last_exit_date[code] = d

        # ── 2) 金字塔加碼候選 ──
        pyramid_candidates = []
        for code, pos in positions.items():
            cs = series_by_code.get(code)
            row = cs.rows.get(d) if cs else None
            if row is None or row["n"] is None:
                continue
            close = row["close"]
            if len(pos.units) >= config.TURTLE_MAX_UNITS_PER_MARKET:
                continue
            if not tt.pyramid_trigger(close, pos.last_fill_price, row["n"],
                                       add_n_mult=config.TURTLE_PYRAMID_ADD_N_MULT):
                continue
            score = (close - pos.last_fill_price) / row["n"]
            pyramid_candidates.append((score, code, close, row["n"]))
        pyramid_candidates.sort(key=lambda x: x[0], reverse=True)

        # ── 3) 新突破進場候選 ──
        entry_candidates = []
        for code, cs in series_by_code.items():
            if code in positions:
                continue
            row = cs.rows.get(d)
            if row is None or row["n"] is None or row["dhigh_entry"] is None:
                continue
            close = row["close"]
            if close < config.TURTLE_MIN_PRICE_JPY:
                continue
            if close <= row["dhigh_entry"]:
                continue
            cooldown_end = last_exit_date.get(code)
            if cooldown_end is not None and (d - cooldown_end).days < config.TURTLE_REENTRY_COOLDOWN_DAYS:
                continue
            score = (close - row["dhigh_entry"]) / row["n"]
            entry_candidates.append((score, code, close, row["n"]))
        entry_candidates.sort(key=lambda x: x[0], reverse=True)

        # ── 4) 依額度執行加碼與新進場（加碼優先） ──
        new_units_today = 0
        missed_today: list[dict] = []
        risk_pct = current_risk_pct()

        for score, code, close, n in pyramid_candidates:
            if new_units_today >= config.TURTLE_MAX_NEW_UNITS_PER_DAY or \
               total_units_open >= config.TURTLE_MAX_TOTAL_UNITS:
                missed_today.append({"code": code, "action": "pyramid", "score": round(score, 3)})
                continue
            shares = tt.unit_size(_mark_to_market(cash, positions, last_known_close), n,
                                  unit_risk_pct=risk_pct, lot_size=config.TURTLE_LOT_SIZE,
                                  price=close, cash=cash)
            if shares < config.TURTLE_LOT_SIZE:
                missed_today.append({"code": code, "action": "pyramid", "reason": "資金不足",
                                     "score": round(score, 3)})
                continue
            pos = positions[code]
            pos.units.append(Unit(fill_date=d, fill_price=close, shares=shares, n_at_fill=n))
            pos.last_fill_price = close
            candidate_stop = tt.stop_line_for_unit(close, n, stop_n_mult=config.TURTLE_STOP_N_MULT)
            pos.stop_line = tt.tighten_stop(pos.stop_line, candidate_stop)
            cash -= shares * close
            new_units_today += 1
            total_units_open += 1

        for score, code, close, n in entry_candidates:
            if new_units_today >= config.TURTLE_MAX_NEW_UNITS_PER_DAY or \
               total_units_open >= config.TURTLE_MAX_TOTAL_UNITS:
                missed_today.append({"code": code, "action": "entry", "score": round(score, 3)})
                continue
            shares = tt.unit_size(_mark_to_market(cash, positions, last_known_close), n,
                                  unit_risk_pct=risk_pct, lot_size=config.TURTLE_LOT_SIZE,
                                  price=close, cash=cash)
            if shares < config.TURTLE_LOT_SIZE:
                missed_today.append({"code": code, "action": "entry", "reason": "資金不足",
                                     "score": round(score, 3)})
                continue
            pos = Position(code=code)
            pos.units.append(Unit(fill_date=d, fill_price=close, shares=shares, n_at_fill=n))
            pos.last_fill_price = close
            pos.stop_line = tt.stop_line_for_unit(close, n, stop_n_mult=config.TURTLE_STOP_N_MULT)
            positions[code] = pos
            cash -= shares * close
            new_units_today += 1
            total_units_open += 1

        # ── 5) 更新最後已知收盤（供缺資料日估值用）──
        for code, cs in series_by_code.items():
            row = cs.rows.get(d)
            if row is not None:
                last_known_close[code] = row["close"]

        # ── 6) 當日權益 ──
        market_value = 0.0
        for code, pos in positions.items():
            px = last_known_close.get(code, pos.last_fill_price)
            market_value += px * pos.total_shares
        equity = cash + market_value
        peak_equity = max(peak_equity, equity)

        # 回撤節流：跌破 peak×(1-20%) → 縮手；回升到 peak×(1-10%) 以內才恢復
        if not throttled and equity <= peak_equity * (1 - config.TURTLE_DRAWDOWN_THROTTLE_PCT):
            throttled = True
        elif throttled and equity >= peak_equity * (1 - config.TURTLE_DRAWDOWN_RECOVER_PCT):
            throttled = False

        equity_curve.append({
            "date": d.isoformat(), "equity_jpy": round(equity, 2),
            "cash_jpy": round(cash, 2), "market_value_jpy": round(market_value, 2),
            "open_positions": len(positions), "open_units": total_units_open,
            "throttled": throttled,
        })
        concurrent_units_daily.append(total_units_open)
        market_value_ratio_daily.append(market_value / equity if equity else 0.0)

    # ── 收尾：期末仍持有的部位以最後收盤估值列為「未平倉」，不計入已實現交易統計 ──
    open_summary = []
    for code, pos in positions.items():
        px = last_known_close.get(code, pos.last_fill_price)
        open_summary.append({
            "code": code, "units": len(pos.units), "shares": pos.total_shares,
            "cost_basis_jpy": round(pos.cost_basis, 2),
            "last_close": px, "market_value_jpy": round(px * pos.total_shares, 2),
            "unrealized_pnl_jpy": round(px * pos.total_shares - pos.cost_basis, 2),
            "stop_line": round(pos.stop_line, 2),
        })

    metrics = compute_metrics(equity_curve, closed_trades, concurrent_units_daily,
                              market_value_ratio_daily, sim_dates)

    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "universe_size": len(series_by_code),
        "sim_start": sim_dates[0].isoformat(),
        "sim_end": sim_dates[-1].isoformat(),
        "sim_trading_days": len(sim_dates),
        "initial_cash_jpy": config.TURTLE_INITIAL_CASH_JPY,
        "params": {
            "n_period": config.TURTLE_N_PERIOD,
            "entry_breakout_days": config.TURTLE_ENTRY_BREAKOUT_DAYS,
            "exit_breakout_days": config.TURTLE_EXIT_BREAKOUT_DAYS,
            "unit_risk_pct": config.TURTLE_UNIT_RISK_PCT,
            "stop_n_mult": config.TURTLE_STOP_N_MULT,
            "pyramid_add_n_mult": config.TURTLE_PYRAMID_ADD_N_MULT,
            "max_units_per_market": config.TURTLE_MAX_UNITS_PER_MARKET,
            "max_total_units": config.TURTLE_MAX_TOTAL_UNITS,
            "max_new_units_per_day": config.TURTLE_MAX_NEW_UNITS_PER_DAY,
            "drawdown_throttle_pct": config.TURTLE_DRAWDOWN_THROTTLE_PCT,
            "drawdown_recover_pct": config.TURTLE_DRAWDOWN_RECOVER_PCT,
            "reentry_cooldown_days": config.TURTLE_REENTRY_COOLDOWN_DAYS,
        },
        "metrics": metrics,
        "closed_trades": [vars(t) for t in closed_trades],
        "open_positions_at_end": open_summary,
        "equity_curve": equity_curve,
    }
    return result


def _mark_to_market(cash: float, positions: dict, last_known_close: dict) -> float:
    mv = 0.0
    for code, pos in positions.items():
        px = last_known_close.get(code, pos.last_fill_price)
        mv += px * pos.total_shares
    return cash + mv


def compute_metrics(equity_curve, closed_trades, concurrent_units_daily,
                    market_value_ratio_daily, sim_dates) -> dict:
    initial = float(config.TURTLE_INITIAL_CASH_JPY)
    final_equity = equity_curve[-1]["equity_jpy"] if equity_curve else initial
    total_return_pct = (final_equity - initial) / initial if initial else 0.0

    span_days = (sim_dates[-1] - sim_dates[0]).days or 1
    annualized_return_pct = (final_equity / initial) ** (365.0 / span_days) - 1.0 if initial > 0 else 0.0

    peak = initial
    max_dd = 0.0
    for row in equity_curve:
        peak = max(peak, row["equity_jpy"])
        dd = (peak - row["equity_jpy"]) / peak if peak else 0.0
        max_dd = max(max_dd, dd)

    n_trades = len(closed_trades)
    wins = [t for t in closed_trades if t.pnl_jpy > 0]
    losses = [t for t in closed_trades if t.pnl_jpy <= 0]
    win_rate = len(wins) / n_trades if n_trades else None
    avg_win_jpy = sum(t.pnl_jpy for t in wins) / len(wins) if wins else 0.0
    avg_loss_jpy = sum(t.pnl_jpy for t in losses) / len(losses) if losses else 0.0
    avg_win_pct = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0.0
    avg_loss_pct = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0.0
    gross_profit = sum(t.pnl_jpy for t in wins)
    gross_loss = abs(sum(t.pnl_jpy for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_profit > 0 else None)
    avg_holding_days = (sum(t.holding_days for t in closed_trades) / n_trades) if n_trades else None
    avg_concurrent_units = (sum(concurrent_units_daily) / len(concurrent_units_daily)
                            if concurrent_units_daily else 0.0)
    avg_capital_utilization = (sum(market_value_ratio_daily) / len(market_value_ratio_daily)
                               if market_value_ratio_daily else 0.0)

    return {
        "final_equity_jpy": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 4),
        "annualized_return_pct": round(annualized_return_pct, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "trade_count": n_trades,
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "avg_win_jpy": round(avg_win_jpy, 2),
        "avg_loss_jpy": round(avg_loss_jpy, 2),
        "avg_win_pct": round(avg_win_pct, 4),
        "avg_loss_pct": round(avg_loss_pct, 4),
        "profit_factor": (round(profit_factor, 3) if isinstance(profit_factor, float)
                         and profit_factor != float("inf") else profit_factor),
        "avg_holding_days": round(avg_holding_days, 1) if avg_holding_days is not None else None,
        "avg_concurrent_units": round(avg_concurrent_units, 2),
        "avg_capital_utilization_pct": round(avg_capital_utilization, 4),
    }


# ── 舊三盤模型：同期比較 ────────────────────────────────────────────────

def load_old_model_comparison(overlap_start: date, overlap_end: date) -> dict:
    ledger_path = PROJECT_ROOT / "data" / "ledgers" / "auto-pocket.json"
    if not ledger_path.exists():
        return {"available": False, "reason": "找不到 data/ledgers/auto-pocket.json"}
    with open(ledger_path, encoding="utf-8") as f:
        ledger = json.load(f)

    log_dir = PROJECT_ROOT / "data" / "auto_trade_log"
    logs = []
    for fp in sorted(glob.glob(str(log_dir / "*.json"))):
        stem = os.path.basename(fp)[:-5]
        try:
            d = datetime.strptime(stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if not (overlap_start <= d <= overlap_end):
            continue
        try:
            with open(fp, encoding="utf-8") as lf:
                logs.append(json.load(lf))
        except (OSError, json.JSONDecodeError):
            continue
    logs.sort(key=lambda lg: lg.get("date", ""))
    if not logs:
        return {"available": False, "reason": "回測區間內無舊模型 daily log 可比較"}

    start_equity = logs[0].get("equity_jpy") or ledger.get("initial_cash_jpy")
    end_equity = logs[-1].get("equity_jpy")
    total_return_pct = ((end_equity - start_equity) / start_equity) if start_equity else None

    closed_in_window = []
    for lg in logs:
        closed_in_window.extend(lg.get("closed", []))
    wins = [c for c in closed_in_window if (c.get("pnl_jpy") or 0) > 0]
    win_rate = (len(wins) / len(closed_in_window)) if closed_in_window else None
    holding_days = []
    for c in closed_in_window:
        try:
            ed = datetime.strptime(c["entry_date"], "%Y-%m-%d").date()
            xd = datetime.strptime(c["exit_date"], "%Y-%m-%d").date()
            holding_days.append((xd - ed).days)
        except (KeyError, ValueError, TypeError):
            continue
    avg_holding = sum(holding_days) / len(holding_days) if holding_days else None
    realized_pnl = sum((c.get("pnl_jpy") or 0) for c in closed_in_window)

    return {
        "available": True,
        "window_start": logs[0].get("date"), "window_end": logs[-1].get("date"),
        "start_equity_jpy": start_equity, "end_equity_jpy": end_equity,
        "total_return_pct": round(total_return_pct, 4) if total_return_pct is not None else None,
        "realized_pnl_jpy": round(realized_pnl, 2),
        "closed_trade_count": len(closed_in_window),
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "avg_holding_days": round(avg_holding, 1) if avg_holding is not None else None,
    }


# ── 報告 ─────────────────────────────────────────────────────────────────

def _pct_or_dash(v: Optional[float]) -> str:
    return f"{v:.1%}" if v is not None else "—"


def write_report(result: dict, old_model: dict) -> None:
    m = result["metrics"]
    p = result["params"]
    win_rate_s = _pct_or_dash(m["win_rate"])
    lines = []
    lines.append("# 海龜投資法（Turtle Trading）全歷史回測報告")
    lines.append("")
    lines.append(f"產出時間：{result['generated_at']}　回測腳本：`scripts/backtest_turtle.py`")
    lines.append("")
    lines.append("## 方法論")
    lines.append("")
    lines.append("- 策略：System 2（55 日收盤突破進場、不看上一筆是否獲利），"
                "20 日收盤突破出場，停損優先於 Donchian 出場。")
    lines.append("- 全市場候選池：`data/cloud-cache/*_price.csv` 涵蓋、暖身資料 "
                f"(>= {MIN_ROWS} 列) 足夠的 **{result['universe_size']} 檔**股票。")
    lines.append(f"- 部位大小：`unit = floor(equity × {p['unit_risk_pct']:.1%} / N)` 捨去到 "
                f"{config.TURTLE_LOT_SIZE} 股整數倍；同一檔最多 {p['max_units_per_market']} 個 unit"
                f"（含首次進場），每次加碼/進場後停損線收緊為「該次價格 − {p['stop_n_mult']}×N」（只升不降）。")
    lines.append(f"- 風控上限：全帳本最多 {p['max_total_units']} unit、單日最多新增 "
                f"{p['max_new_units_per_day']} unit；回撤節流：權益跌破歷史高點 "
                f"{p['drawdown_throttle_pct']:.0%} 縮手一半，回升到高點 -{p['drawdown_recover_pct']:.0%} "
                "以內恢復；出場後同檔 "
                f"{p['reentry_cooldown_days']} 個日曆日內不可新倉重新進場。")
    lines.append(f"- 起始資金：¥{config.TURTLE_INITIAL_CASH_JPY:,}（比照舊三盤模型，方便直接比較）。")
    lines.append("")
    lines.append("## 假設與限制（務必先讀）")
    lines.append("")
    lines.append(f"- **資料長度有限**：`data/cloud-cache` 目前只有約 8 個月（"
                f"{result['sim_start']} ~ {result['sim_end']}，扣除 60 個交易日暖身期）的日 K，"
                "遠短於海龜法設計時假設的「跨多個景氣循環」樣本，本報告的年化報酬/最大回撤等指標"
                "**極可能不具代表性**，僅供起始基準參考，之後隨每日模擬交易累積更長歷史應重新回測。")
    lines.append("- **存活偏誤**：候選池是「目前仍在 cloud-cache 中的股票」，缺少回測期間可能已下市"
                "/下櫃的股票，會讓報酬率偏樂觀。")
    lines.append("- **收盤突破而非盤中**：系統為收盤後跑的日頻排程，用收盤價判斷突破/出場，"
                "無法複製盤中觸價的原始海龜法（該法本為盤中觸價即成交）。")
    lines.append("- 不含手續費/滑價/稅負；假設所有訊號都能以當日收盤價足額成交（無流動性限制）。")
    lines.append("")
    lines.append("## 回測結果")
    lines.append("")
    lines.append("| 指標 | 數值 |")
    lines.append("|---|---|")
    lines.append(f"| 期末權益 | ¥{m['final_equity_jpy']:,.0f} |")
    lines.append(f"| 總報酬率 | {m['total_return_pct']:.2%} |")
    lines.append(f"| 年化報酬率（依實際天數換算） | {m['annualized_return_pct']:.2%} |")
    lines.append(f"| 最大回撤 | {m['max_drawdown_pct']:.2%} |")
    lines.append(f"| 交易筆數（已平倉） | {m['trade_count']} |")
    lines.append(f"| 勝率 | {win_rate_s} |")
    lines.append(f"| 平均獲利 | ¥{m['avg_win_jpy']:,.0f}（{m['avg_win_pct']:.2%}） |")
    lines.append(f"| 平均虧損 | ¥{m['avg_loss_jpy']:,.0f}（{m['avg_loss_pct']:.2%}） |")
    lines.append(f"| 獲利因子 | {m['profit_factor']} |")
    lines.append(f"| 平均持有天數 | {m['avg_holding_days']} |")
    lines.append(f"| 平均同時持有 unit 數 | {m['avg_concurrent_units']} |")
    lines.append(f"| 平均資金使用率 | {m['avg_capital_utilization_pct']:.1%} |")
    lines.append(f"| 期末仍持有部位 | {len(result['open_positions_at_end'])} 檔（未計入上述已平倉統計）|")
    lines.append("")
    lines.append("## 與舊三盤口袋名單模型比較")
    lines.append("")
    if old_model.get("available"):
        old_return_s = (f"{old_model['total_return_pct']:.2%}"
                        if old_model['total_return_pct'] is not None else "—")
        old_win_rate_s = _pct_or_dash(old_model["win_rate"])
        lines.append(f"比較區間（舊模型有 daily log 的重疊期間）：{old_model['window_start']} ~ "
                    f"{old_model['window_end']}")
        lines.append("")
        lines.append("| 指標 | 海龜模型（全期間回測，非同窗口）| 舊三盤模型（同窗口實跑）|")
        lines.append("|---|---|---|")
        lines.append(f"| 總報酬率 | {m['total_return_pct']:.2%} | {old_return_s} |")
        lines.append(f"| 已實現損益 | — | ¥{old_model['realized_pnl_jpy']:,.0f} |")
        lines.append(f"| 已平倉交易筆數 | {m['trade_count']}（全期間） | "
                    f"{old_model['closed_trade_count']}（同窗口） |")
        lines.append(f"| 勝率 | {win_rate_s} | {old_win_rate_s} |")
        lines.append(f"| 平均持有天數 | {m['avg_holding_days']} | {old_model['avg_holding_days']} |")
        lines.append("")
        lines.append("**注意**：海龜模型的指標是「全部 8 個月回測」，舊模型的指標是「兩者重疊的較短窗口"
                    "（舊模型實際上線運行的期間）」，兩者時間基準不同、不能直接相減比較報酬率，"
                    "此表只能看出「量級」與「交易風格」差異（例如持有天數、交易頻率），不是嚴謹的"
                    "同期回測對照。若要嚴謹比較，需要用兩套模型在**完全相同的日期區間**各自跑一次"
                    "（本次回測已把海龜模型跑好，舊模型受限於「歷史口袋名單需要 EDINET/margin 歷史"
                    "資料才能重算」，目前只有它實際上線後的 daily log 可用，做不到同窗口回放）。")
    else:
        lines.append(f"（無法比較：{old_model.get('reason')}）")
    lines.append("")
    lines.append("## 結論")
    lines.append("")
    if old_model.get("available") and old_model.get("total_return_pct") is not None:
        turtle_r = m["total_return_pct"]
        old_r = old_model["total_return_pct"]
        if turtle_r > old_r:
            verdict = ("海龜模型在其較長的回測窗口內報酬率高於舊模型在其實跑窗口內的報酬率，"
                      "但兩者窗口長度與市場環境不同，**不能直接視為「海龜比較好」的證據**——"
                      "樣本太短、窗口不對齊，充其量只能說「海龜模型的初步回測數字沒有明顯劣於舊模型」。")
        else:
            verdict = ("海龜模型在其回測窗口內的報酬率並未優於舊模型在其實跑窗口內的報酬率。"
                      "考量到窗口不對齊與樣本極短，這不代表海龜法本身無效，"
                      "但也不支持「換成海龜法會更好」的樂觀期待，須靠接下來的每日模擬交易持續驗證。")
        lines.append(verdict)
    else:
        lines.append("舊模型無可比較的重疊窗口資料，暫時只能看海龜模型自身的回測數字，"
                    "尚無法下「比舊模型好或差」的結論。")
    lines.append("")
    lines.append(f"完整逐筆交易與逐日權益曲線見 `docs/EVIDENCES/{BACKTEST_JSON_PATH.name}`。")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    EVIDENCES_DIR.mkdir(parents=True, exist_ok=True)
    result = run_backtest()
    overlap_start = datetime.strptime(result["sim_start"], "%Y-%m-%d").date()
    overlap_end = datetime.strptime(result["sim_end"], "%Y-%m-%d").date()
    old_model = load_old_model_comparison(overlap_start, overlap_end)
    result["old_model_comparison"] = old_model

    with open(BACKTEST_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"[write] {BACKTEST_JSON_PATH}")

    write_report(result, old_model)
    print(f"[write] {REPORT_PATH}")

    m = result["metrics"]
    win_rate_s = _pct_or_dash(m["win_rate"])
    print(f"\n總報酬 {m['total_return_pct']:.2%}｜最大回撤 {m['max_drawdown_pct']:.2%}｜"
          f"交易 {m['trade_count']} 筆｜勝率 {win_rate_s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
