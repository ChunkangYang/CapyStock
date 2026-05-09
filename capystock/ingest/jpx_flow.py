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
    """解析 JPX 投資部門別 Excel（stock_val_1_*.xls）。
    欄位布局：[類別JP, 売買JP, 売買EN, 金額_w1, 比率_w1, 差引き_w1, 金額_w2, ...]
    差引き Balance（淨買賣）固定在 column index 5。
    回傳欄位：week, foreign_net, institution_net, individual_net（千円）
    """
    df_raw = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None)

    # 欄位布局（0-indexed）：
    #   col0=類別JP, col1=売買JP, col2=売買EN, col3=空, col4=金額_w1,
    #   col5=比率_w1, col6=差引き_w1（淨買賣），col7=空, col8=金額_w2...
    # 數值皆為逗號格式字串，需去除逗號後轉 float
    BALANCE_IDX = 6

    def _parse_num(v) -> Optional[float]:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).replace(",", "").strip()
        try:
            return float(s)
        except ValueError:
            return None

    def _find_balance(keywords: list) -> Optional[float]:
        """在前 3 欄比對關鍵字，回傳第一個有效的差引き Balance 值。"""
        for _, row in df_raw.iterrows():
            vals = list(row.values)
            prefix = " ".join(str(v) for v in vals[:3])
            if not any(kw in prefix for kw in keywords):
                continue
            if len(vals) > BALANCE_IDX:
                result = _parse_num(vals[BALANCE_IDX])
                if result is not None:
                    return result
        return None

    # 海外投資家（外資）
    foreign_net = _find_balance(["海外投資家", "Foreigners"])
    # 法人（機構）
    institution_net = _find_balance(["法　人", "Institutions"])
    # 個人
    individual_net = _find_balance(["個　人", "Individuals"])

    if foreign_net is None:
        raise RuntimeError("JPX Excel: 無法找到外資淨買賣數值（海外投資家欄）")

    week = week_label or (
        str(date.today().isocalendar()[0])
        + "-W"
        + str(date.today().isocalendar()[1]).zfill(2)
    )
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
