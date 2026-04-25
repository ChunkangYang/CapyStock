"""回測和前進模擬核心引擎（純演算法，無外部時間依賴）。"""
from datetime import date, timedelta
from typing import Optional

from api.schemas.common import SignalResult
from api.schemas.simulation import (
    ClosedTrade,
    EquityPoint,
    Position,
    Simulation,
    SimulationState,
)


def resolve_entry_price(
    entry_date: date,
    entry_rule_price_basis: str,
    signal_close: Optional[float],
    next_open: Optional[float],
    user_price: Optional[float],
) -> Optional[float]:
    """根據進場規則解析進場價。"""
    if entry_rule_price_basis == "signal_close":
        return signal_close
    elif entry_rule_price_basis == "next_open":
        return next_open
    elif entry_rule_price_basis == "user_specified":
        return user_price
    return None


def resolve_exit_price(
    exit_rule_price_basis: str,
    signal_close: Optional[float],
    next_open: Optional[float],
) -> Optional[float]:
    """根據出場規則解析出場價。"""
    if exit_rule_price_basis == "signal_close":
        return signal_close
    elif exit_rule_price_basis == "next_open":
        return next_open
    return None


def compute_shares(
    entry_price: float,
    mode: str,
    fixed_jpy: Optional[float],
    fixed_shares: Optional[int],
    cash: float,
    pending_entries: int,
    max_concurrent: int,
) -> int:
    """計算進場股數。"""
    if mode == "equal_weight":
        available_slots = max_concurrent - pending_entries
        if available_slots <= 0:
            return 0
        allocation_per_slot = cash / available_slots
        shares = int(allocation_per_slot / entry_price)
    elif mode == "fixed_jpy":
        if fixed_jpy is None:
            return 0
        shares = int(fixed_jpy / entry_price)
    elif mode == "fixed_shares":
        shares = fixed_shares or 0
    else:
        return 0
    return max(0, shares)


def decide_exit_reason(
    pos: Position,
    today: date,
    latest_price: Optional[float],
    exit_rule_use_exit_signal: bool,
    exit_rule_use_stop_loss: bool,
    exit_rule_take_profit_pct: Optional[float],
    exit_rule_max_hold_days: Optional[int],
    has_exit_signal: bool,
    has_stop_loss: bool,
) -> Optional[str]:
    """判斷是否觸發出場條件，返回出場原因或 None。"""
    if latest_price is None:
        return None

    hold_days = (today - pos.entry_date).days

    if exit_rule_use_exit_signal and has_exit_signal:
        return "exit_signal"

    if exit_rule_use_stop_loss and has_stop_loss:
        return "stop_loss"

    if exit_rule_take_profit_pct is not None:
        gain_pct = (latest_price - pos.entry_price) / pos.entry_price
        if gain_pct >= exit_rule_take_profit_pct:
            return "take_profit"

    if exit_rule_max_hold_days is not None:
        if hold_days >= exit_rule_max_hold_days:
            return "max_hold"

    return None


def run_one_day(
    sim: Simulation,
    today: date,
    signal_service,
    price_cache: dict,  # {code: {date: {close, open}}}
) -> None:
    """執行一天的回測邏輯。

    Args:
        sim: Simulation object
        today: 當前日期
        signal_service: 訊號分析服務（用 analyze_one 等）
        price_cache: 快取的價格資料
    """
    state = sim.state
    cfg = sim.config

    # === 1. 進場 ===
    for cand in list(state.pending_entries):
        # 決定進場日期
        if cand.forced_entry_date is not None:
            entry_date = cand.forced_entry_date
        else:
            # 預設使用訊號當日
            entry_date = cand.entry_signal_date or today

        if entry_date is None or entry_date > today:
            continue

        # 取得進場價
        today_price = price_cache.get(cand.code, {}).get(entry_date)
        if today_price is None:
            continue

        signal_close = today_price.get("close")
        next_date = entry_date + timedelta(days=1)
        next_price = price_cache.get(cand.code, {}).get(next_date)
        next_open = next_price.get("open") if next_price else None

        entry_price = resolve_entry_price(
            entry_date,
            cfg.entry_rule.price_basis,
            signal_close,
            next_open,
            cfg.entry_rule.user_price,
        )

        if entry_price is None:
            continue

        # 檢查訊號要求
        if cfg.entry_rule.require_signal:
            try:
                snap = signal_service.analyze_one(cand.code)
                if not snap.accumulation_signal:
                    state.pending_entries.remove(cand)
                    continue
            except Exception:
                continue

        # 檢查部位限制
        if len(state.positions) >= cfg.position_sizing.max_concurrent_positions:
            continue

        # 計算股數
        shares = compute_shares(
            entry_price,
            cfg.position_sizing.mode,
            cfg.position_sizing.fixed_jpy,
            cfg.position_sizing.fixed_shares,
            state.cash,
            len(state.positions),
            cfg.position_sizing.max_concurrent_positions,
        )

        if shares <= 0:
            continue

        # 計算成本
        cost = shares * entry_price * (
            1 + cfg.cost_model.commission_pct + cfg.cost_model.slippage_pct
        )
        if cost > state.cash:
            continue

        # 建立部位
        state.cash -= cost
        state.positions.append(
            Position(
                code=cand.code,
                name=cand.name,
                entry_date=entry_date,
                entry_price=entry_price,
                shares=shares,
                cost_basis=cost,
            )
        )
        state.pending_entries.remove(cand)

    # === 2. 出場 ===
    for pos in list(state.positions):
        today_price = price_cache.get(pos.code, {}).get(today)
        if today_price is None:
            continue

        latest_price = today_price.get("close")

        # 檢查停損條件（最近 2 日跌破 -5%）
        has_stop_loss = False
        if cfg.exit_rule.use_stop_loss:
            stop_loss_pct = 0.95
            if latest_price is not None:
                if latest_price <= pos.entry_price * stop_loss_pct:
                    # 檢查前一天
                    prev_date = today - timedelta(days=1)
                    prev_price = price_cache.get(pos.code, {}).get(prev_date)
                    if prev_price:
                        prev_close = prev_price.get("close")
                        if prev_close and prev_close <= pos.entry_price * stop_loss_pct:
                            has_stop_loss = True

        # 檢查訊號條件
        has_exit_signal = False
        if cfg.exit_rule.use_exit_signal:
            try:
                snap = signal_service.analyze_one(pos.code)
                if snap.conditions.matched >= 2:
                    has_exit_signal = True
            except Exception:
                pass

        # 決定出場原因
        exit_reason = decide_exit_reason(
            pos,
            today,
            latest_price,
            cfg.exit_rule.use_exit_signal,
            cfg.exit_rule.use_stop_loss,
            cfg.exit_rule.take_profit_pct,
            cfg.exit_rule.max_hold_days,
            has_exit_signal,
            has_stop_loss,
        )

        if exit_reason:
            # 決定出場價
            signal_close = latest_price
            next_date = today + timedelta(days=1)
            next_price = price_cache.get(pos.code, {}).get(next_date)
            next_open = next_price.get("open") if next_price else None

            exit_price = resolve_exit_price(
                cfg.exit_rule.exit_price_basis,
                signal_close,
                next_open,
            )

            if exit_price is None:
                exit_price = latest_price

            # 平倉
            close_position(state, pos, exit_price, today, exit_reason, cfg.cost_model)

    # === 3. mark-to-market ===
    if state.positions or not state.equity_curve or state.equity_curve[-1].date != today:
        market_value = 0.0
        for pos in state.positions:
            today_price = price_cache.get(pos.code, {}).get(today)
            if today_price:
                close_price = today_price.get("close", pos.entry_price)
                market_value += close_price * pos.shares

        equity = state.cash + market_value
        state.equity_curve.append(
            EquityPoint(
                date=today,
                cash=state.cash,
                market_value=market_value,
                equity=equity,
            )
        )
        state.cursor_date = today


def close_position(
    state: SimulationState,
    pos: Position,
    exit_price: float,
    exit_date: date,
    exit_reason: str,
    cost_model,
) -> None:
    """平倉一個部位。"""
    proceed = pos.shares * exit_price
    cost = proceed * (1 - cost_model.commission_pct - cost_model.slippage_pct)
    state.cash += cost

    hold_days = (exit_date - pos.entry_date).days
    pnl_jpy = cost - pos.cost_basis
    pnl_pct = pnl_jpy / pos.cost_basis if pos.cost_basis != 0 else 0

    state.closed_trades.append(
        ClosedTrade(
            code=pos.code,
            name=pos.name,
            entry_date=pos.entry_date,
            entry_price=pos.entry_price,
            exit_date=exit_date,
            exit_price=exit_price,
            shares=pos.shares,
            pnl_jpy=pnl_jpy,
            pnl_pct=pnl_pct,
            hold_days=hold_days,
            exit_reason=exit_reason,
        )
    )

    state.positions.remove(pos)


def run_backtest(
    sim: Simulation,
    signal_service,
    price_cache: dict,
) -> None:
    """執行完整回測：從 start_date 走到 end_date。"""
    cfg = sim.config
    state = sim.state

    current = cfg.start_date
    end = cfg.end_date or current

    while current <= end:
        run_one_day(sim, current, signal_service, price_cache)
        current += timedelta(days=1)

    # 結束時平倉所有部位（end_of_sim）
    for pos in list(state.positions):
        last_price_data = price_cache.get(pos.code, {}).get(end)
        if last_price_data:
            exit_price = last_price_data.get("close", pos.entry_price)
            close_position(state, pos, exit_price, end, "end_of_sim", cfg.cost_model)


def calculate_report_metrics(sim: Simulation) -> dict:
    """計算報告指標。"""
    cfg = sim.config
    state = sim.state

    if not state.equity_curve:
        return {
            "total_return_pct": 0,
            "annualized_return_pct": 0,
            "max_drawdown_pct": 0,
            "win_rate": None,
            "avg_pnl_pct": None,
            "avg_hold_days": None,
            "profit_factor": None,
            "winning_trades": 0,
            "losing_trades": 0,
        }

    # 計算報酬
    initial_capital = cfg.initial_capital
    final_equity = state.equity_curve[-1].equity
    total_return = final_equity - initial_capital
    total_return_pct = (total_return / initial_capital * 100) if initial_capital != 0 else 0

    # 計算年化報酬
    period_days = (
        state.equity_curve[-1].date - state.equity_curve[0].date
    ).days + 1
    annualized_return_pct = (
        (1 + total_return / initial_capital) ** (365 / max(period_days, 1)) - 1
    ) * 100

    # 計算最大回撤
    max_dd_pct = 0
    peak = initial_capital
    for point in state.equity_curve:
        if point.equity > peak:
            peak = point.equity
        dd = (peak - point.equity) / peak if peak != 0 else 0
        if dd > max_dd_pct:
            max_dd_pct = dd
    max_dd_pct *= 100

    # 交易統計
    total_trades = len(state.closed_trades)
    winning_trades = sum(1 for t in state.closed_trades if t.pnl_jpy > 0)
    losing_trades = sum(1 for t in state.closed_trades if t.pnl_jpy < 0)

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else None
    avg_pnl_pct = (
        sum(t.pnl_pct for t in state.closed_trades) / total_trades * 100
    ) if total_trades > 0 else None
    avg_hold_days = (
        sum(t.hold_days for t in state.closed_trades) // total_trades
    ) if total_trades > 0 else None

    # Profit Factor
    wins_sum = sum(t.pnl_jpy for t in state.closed_trades if t.pnl_jpy > 0)
    loss_sum = abs(sum(t.pnl_jpy for t in state.closed_trades if t.pnl_jpy < 0))
    profit_factor = (wins_sum / loss_sum) if loss_sum > 0 else None

    return {
        "total_return_pct": total_return_pct,
        "annualized_return_pct": annualized_return_pct,
        "max_drawdown_pct": max_dd_pct,
        "win_rate": win_rate,
        "avg_pnl_pct": avg_pnl_pct,
        "avg_hold_days": avg_hold_days,
        "profit_factor": profit_factor,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
    }
