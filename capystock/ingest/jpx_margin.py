"""JPX 個別銘柄信用取引週末残高 PDF ingest。

每週從 JPX 官方 PDF 下載全市場信用残資料（3731+ 支），
一次下載取代逐股爬蟲，避免 Yahoo Finance JP 在 Azure IP 被封鎖的問題。

URL 模式：https://www.jpx.co.jp/markets/statistics-equities/margin/05.html
PDF 命名：syumatsu{YYYYMMDD}.pdf（週末日期）
"""
from __future__ import annotations

import io
import re
import time
from datetime import date
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
import requests

from capystock import config
from capystock.ingest.base import IngestionSource

_JPX_MARGIN_PAGE = "https://www.jpx.co.jp/markets/statistics-equities/margin/05.html"
_JPX_BASE = "https://www.jpx.co.jp"

# 市場等級全量快取路徑
MARKET_MARGIN_PATH = config.CACHE_DIR / "_market_margin.csv"


def _find_latest_pdf_url() -> str:
    """從 JPX 05.html 找最新的週末残高 PDF 連結。"""
    headers = {"User-Agent": config.USER_AGENT}
    time.sleep(config.REQUEST_DELAY_SECONDS)
    resp = requests.get(_JPX_MARGIN_PAGE, headers=headers, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "lxml")
    # 連結格式：/markets/statistics-equities/margin/tvdivq.../syumatsu{DATE}.pdf
    pdf_links = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if "syumatsu" in href and href.endswith(".pdf"):
            pdf_links.append(href)

    if not pdf_links:
        raise RuntimeError("JPX margin: 找不到 syumatsu PDF 連結")

    # 取最新（按日期字串排序）
    latest = sorted(pdf_links)[-1]
    return (_JPX_BASE + latest) if not latest.startswith("http") else latest


def _extract_week_from_url(url: str) -> str:
    """從 URL 提取日期並轉為 YYYY-MM-DD 格式。syumatsu20260501.pdf → 2026-05-01"""
    m = re.search(r"syumatsu(\d{8})", url)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return str(date.today())


def _parse_margin_pdf(content: bytes, week_label: str) -> pd.DataFrame:
    """解析 JPX 信用残 PDF，回傳 DataFrame。

    欄位：week, code, margin_short, margin_long, ratio
    code 是 4 位字串（去除 JPX 的尾碼 "0"）。
    """
    import pdfplumber

    rows = []
    # 代碼格式：行首 "B トヨタ自動車 普通株式 72030"，尾碼5字元（4碼+0 或 3碼+字母+0）
    pattern = re.compile(r"\s([0-9A-Z]{4}0)\s*$")

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or not row[0]:
                        continue
                    cell0 = str(row[0]).strip()
                    m = pattern.search(cell0)
                    if not m:
                        continue
                    raw_code = m.group(1)  # e.g. "72030"
                    code = raw_code[:-1]   # strip trailing "0" → "7203"

                    def _n(v) -> Optional[float]:
                        if v is None:
                            return None
                        s = str(v).replace(",", "").strip()
                        try:
                            return float(s) if s else None
                        except ValueError:
                            return None

                    # col4=売残高合計, col6=買残高合計
                    short = _n(row[4] if len(row) > 4 else None)
                    long_ = _n(row[6] if len(row) > 6 else None)
                    ratio = round(short / long_, 4) if short and long_ and long_ != 0 else None
                    rows.append({
                        "week": week_label,
                        "code": code,
                        "margin_short": short,
                        "margin_long": long_,
                        "ratio": ratio,
                    })

    if not rows:
        raise RuntimeError("JPX margin PDF: 未解析到任何股票資料")
    return pd.DataFrame(rows)


def fetch_market_margin() -> pd.DataFrame:
    """下載最新週次 PDF，解析全市場信用残，cache 到 _market_margin.csv。"""
    url = _find_latest_pdf_url()
    week_label = _extract_week_from_url(url)

    # 若已有當週資料，直接用 cache
    if MARKET_MARGIN_PATH.exists():
        try:
            existing = pd.read_csv(MARKET_MARGIN_PATH, dtype={"code": str})
            if week_label in existing["week"].values:
                return existing
        except Exception:
            pass

    time.sleep(config.REQUEST_DELAY_SECONDS)
    headers = {"User-Agent": config.USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()

    df = _parse_margin_pdf(resp.content, week_label)

    # append + dedupe
    if MARKET_MARGIN_PATH.exists():
        try:
            existing = pd.read_csv(MARKET_MARGIN_PATH, dtype={"code": str})
            df = pd.concat([existing, df], ignore_index=True)
            df = df.drop_duplicates(["week", "code"], keep="last")
        except Exception:
            pass

    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(MARKET_MARGIN_PATH, index=False)
    return df


class JpxMarginSource(IngestionSource):
    name = "jpx_margin"
    kind: Literal["margin"] = "margin"

    def fetch(self, code: str) -> pd.DataFrame:
        market_df = fetch_market_margin()
        stock_df = market_df[market_df["code"] == str(code)][["week", "margin_short", "margin_long", "ratio"]]
        if stock_df.empty:
            raise RuntimeError(f"JPX margin: 找不到代碼 {code} 的信用残資料（可能無信用交易）")
        return stock_df.reset_index(drop=True)

    def health_check(self) -> bool:
        try:
            r = requests.get(_JPX_MARGIN_PAGE, headers={"User-Agent": config.USER_AGENT}, timeout=5)
            return r.status_code == 200
        except Exception:
            return False
