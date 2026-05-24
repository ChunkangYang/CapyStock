"""判斷邏輯：持倉出場 / 停損 / 吃貨訊號。

回傳的 alert dict：
  {
    "code": str, "name": str,
    "alert_type": "exit" | "stop_loss" | "time_stop" | "volume_stop"
                  | "last_step_break" | "accumulation" | "info",
    "severity": "info" | "warn" | "critical",
    "message": str,
    "details": dict,
  }
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from . import config


@dataclass
class Snapshot:
    code: str
    name: str
    start_price: float
    # v2：心法新增的可選錨點與目標
    master_cost: Optional[float] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    last_step_price: Optional[float] = None
    added_date: Optional[str] = None

    latest_price: Optional[float] = None
    latest_date: Optional[pd.Timestamp] = None
    price_vs_start_pct: Optional[float] = None
    price_vs_recent_low_pct: Optional[float] = None
    price_vs_master_cost_pct: Optional[float] = None
    risk_reward_ratio: Optional[float] = None  # 風報比（target/stop 都有時）

    # 條件旗標（出場三選二）
    cond_inst_sell: bool = False
    cond_margin_surge: bool = False
    cond_price_rise: bool = False
    # 個別觸發旗標
    stop_loss_triggered: bool = False
    last_step_break: bool = False
    time_stop_warned: bool = False
    volume_stop_warned: bool = False
    target_reached: bool = False
    accumulation_signal: bool = False

    # 三階段移動停損（Chandelier Exit）
    trailing_stop_stage: Optional[int] = None  # 1/2/3
    trailing_stop_price: Optional[float] = None
    trailing_stop_triggered: bool = False
    trailing_stop_anchor: Optional[str] = None  # 描述：保本 / 進場 -3×ATR / 高點 -2.5×ATR
    atr_14: Optional[float] = None
    # 減碼警示（不強制砍倉）
    exit_warnings: list[str] = field(default_factory=list)

    flow_recent: list[float] = field(default_factory=list)
    margin_trend_note: str = ""
    notes: list[str] = field(default_factory=list)


def _pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a - b) / b


def _check_accumulation(
    snap: Snapshot,
    flow_df: Optional[pd.DataFrame],
    margin_df: Optional[pd.DataFrame],
    alerts: list[dict],
) -> None:
    """吃貨訊號：不依賴 price_df，可在 early return 前執行。
    flow_df 為週頻 JPX 資料（通常 1–3 筆），用實際可用筆數。
    """
    if flow_df is None or len(flow_df) < 2:
        return
    flow_df = flow_df.sort_values("date").reset_index(drop=True)
    n = min(config.ACCUMULATION_INSTITUTIONAL_BUY_DAYS, len(flow_df))
    last_n = flow_df.tail(n)
    inst_buy = any(
        col in flow_df.columns and (last_n[col] > 0).all()
        for col in ("foreign_net", "institution_net")
    )
    margin_declining = False
    if margin_df is not None and len(margin_df) >= 2:
        margin_declining = bool(margin_df["margin_long"].diff().tail(1).iloc[0] < 0)
    if inst_buy and margin_declining:
        snap.accumulation_signal = True
        alerts.append({
            "code": snap.code, "name": snap.name,
            "alert_type": "accumulation", "severity": "info",
            "message": f"主力疑似吃貨：外資/法人連續 {n} 期買超，融資餘額同期下降",
            "details": {},
        })


def _compute_atr(price_df: pd.DataFrame, period: int) -> Optional[float]:
    """True Range 14 日均（Wilder ATR 簡化版用 SMA）。"""
    if price_df is None or len(price_df) < period + 1:
        return None
    if not {"high", "low", "close"}.issubset(price_df.columns):
        return None
    high = price_df["high"]
    low = price_df["low"]
    prev_close = price_df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    if pd.isna(atr):
        return None
    return float(atr)


def _check_trailing_stop(
    snap: Snapshot,
    price_df: Optional[pd.DataFrame],
    alerts: list[dict],
) -> None:
    """三階段移動停損：
    Stage 1 (profit < STAGE2): max(進場×0.95, 進場 - 3×ATR)
    Stage 2 (STAGE2 ≤ profit < STAGE3): 進場價（保本）
    Stage 3 (profit ≥ STAGE3): 近 N 日最高 - 2.5×ATR (Chandelier Exit)

    錨點 entry 優先用 master_cost，否則用 start_price。
    """
    if snap.latest_price is None or price_df is None or len(price_df) < 2:
        return
    entry = snap.master_cost if snap.master_cost else snap.start_price
    if not entry or entry <= 0:
        return

    atr_period = config.get_exit_param("atr_period", config.ATR_PERIOD)
    atr = _compute_atr(price_df, atr_period)
    if atr is None or atr <= 0:
        return
    snap.atr_14 = atr

    profit_pct = (snap.latest_price - entry) / entry
    stage2 = config.get_exit_param("stage2_threshold_pct", config.TRAILING_STAGE2_THRESHOLD)
    stage3 = config.get_exit_param("stage3_threshold_pct", config.TRAILING_STAGE3_THRESHOLD)
    init_mult = config.get_exit_param("initial_stop_atr_mult", config.INITIAL_STOP_ATR_MULT)
    ch_mult = config.get_exit_param("chandelier_atr_mult", config.CHANDELIER_ATR_MULT)
    ch_window = config.get_exit_param("chandelier_high_window", config.CHANDELIER_HIGH_WINDOW)

    if profit_pct < stage2:
        stop_pct_price = entry * (1 - config.STOP_LOSS_DROP_PCT)
        stop_atr_price = entry - init_mult * atr
        stop_price = max(stop_pct_price, stop_atr_price)
        stage = 1
        anchor = f"進場 {entry:,.0f} - {init_mult}×ATR({atr_period})={atr:,.1f} 或 ×{1-config.STOP_LOSS_DROP_PCT}（取較高）"
    elif profit_pct < stage3:
        stop_price = entry
        stage = 2
        anchor = f"保本：進場 {entry:,.0f}（已獲利 {profit_pct*100:.1f}%）"
    else:
        recent_high = float(price_df["high"].tail(ch_window).max())
        stop_price = recent_high - ch_mult * atr
        stage = 3
        anchor = f"Chandelier：近 {ch_window} 日高 {recent_high:,.0f} - {ch_mult}×ATR({atr_period})={atr:,.1f}"

    snap.trailing_stop_stage = stage
    snap.trailing_stop_price = float(stop_price)
    snap.trailing_stop_anchor = anchor

    if snap.latest_price < stop_price:
        snap.trailing_stop_triggered = True
        alerts.append({
            "code": snap.code, "name": snap.name,
            "alert_type": "stop_loss", "severity": "critical",
            "message": (
                f"移動停損觸發（Stage {stage}）：最新 {snap.latest_price:,.0f} < "
                f"停損 {stop_price:,.0f}（{anchor}）"
            ),
            "details": {"stage": stage, "stop": stop_price, "latest": snap.latest_price,
                        "anchor": anchor, "atr": atr},
        })


def _check_exit_warnings(
    snap: Snapshot,
    price_df: Optional[pd.DataFrame],
    indicator_signals: Optional[list] = None,
) -> None:
    """技術破位減碼警示（不強制砍倉）：
    1) 收盤跌破 SMA20 且 SMA20 近 5 日向下
    2) MACD 死叉（從 indicator_signals 取，若有）
    3) 連續 N 日成交量 < 5 日均量 × VOLUME_DRY_RATIO
    """
    if price_df is None or len(price_df) < 25 or snap.latest_price is None:
        return
    if "close" not in price_df.columns:
        return

    # 1) SMA20 跌破 + 走平/向下
    sma_period = config.get_exit_param("sma_break_period", config.SMA_BREAK_PERIOD)
    sma = price_df["close"].rolling(sma_period).mean()
    if not pd.isna(sma.iloc[-1]) and not pd.isna(sma.iloc[-6]):
        below_sma = snap.latest_price < float(sma.iloc[-1])
        sma_falling = float(sma.iloc[-1]) <= float(sma.iloc[-6])
        if below_sma and sma_falling:
            snap.exit_warnings.append(
                f"跌破 SMA{sma_period} 且均線走平/向下 → 中期趨勢轉弱"
            )

    # 2) 量能萎縮
    if "volume" in price_df.columns and len(price_df) >= 10:
        dry_days = config.get_exit_param("volume_dry_days", config.VOLUME_DRY_DAYS)
        dry_ratio = config.get_exit_param("volume_dry_ratio", config.VOLUME_DRY_RATIO)
        vol5_mean = float(price_df["volume"].tail(5).mean())
        if vol5_mean > 0:
            recent_vol = price_df["volume"].tail(dry_days)
            dry_count = int((recent_vol < vol5_mean * dry_ratio).sum())
            if dry_count >= dry_days:
                snap.exit_warnings.append(
                    f"連續 {dry_days} 日量能 < 5 日均量 ×{dry_ratio} → 失去動能"
                )

    # 3) MACD 死叉（從 indicator_signals 找）
    if indicator_signals:
        for s in indicator_signals[:5]:  # 看最近 5 個訊號
            name = s.name if hasattr(s, "name") else s.get("name", "")
            if name == "macd_dead_cross":
                snap.exit_warnings.append("MACD 死叉 → 動能反轉")
                break


def _stop_loss_anchor(snap: Snapshot) -> tuple[float, str]:
    """選定停損錨點（價格、來源說明）。

    心法第七/九篇：應錨在主力成本，不是使用者買進價。
    """
    if snap.stop_price is not None:
        return float(snap.stop_price), "使用者指定停損價"
    if snap.master_cost is not None:
        threshold = snap.master_cost * (1 - config.STOP_LOSS_DROP_PCT)
        return threshold, f"主力成本 {snap.master_cost:,.0f} ×(1-{config.STOP_LOSS_DROP_PCT*100:.0f}%)"
    threshold = snap.start_price * (1 - config.STOP_LOSS_DROP_PCT)
    return threshold, f"起始價 {snap.start_price:,.0f} ×(1-{config.STOP_LOSS_DROP_PCT*100:.0f}%)"


def analyze(
    code: str,
    name: str,
    start_price: float,
    price_df: Optional[pd.DataFrame],
    margin_df: Optional[pd.DataFrame],
    flow_df: Optional[pd.DataFrame],
    *,
    master_cost: Optional[float] = None,
    target_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    last_step_price: Optional[float] = None,
    added_date: Optional[str] = None,
) -> tuple[Snapshot, list[dict]]:
    snap = Snapshot(
        code=code, name=name, start_price=float(start_price),
        master_cost=master_cost, target_price=target_price,
        stop_price=stop_price, last_step_price=last_step_price,
        added_date=added_date,
    )
    alerts: list[dict] = []

    # 風報比（進場前計算用，target+stop 都有才算）
    if target_price is not None and stop_price is not None and start_price > stop_price:
        reward = target_price - start_price
        risk = start_price - stop_price
        if risk > 0:
            snap.risk_reward_ratio = reward / risk
            if snap.risk_reward_ratio < config.RISK_REWARD_MIN_RATIO:
                snap.notes.append(
                    f"風報比 1:{snap.risk_reward_ratio:.2f} < 1:{config.RISK_REWARD_MIN_RATIO:.0f} "
                    f"（心法建議跳過）"
                )

    # 吃貨訊號不依賴 price_df，先在 early return 前執行
    _check_accumulation(snap, flow_df, margin_df, alerts)

    if price_df is None or len(price_df) == 0:
        snap.notes.append("無股價資料")
        return snap, alerts

    price_df = price_df.sort_values("date").reset_index(drop=True)
    latest = price_df.iloc[-1]
    snap.latest_price = float(latest["close"])
    snap.latest_date = latest["date"]
    snap.price_vs_start_pct = _pct(snap.latest_price, snap.start_price)
    if snap.master_cost:
        snap.price_vs_master_cost_pct = _pct(snap.latest_price, snap.master_cost)

    # 近 N 日低點
    window = price_df.tail(config.PRICE_RECENT_LOW_WINDOW_DAYS)
    recent_low = float(window["low"].min()) if "low" in window.columns else float(window["close"].min())
    snap.price_vs_recent_low_pct = _pct(snap.latest_price, recent_low)

    # --- 條件 3: 達到使用者目標價 / 或 fallback 漲離近期低點 30% ---
    if snap.target_price is not None:
        if snap.latest_price >= snap.target_price:
            snap.target_reached = True
            snap.cond_price_rise = True
            snap.notes.append(
                f"已達目標價 {snap.target_price:,.0f}（最新 {snap.latest_price:,.0f}）"
            )
    else:
        if snap.price_vs_recent_low_pct >= config.PRICE_RISE_FROM_RECENT_LOW:
            snap.cond_price_rise = True

    # --- 條件 1: 外資/法人連續賣超 & 累計賣超 > 前10日買超 20% ---
    need_rows = config.INSTITUTIONAL_SELL_CONSECUTIVE_DAYS + 10
    if flow_df is not None and len(flow_df) >= need_rows:
        flow_df = flow_df.sort_values("date").reset_index(drop=True)
        days_n = config.INSTITUTIONAL_SELL_CONSECUTIVE_DAYS
        last_n = flow_df.tail(days_n)
        prior_10 = flow_df.iloc[-(days_n + 10):-days_n]

        for col in ("foreign_net", "institution_net"):
            if col not in flow_df.columns:
                continue
            if (last_n[col] < 0).all():
                cum_sell = -last_n[col].sum()
                prior_buy = prior_10[col][prior_10[col] > 0].sum()
                if prior_buy > 0 and cum_sell / prior_buy >= config.INSTITUTIONAL_SELL_RATIO_OF_PRIOR_10D_BUY:
                    snap.cond_inst_sell = True
                    snap.notes.append(
                        f"{col} 連續 {days_n} 日賣超，累計 {cum_sell:.0f} 千株"
                        f"（前10日買超 {prior_buy:.0f} 千株的 {cum_sell/prior_buy*100:.0f}%）"
                    )
                    break

        snap.flow_recent = last_n.get("foreign_net", last_n.get("institution_net", pd.Series([]))).tolist()
    else:
        have = len(flow_df) if flow_df is not None else 0
        snap.notes.append(f"投資部門別資料筆數不足（需 {need_rows} 筆，現有 {have} 筆），跳過條件 1")

    # --- 條件 2: 融資残連續 3 週增加 & 本週增幅 > 8 週均值 2 倍 ---
    if margin_df is not None and len(margin_df) >= 9:
        margin_df = margin_df.sort_values("week").reset_index(drop=True)
        long_series = margin_df["margin_long"]
        diffs = long_series.diff()
        last3 = diffs.tail(config.MARGIN_INCREASE_CONSECUTIVE_WEEKS)
        if (last3 > 0).all():
            this_week_increase = float(last3.iloc[-1])
            prior_8 = diffs.tail(9).iloc[:-1]  # 前 8 週週增量
            mean_8w = float(prior_8.abs().mean()) if len(prior_8) else 0.0
            if mean_8w > 0 and this_week_increase >= mean_8w * config.MARGIN_INCREASE_VS_8W_MEAN:
                snap.cond_margin_surge = True
                base = long_series.iloc[-2]
                pct = this_week_increase / base if base else 0
                snap.margin_trend_note = (
                    f"融資↑ 連續 {config.MARGIN_INCREASE_CONSECUTIVE_WEEKS} 週 / "
                    f"本週增幅 +{pct*100:.1f}%（均值 {this_week_increase/mean_8w:.1f} 倍）"
                )
    else:
        snap.notes.append("缺信用残資料，跳過條件 2")

    # --- 三階段移動停損（Chandelier Exit）---
    _check_trailing_stop(snap, price_df, alerts)

    # --- 技術破位減碼警示 ---
    _check_exit_warnings(snap, price_df, indicator_signals=None)

    # --- 價格停損（v2：錨點優先用主力成本/使用者停損價）---
    threshold, anchor_desc = _stop_loss_anchor(snap)
    tail = price_df.tail(config.STOP_LOSS_CONSECUTIVE_DAYS)
    if len(tail) >= config.STOP_LOSS_CONSECUTIVE_DAYS and (tail["close"] < threshold).all():
        snap.stop_loss_triggered = True
        alerts.append({
            "code": code, "name": name,
            "alert_type": "stop_loss", "severity": "critical",
            "message": (
                f"停損觸發：連續 {config.STOP_LOSS_CONSECUTIVE_DAYS} 日收盤 "
                f"{snap.latest_price:,.0f} 低於 {threshold:,.0f}"
                f"（錨點：{anchor_desc}）"
            ),
            "details": {"threshold": threshold, "latest": snap.latest_price,
                        "anchor": anchor_desc},
        })

    # --- 最後一階失守（第七篇）---
    if snap.last_step_price is not None:
        last_step_threshold = snap.last_step_price * (1 - config.LAST_STEP_BREAK_PCT)
        ls_tail = price_df.tail(config.STOP_LOSS_CONSECUTIVE_DAYS)
        if len(ls_tail) >= config.STOP_LOSS_CONSECUTIVE_DAYS and (ls_tail["close"] < last_step_threshold).all():
            snap.last_step_break = True
            alerts.append({
                "code": code, "name": name,
                "alert_type": "last_step_break", "severity": "warn",
                "message": (
                    f"最後一階失守：跌破 {snap.last_step_price:,.0f} ×"
                    f"(1-{config.LAST_STEP_BREAK_PCT*100:.0f}%)={last_step_threshold:,.0f}"
                    f" 連 {config.STOP_LOSS_CONSECUTIVE_DAYS} 日"
                ),
                "details": {"last_step": snap.last_step_price,
                            "threshold": last_step_threshold},
            })

    # --- 時間停損（第九篇）---
    # 加入觀察 ≥ TIME_STOP_DAYS 個交易日，且最新價在成本帶 ±TIME_STOP_RANGE_PCT 內
    if snap.added_date and snap.master_cost:
        try:
            added = datetime.strptime(snap.added_date, "%Y-%m-%d")
            held_days = (datetime.now() - added).days
        except ValueError:
            held_days = 0
        if held_days >= config.TIME_STOP_DAYS:
            within_range = abs(_pct(snap.latest_price, snap.master_cost)) <= config.TIME_STOP_RANGE_PCT
            if within_range:
                snap.time_stop_warned = True
                alerts.append({
                    "code": code, "name": name,
                    "alert_type": "time_stop", "severity": "warn",
                    "message": (
                        f"時間停損警告：進場 {held_days} 日，股價仍在主力成本 "
                        f"{snap.master_cost:,.0f} ±{config.TIME_STOP_RANGE_PCT*100:.0f}% 內盤整 "
                        f"→ 考慮減碼一半"
                    ),
                    "details": {"held_days": held_days,
                                "master_cost": snap.master_cost},
                })

    # --- 量能停損（第九篇：爆量不漲）---
    if "volume" in price_df.columns and len(price_df) >= 6:
        prior_5 = price_df.iloc[-6:-1]
        avg_vol = float(prior_5["volume"].mean()) if not prior_5.empty else 0.0
        latest_vol = float(latest["volume"]) if pd.notna(latest.get("volume")) else 0.0
        prev_close = float(price_df.iloc[-2]["close"])
        day_change = _pct(snap.latest_price, prev_close)
        if (
            avg_vol > 0
            and latest_vol >= avg_vol * config.VOLUME_SPIKE_MULTIPLE
            and day_change < config.VOLUME_SPIKE_PRICE_FLAT_PCT
        ):
            snap.volume_stop_warned = True
            alerts.append({
                "code": code, "name": name,
                "alert_type": "volume_stop", "severity": "warn",
                "message": (
                    f"爆量不漲：成交量 {latest_vol:,.0f} 為近 5 日均 "
                    f"{avg_vol:,.0f} 的 {latest_vol/avg_vol:.1f} 倍，"
                    f"當日漲幅僅 {day_change*100:+.1f}% → 疑似主力出貨"
                ),
                "details": {"latest_vol": latest_vol, "avg_vol": avg_vol,
                            "day_change": day_change},
            })

    # --- 持倉出場彙整（三選二） ---
    matched = sum([snap.cond_inst_sell, snap.cond_margin_surge, snap.cond_price_rise])
    if matched >= 2:
        parts = []
        if snap.cond_inst_sell:
            parts.append("法人連賣")
        if snap.cond_margin_surge:
            parts.append(f"融資暴增（{snap.margin_trend_note}）")
        if snap.cond_price_rise:
            if snap.target_reached:
                parts.append(f"達目標價 {snap.target_price:,.0f}")
            else:
                parts.append(f"股價離低點 +{snap.price_vs_recent_low_pct*100:.0f}%")
        alerts.append({
            "code": code, "name": name,
            "alert_type": "exit", "severity": "warn",
            "message": f"符合 {matched}/3 出場條件：" + "、".join(parts),
            "details": {
                "cond_inst_sell": snap.cond_inst_sell,
                "cond_margin_surge": snap.cond_margin_surge,
                "cond_price_rise": snap.cond_price_rise,
            },
        })

    return snap, alerts
