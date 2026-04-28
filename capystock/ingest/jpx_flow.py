"""JPX 投資部門別週報 Excel ingest。"""
from __future__ import annotations

import io
import time
from datetime import date
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
import requests

from capystock import config
from capystock.ingest.base import IngestionResult, IngestionSource

# JPX 公開統計頁（投資部門別売買状況）
_JPX_BASE = "https://www.jpx.co.jp/markets/statistics-equities/investor-type/"

# 市場 flow 快取路徑（不分個股）
MARKET_FLOW_PATH = config.CACHE_DIR / "_market_flow.csv"


def _fetch_jpx_excel(week: Optional[str] = None) -> bytes:
    """從 JPX 下載最新週報 Excel bytes。week 可指定，但目前取最新一份。"""
    headers = {"User-Agent": config.USER_AGENT}
    time.sleep(config.REQUEST_DELAY_SECONDS)
    # 取 JPX 頁面找最新 xlsx 連結
    resp = requests.get(_JPX_BASE, headers=headers, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "lxml")
    xlsx_link = None
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if href.endswith(".xlsx") or href.endswith(".xls"):
            if not href.startswith("http"):
                href = "https://www.jpx.co.jp" + href
            xlsx_link = href
            break

    if not xlsx_link:
        raise RuntimeError("JPX: 找不到週報 Excel 下載連結")

    time.sleep(config.REQUEST_DELAY_SECONDS)
    r2 = requests.get(xlsx_link, headers=headers, timeout=30)
    r2.raise_for_status()
    return r2.content


def parse_jpx_excel(content: bytes, week_label: Optional[str] = None) -> pd.DataFrame:
    """解析 JPX Excel → 億日圓單位 DataFrame。
    回傳欄位：week, foreign_net, institution_net, individual_net
    """
    df_raw = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None)

    # 找外資 / 個人 / 投信 行
    foreign_net = institution_net = individual_net = None

    for i, row in df_raw.iterrows():
        row_text = " ".join(str(v) for v in row.values)
        if "外国人" in row_text or "外資" in row_text:
            # 取數值欄（非空值）
            nums = [v for v in row.values if isinstance(v, (int, float)) and pd.notna(v)]
            if nums:
                foreign_net = float(nums[-1])  # 週淨買賣（最後一個數）
        if "投資信託" in row_text or "投信" in row_text:
            nums = [v for v in row.values if isinstance(v, (int, float)) and pd.notna(v)]
            if nums:
                institution_net = float(nums[-1])
        if "個人" in row_text:
            nums = [v for v in row.values if isinstance(v, (int, float)) and pd.notna(v)]
            if nums:
                individual_net = float(nums[-1])

    if foreign_net is None:
        # fallback: 嘗試 sheet "総合"
        try:
            df2 = pd.read_excel(io.BytesIO(content), sheet_name="総合", header=None)
            for i, row in df2.iterrows():
                row_text = " ".join(str(v) for v in row.values)
                if "外国人" in row_text or "外資" in row_text:
                    nums = [v for v in row.values if isinstance(v, (int, float)) and pd.notna(v)]
                    if nums:
                        foreign_net = float(nums[-1])
        except Exception:
            pass

    if foreign_net is None:
        raise RuntimeError("JPX Excel: 無法找到外資淨買賣數值")

    week = week_label or str(date.today().isocalendar()[0]) + "-W" + str(date.today().isocalendar()[1]).zfill(2)
    return pd.DataFrame([{
        "week": week,
        "foreign_net": foreign_net,
        "institution_net": institution_net,
        "individual_net": individual_net,
    }])


def estimate_stock_flow(
    code: str,
    market_flow: pd.DataFrame,
    price_df: Optional[pd.DataFrame] = None,
    market_total_volume: Optional[float] = None,
    stock_volume: Optional[float] = None,
) -> pd.DataFrame:
    """用市場 flow 比例估算個股 flow（estimated=True 標記）。"""
    rows = []
    for _, mrow in market_flow.iterrows():
        ratio = 0.005  # 預設 0.5%
        if market_total_volume and stock_volume and market_total_volume > 0:
            ratio = stock_volume / market_total_volume
        rows.append({
            "date": mrow.get("week", str(date.today())),
            "foreign_net": (mrow.get("foreign_net") or 0) * ratio,
            "institution_net": (mrow.get("institution_net") or 0) * ratio,
            "individual_net": (mrow.get("individual_net") or 0) * ratio,
            "estimated": True,
        })
    return pd.DataFrame(rows)


class JpxFlowSource(IngestionSource):
    name = "jpx_flow"
    kind: Literal["flow"] = "flow"

    def fetch(self, code: str) -> pd.DataFrame:
        content = _fetch_jpx_excel()
        market_df = parse_jpx_excel(content)
        # 寫入市場 flow
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if MARKET_FLOW_PATH.exists():
            existing = pd.read_csv(MARKET_FLOW_PATH)
            market_df = pd.concat([existing, market_df], ignore_index=True).drop_duplicates("week")
        market_df.to_csv(MARKET_FLOW_PATH, index=False)
        # 個股估算
        return estimate_stock_flow(code, market_df)

    def health_check(self) -> bool:
        try:
            r = requests.get(_JPX_BASE, headers={"User-Agent": config.USER_AGENT}, timeout=5)
            return r.status_code == 200
        except Exception:
            return False
