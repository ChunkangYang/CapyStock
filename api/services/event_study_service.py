"""事件研究服務：AR / AAR / CAR 計算。"""
from __future__ import annotations

import logging
from datetime import date
from typing import List, Tuple

import pandas as pd

from api.schemas.analytics import EventStudyResult
from api.services.signal_service import get_price_history

logger = logging.getLogger(__name__)


class EventStudyService:
    def run(
        self,
        code: str,
        events: List[date],
        window: Tuple[int, int] = (-5, 20),
        benchmark: str = "self_mean",
    ) -> EventStudyResult:
        if not events:
            return EventStudyResult(
                code=code, events=[], window_days=window,
                aar=[], car=[], n_events=0, benchmark=benchmark,
            )

        pre, post = window
        total_days = abs(pre) + post + 1

        bars = get_price_history(code, days=365)
        if len(bars) < 5:
            return EventStudyResult(
                code=code, events=events, window_days=window,
                aar=[0.0] * total_days, car=[0.0] * total_days,
                n_events=0, benchmark=benchmark,
            )

        df = pd.DataFrame([{"date": b.date, "close": b.close} for b in bars])
        df = df.sort_values("date").reset_index(drop=True)
        df["ret"] = df["close"].pct_change()

        # benchmark: self_mean（過去 60 日平均日報酬）
        bench_return = float(df["ret"].tail(60).mean()) if benchmark == "self_mean" else 0.0

        all_ars: List[List[float]] = []
        for ev_date in events:
            ev_idx = df[df["date"] == ev_date].index
            if len(ev_idx) == 0:
                # 找最近一個
                future = df[df["date"] >= ev_date]
                if future.empty:
                    continue
                ev_idx = [future.index[0]]
            ev_i = ev_idx[0]

            start_i = ev_i + pre
            end_i = ev_i + post
            if start_i < 0 or end_i >= len(df):
                continue

            window_rets = df.loc[start_i:end_i, "ret"].fillna(0.0).tolist()
            if len(window_rets) != total_days:
                continue
            ars = [r - bench_return for r in window_rets]
            all_ars.append(ars)

        if not all_ars:
            return EventStudyResult(
                code=code, events=events, window_days=window,
                aar=[0.0] * total_days, car=[0.0] * total_days,
                n_events=0, benchmark=benchmark,
            )

        # AAR = mean across events for each offset
        aar = [
            sum(ev[t] for ev in all_ars) / len(all_ars)
            for t in range(total_days)
        ]
        # CAR = cumsum of AAR
        car: List[float] = []
        cumsum = 0.0
        for a in aar:
            cumsum += a
            car.append(round(cumsum, 6))

        return EventStudyResult(
            code=code,
            events=sorted(events),
            window_days=window,
            aar=[round(a, 6) for a in aar],
            car=car,
            n_events=len(all_ars),
            benchmark=benchmark,
        )
