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

    flow_recent: list[float] = field(default_factory=list)
    margin_trend_note: str = ""
    notes: list[str] = field(default_factory=list)


def _pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a - b) / b


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
    if flow_df is not None and len(flow_df) >= config.INSTITUTIONAL_SELL_CONSECUTIVE_DAYS + 10:
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
        snap.notes.append("缺投資部門別資料，跳過條件 1")

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

    # --- 吃貨訊號 ---
    if flow_df is not None and len(flow_df) >= config.ACCUMULATION_INSTITUTIONAL_BUY_DAYS:
        flow_df = flow_df.sort_values("date").reset_index(drop=True)
        n = config.ACCUMULATION_INSTITUTIONAL_BUY_DAYS
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
                "code": code, "name": name,
                "alert_type": "accumulation", "severity": "info",
                "message": f"主力疑似吃貨：外資/法人連續 {n} 日買超，融資餘額同期下降",
                "details": {},
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
