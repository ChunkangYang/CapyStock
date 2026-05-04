"""異常偵測服務：成交量暴增 / 價格跳動 / 跳空。"""
from __future__ import annotations

import logging
from datetime import date
from typing import List

import pandas as pd

from api.schemas.analytics import AnomalyEvent
from api.services.signal_service import get_price_history

logger = logging.getLogger(__name__)


def _severity(value: float, threshold: float) -> str:
    ratio = value / threshold if threshold else 0
    if ratio >= 3.0:
        return "critical"
    if ratio >= 1.5:
        return "warn"
    return "info"


class AnomalyService:
    def scan(
        self,
        code: str,
        days: int = 90,
        volume_multiplier: float = 3.0,
        price_sigma: float = 2.5,
        gap_pct: float = 0.05,
    ) -> List[AnomalyEvent]:
        bars = get_price_history(code, days=max(days + 20, 120))
        if len(bars) < 5:
            return []

        df = pd.DataFrame([{
            "date": b.date,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        } for b in bars])
        df = df.sort_values("date").reset_index(drop=True)

        # 20 日移動統計
        df["vol_ma20"] = df["volume"].rolling(20, min_periods=5).mean()
        df["ret"] = df["close"].pct_change()
        df["ret_std20"] = df["ret"].rolling(20, min_periods=5).std()

        events: List[AnomalyEvent] = []
        cutoff = df["date"].iloc[-1] if days >= len(df) else \
            df["date"].iloc[-(days + 1)]

        for i, row in df.iterrows():
            if row["date"] <= cutoff and days < len(df):
                continue
            d = row["date"]
            vol_ma = row.get("vol_ma20")
            if pd.notna(vol_ma) and vol_ma > 0:
                vol_ratio = row["volume"] / vol_ma
                if vol_ratio >= volume_multiplier:
                    events.append(AnomalyEvent(
                        code=code, date=d, type="volume_spike",
                        value=round(vol_ratio, 3), threshold=volume_multiplier,
                        severity=_severity(vol_ratio, volume_multiplier),
                    ))

            ret = row.get("ret")
            ret_std = row.get("ret_std20")
            if pd.notna(ret) and pd.notna(ret_std) and ret_std > 0:
                sigma = abs(ret) / ret_std
                if sigma >= price_sigma:
                    events.append(AnomalyEvent(
                        code=code, date=d, type="price_jump",
                        value=round(sigma, 3), threshold=price_sigma,
                        severity=_severity(sigma, price_sigma),
                    ))

            # 跳空偵測
            if i > 0:
                prev_close = df.at[i - 1, "close"]
                if pd.notna(prev_close) and prev_close > 0:
                    gap = (row["open"] - prev_close) / prev_close
                    if abs(gap) >= gap_pct:
                        evt_type = "gap_up" if gap > 0 else "gap_down"
                        events.append(AnomalyEvent(
                            code=code, date=d, type=evt_type,
                            value=round(abs(gap), 4), threshold=gap_pct,
                            severity=_severity(abs(gap), gap_pct),
                        ))

        return events
