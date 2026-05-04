"""共用 schema 定義。"""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from capystock.indicators import IndicatorSignal


class WatchlistEntry(BaseModel):
    """追蹤清單項目。"""
    code: str
    name: str
    start_price: float
    added_date: Optional[str] = None


class PriceBar(BaseModel):
    """K 線資料點。"""
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float  # 千株


class FlowRow(BaseModel):
    """投資部門別買賣超。"""
    date: date
    foreign_net: Optional[float] = None  # 千株
    institution_net: Optional[float] = None
    individual_net: Optional[float] = None


class MarginRow(BaseModel):
    """信用殘餘。"""
    week: date
    margin_long: float  # 千株
    margin_short: float
    ratio: Optional[float] = None


class EdinetEvent(BaseModel):
    """EDINET 5% rule 申報事件。"""
    sec_code: str
    submit_date: str
    doc_type_code: Literal["350", "360"]  # 350=新規, 360=變更
    filer_name: str
    pdf_url: str


class SignalConditions(BaseModel):
    """三選二條件."""
    cond_inst_sell: bool
    cond_margin_surge: bool
    cond_price_rise: bool
    matched: int  # 0..3


class Alert(BaseModel):
    """警示訊息。"""
    alert_type: Literal["exit", "stop_loss", "accumulation", "info"]
    severity: Literal["info", "warn", "critical"]
    message: str
    details: dict = Field(default_factory=dict)


class SignalResult(BaseModel):
    """單檔股票的訊號分析結果。"""
    code: str
    name: str
    latest_price: Optional[float] = None
    latest_date: Optional[date] = None
    start_price: Optional[float] = None
    price_vs_start_pct: Optional[float] = None
    price_vs_recent_low_pct: Optional[float] = None
    conditions: SignalConditions
    stop_loss_triggered: bool
    accumulation_signal: bool
    flow_recent: list[float] = Field(default_factory=list)
    margin_trend_note: str = ""
    notes: list[str] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    indicator_signals: list[IndicatorSignal] = Field(default_factory=list)
    technical_score: float = 0.0


class FundamentalMetric(BaseModel):
    """基本面指標（評分）。"""
    metric: str
    score: Literal["PASS", "WARN", "FAIL", "N/A"]
    note: str


class FundamentalReport(BaseModel):
    """基本面分析報告。"""
    code: str
    name: str
    overall: Literal["STRONG", "HEALTHY", "CAUTION", "RISKY"]
    metrics: list[FundamentalMetric]

    def counts(self) -> dict[str, int]:
        """統計各等級計數。"""
        counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "N/A": 0}
        for m in self.metrics:
            counts[m.score] += 1
        return counts
