"""判斷邏輯：持倉出場 / 停損 / 吃貨訊號。

回傳的 alert dict：
  {
    "code": str, "name": str,
    "alert_type": "exit" | "stop_loss" | "accumulation" | "info",
    "severity": "info" | "warn" | "critical",
    "message": str,
    "details": dict,
  }
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import config


@dataclass
class Snapshot:
    code: str
    name: str
    start_price: float
    latest_price: Optional[float] = None
    latest_date: Optional[pd.Timestamp] = None
    price_vs_start_pct: Optional[float] = None
    price_vs_recent_low_pct: Optional[float] = None
    # 條件旗標
    cond_inst_sell: bool = False
    cond_margin_surge: bool = False
    cond_price_rise: bool = False
    stop_loss_triggered: bool = False
    accumulation_signal: bool = False
    # 細節
    flow_recent: list[float] = field(default_factory=list)
    margin_trend_note: str = ""
    notes: list[str] = field(default_factory=list)


def _pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a - b) / b


def analyze(
    code: str,
    name: str,
    start_price: float,
    price_df: Optional[pd.DataFrame],
    margin_df: Optional[pd.DataFrame],
    flow_df: Optional[pd.DataFrame],
) -> tuple[Snapshot, list[dict]]:
    snap = Snapshot(code=code, name=name, start_price=float(start_price))
    alerts: list[dict] = []

    if price_df is None or len(price_df) == 0:
        snap.notes.append("無股價資料")
        return snap, alerts

    price_df = price_df.sort_values("date").reset_index(drop=True)
    latest = price_df.iloc[-1]
    snap.latest_price = float(latest["close"])
    snap.latest_date = latest["date"]
    snap.price_vs_start_pct = _pct(snap.latest_price, snap.start_price)

    # 近 N 日低點
    window = price_df.tail(config.PRICE_RECENT_LOW_WINDOW_DAYS)
    recent_low = float(window["low"].min()) if "low" in window.columns else float(window["close"].min())
    snap.price_vs_recent_low_pct = _pct(snap.latest_price, recent_low)

    # --- 條件 3: 股價離近期低點 +30% ---
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

    # --- 停損：收盤低於 start_price * (1 - STOP_LOSS_DROP_PCT) 連續 2 日 ---
    threshold = snap.start_price * (1 - config.STOP_LOSS_DROP_PCT)
    tail = price_df.tail(config.STOP_LOSS_CONSECUTIVE_DAYS)
    if len(tail) >= config.STOP_LOSS_CONSECUTIVE_DAYS and (tail["close"] < threshold).all():
        snap.stop_loss_triggered = True
        alerts.append({
            "code": code, "name": name,
            "alert_type": "stop_loss", "severity": "critical",
            "message": (
                f"停損觸發：連續 {config.STOP_LOSS_CONSECUTIVE_DAYS} 日收盤 "
                f"{snap.latest_price:.0f} 低於起始價 {snap.start_price:.0f} "
                f"的 {config.STOP_LOSS_DROP_PCT*100:.0f}%（{threshold:.0f}）"
            ),
            "details": {"threshold": threshold, "latest": snap.latest_price},
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
