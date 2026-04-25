"""股息分析服務（基本面分析）。"""
from typing import Optional

import pandas as pd

from capystock import fundamental, scraper
from api.schemas.common import FundamentalMetric, FundamentalReport as FundamentalReportSchema


def get_fundamental_report(code: str) -> Optional[FundamentalReportSchema]:
    """取得基本面分析報告（8 指標評分）。"""
    # 取得股票名稱
    name = scraper.fetch_name(code) or ""

    # 分析基本面
    report, err = fundamental.analyze_fundamental(code, name)
    if err or report is None:
        return None

    # 轉換為 schema
    metrics = [
        FundamentalMetric(
            metric=m.metric,
            score=m.score,
            note=m.note,
        )
        for m in report.metrics
    ]

    return FundamentalReportSchema(
        code=code,
        name=name,
        overall=report.overall,
        metrics=metrics,
    )


def get_dividend_history(code: str) -> dict:
    """取得配當歷史（年度 DPS 與其他指標時序）。

    簡化版本，直接讀快取 CSV，返回可用於前端圖表的結構。
    """
    # 讀取快取檔案 data/cache/{code}_fundamental.csv
    cache_path = fundamental._cache_path(code)
    if not cache_path.exists():
        return {"dps_series": [], "eps_series": [], "payout_series": []}

    try:
        df = pd.read_csv(cache_path)
    except Exception:
        return {"dps_series": [], "eps_series": [], "payout_series": []}

    result = {
        "dps_series": df["dps"].dropna().tolist() if "dps" in df.columns else [],
        "eps_series": df["eps"].dropna().tolist() if "eps" in df.columns else [],
        "payout_series": (df["payout"].dropna() * 100).tolist() if "payout" in df.columns else [],
    }
    return result
