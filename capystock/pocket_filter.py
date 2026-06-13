"""每日三盤濾網選股（舅舅心法第二篇 → 第十四節日本市場對映）。

三盤（順序不可亂，三關全過才進「口袋名單」）：

  第一盤 連續性（gate1）：日股無券商分點，改用 EDINET 大量保有/変更報告書（5% rule）。
      同一「申報人」在窗口內重複申報（次數 >= 門檻）視為主力連續建倉。
      輸入＝該檔的真實 EDINET 申報列表（每檔不同）。

  第二盤 成本（gate2）：主力成本以「各申報日鄰近收盤」均價近似（主力分批建倉的成本帶）。
      現價（最新收盤）不可高於主力成本 ×(1+容忍%)，否則是追高不是佈局。
      輸入＝該檔真實股價 CSV + 真實申報日（每檔不同）。

  第三盤 戶數/籌碼集中（gate3）：日股無集保戶數，改用個股信用残（融資 margin_long）。
      融資餘額連續 N 週下降＝浮額釋出、籌碼向強手集中。
      輸入＝該檔真實信用残 CSV（每檔不同）。

設計重點：所有 gate 函式為純函式，吃「單一個股」的真實資料（dict / DataFrame），
不依賴網路或檔案，方便 pytest。禁止用「全市場數字攤平到每檔」的假 flow。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from . import config


# ---------------------------------------------------------------------------
# 第一盤：連續性（EDINET 同一申報人重複申報）
# ---------------------------------------------------------------------------
def gate1_continuity(
    filings: list[dict],
    min_filings: int = config.POCKET_GATE1_MIN_FILINGS,
    window_days: int = config.POCKET_GATE1_WINDOW_DAYS,
    as_of: Optional[str] = None,
) -> dict:
    """同一申報人在窗口內申報次數 >= min_filings 即過第一盤。

    filings: 該檔 EDINET 申報列表，每筆需含
        {"submit_date": "YYYY-MM-DD", "filer_name": str, "doc_type_code": "350"|"360"}
    回傳 dict：
        {passed, lead_filer, filing_count, dates:[...], doc_types:[...]}
    """
    if not filings:
        return {"passed": False, "lead_filer": None, "filing_count": 0,
                "dates": [], "doc_types": []}

    # 窗口過濾（以最新申報日或 as_of 為基準回看 window_days）
    def _parse(d: str) -> Optional[datetime]:
        try:
            return datetime.strptime(d[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    dated = [(f, _parse(f.get("submit_date", ""))) for f in filings]
    dated = [(f, dt) for f, dt in dated if dt is not None]
    if not dated:
        return {"passed": False, "lead_filer": None, "filing_count": 0,
                "dates": [], "doc_types": []}

    anchor = _parse(as_of) if as_of else max(dt for _, dt in dated)
    cutoff = anchor.toordinal() - window_days
    in_window = [(f, dt) for f, dt in dated if cutoff <= dt.toordinal() <= anchor.toordinal()]

    # 依申報人聚合
    by_filer: dict[str, list[tuple[dict, datetime]]] = {}
    for f, dt in in_window:
        name = (f.get("filer_name") or "").strip()
        if not name:
            continue
        by_filer.setdefault(name, []).append((f, dt))

    if not by_filer:
        return {"passed": False, "lead_filer": None, "filing_count": 0,
                "dates": [], "doc_types": []}

    # 取申報次數最多的申報人為「主力」
    lead_filer, rows = max(by_filer.items(), key=lambda kv: len(kv[1]))
    rows.sort(key=lambda r: r[1])
    dates = [r[0].get("submit_date", "")[:10] for r in rows]
    doc_types = [r[0].get("doc_type_code", "") for r in rows]
    count = len(rows)
    return {
        "passed": count >= min_filings,
        "lead_filer": lead_filer,
        "filing_count": count,
        "dates": dates,
        "doc_types": doc_types,
    }


# ---------------------------------------------------------------------------
# 第二盤：成本（現價 <= 主力成本 +5%）
# ---------------------------------------------------------------------------
def _close_near(price_df: pd.DataFrame, target_ord: int) -> Optional[float]:
    """取最接近 target 日（不晚於該日；若無更早資料則取最早一筆）的收盤價。"""
    if price_df is None or len(price_df) == 0 or "close" not in price_df.columns:
        return None
    df = price_df.copy()
    df["_ord"] = pd.to_datetime(df["date"]).map(lambda x: x.toordinal())
    on_or_before = df[df["_ord"] <= target_ord]
    row = on_or_before.iloc[-1] if len(on_or_before) else df.iloc[0]
    try:
        return float(row["close"])
    except (ValueError, TypeError):
        return None


def gate2_cost(
    price_df: Optional[pd.DataFrame],
    filing_dates: list[str],
    tolerance: float = config.POCKET_GATE2_COST_TOLERANCE_PCT,
) -> dict:
    """主力成本 = 各申報日鄰近收盤均價；現價（最新收盤）<= 成本×(1+tolerance) 過關。

    回傳 {passed, master_cost, latest_price, premium_pct, price_date}
    price_date＝latest_price 來源那筆的日期（YYYY-MM-DD）。前端用它誠實標示
    「現價」其實是哪天的收盤，避免把 stale 收盤當即時價。無 price_df 時為 None。
    """
    out = {"passed": False, "master_cost": None, "latest_price": None,
           "premium_pct": None, "price_date": None}
    if price_df is None or len(price_df) == 0 or "close" not in price_df.columns:
        return out
    pdf = price_df.sort_values("date").reset_index(drop=True)
    latest_price = float(pdf.iloc[-1]["close"])
    out["latest_price"] = latest_price
    out["price_date"] = str(pdf.iloc[-1]["date"])[:10] if "date" in pdf.columns else None

    costs: list[float] = []
    for d in filing_dates:
        try:
            o = datetime.strptime(d[:10], "%Y-%m-%d").toordinal()
        except (ValueError, TypeError):
            continue
        c = _close_near(pdf, o)
        if c and c > 0:
            costs.append(c)
    if not costs:
        return out

    master_cost = sum(costs) / len(costs)
    premium = (latest_price - master_cost) / master_cost if master_cost else None
    out["master_cost"] = master_cost
    out["premium_pct"] = premium
    out["passed"] = premium is not None and premium <= tolerance
    return out


# ---------------------------------------------------------------------------
# 第三盤：戶數/籌碼集中（信用残 margin_long 連續下降）
# ---------------------------------------------------------------------------
def gate3_margin(
    margin_df: Optional[pd.DataFrame],
    weeks: int = config.POCKET_GATE3_MARGIN_DECLINE_WEEKS,
) -> dict:
    """融資餘額(margin_long)最近 weeks 週逐週下降 → 過第三盤。

    回傳 {passed, weeks, drop_pct, series:[...]}
    """
    out = {"passed": False, "weeks": weeks, "drop_pct": None, "series": []}
    if margin_df is None or "margin_long" not in margin_df.columns:
        return out
    m = margin_df.sort_values("week").reset_index(drop=True)
    if len(m) < weeks + 1:
        return out
    tail = m["margin_long"].tail(weeks + 1).reset_index(drop=True)
    out["series"] = [float(x) for x in tail.tolist()]
    diffs = tail.diff().dropna()
    if not (diffs < 0).all():
        return out
    first = float(tail.iloc[0])
    last = float(tail.iloc[-1])
    out["drop_pct"] = (first - last) / first if first else None
    out["passed"] = True
    return out


# ---------------------------------------------------------------------------
# 單檔三盤評估
# ---------------------------------------------------------------------------
@dataclass
class PocketResult:
    code: str
    name: str = ""
    gate1: dict = field(default_factory=dict)
    gate2: dict = field(default_factory=dict)
    gate3: dict = field(default_factory=dict)

    @property
    def passed_gate1(self) -> bool:
        return bool(self.gate1.get("passed"))

    @property
    def passed_gate2(self) -> bool:
        return bool(self.gate2.get("passed"))

    @property
    def passed_gate3(self) -> bool:
        return bool(self.gate3.get("passed"))

    @property
    def in_pocket(self) -> bool:
        """三關全過。"""
        return self.passed_gate1 and self.passed_gate2 and self.passed_gate3

    @property
    def gates_passed(self) -> int:
        return int(self.passed_gate1) + int(self.passed_gate2) + int(self.passed_gate3)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "in_pocket": self.in_pocket,
            "gates_passed": self.gates_passed,
            "gate1": self.gate1,
            "gate2": self.gate2,
            "gate3": self.gate3,
        }


def evaluate_stock(
    code: str,
    filings: list[dict],
    price_df: Optional[pd.DataFrame],
    margin_df: Optional[pd.DataFrame],
    name: str = "",
    *,
    min_filings: int = config.POCKET_GATE1_MIN_FILINGS,
    window_days: int = config.POCKET_GATE1_WINDOW_DAYS,
    cost_tolerance: float = config.POCKET_GATE2_COST_TOLERANCE_PCT,
    margin_weeks: int = config.POCKET_GATE3_MARGIN_DECLINE_WEEKS,
    as_of: Optional[str] = None,
) -> PocketResult:
    """對單一個股跑三盤濾網。短路評估：前一關沒過就不需要算後面（但仍計算以供 UI 漏斗展示）。"""
    g1 = gate1_continuity(filings, min_filings=min_filings, window_days=window_days, as_of=as_of)
    g2 = gate2_cost(price_df, g1.get("dates", []), tolerance=cost_tolerance)
    g3 = gate3_margin(margin_df, weeks=margin_weeks)
    return PocketResult(code=code, name=name, gate1=g1, gate2=g2, gate3=g3)
