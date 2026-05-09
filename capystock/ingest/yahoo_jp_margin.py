"""Yahoo Finance Japan 信用残爬蟲。"""
from __future__ import annotations

import time
from typing import Literal

import pandas as pd
import requests
from bs4 import BeautifulSoup

from capystock import config
from capystock.ingest.base import IngestionSource


class YahooJpMarginSource(IngestionSource):
    name = "yahoo_jp"
    kind: Literal["margin"] = "margin"

    # Yahoo JP 於 2025 年將信用残頁面路徑從 /credit_balance 改為 /history?styl=margin
    _URL = "https://finance.yahoo.co.jp/quote/{code}.T/history?styl=margin"
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ja,en;q=0.9",
    }

    def fetch(self, code: str) -> pd.DataFrame:
        url = self._URL.format(code=code)
        time.sleep(config.REQUEST_DELAY_SECONDS)
        resp = requests.get(url, headers=self._HEADERS, timeout=config.REQUEST_TIMEOUT)
        if resp.status_code != 200:
            raise RuntimeError(f"Yahoo JP HTTP {resp.status_code} for {code}")
        return self._parse(resp.text, code)

    def health_check(self) -> bool:
        try:
            resp = requests.get(
                "https://finance.yahoo.co.jp/",
                headers={"User-Agent": config.USER_AGENT},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _parse(self, html: str, code: str) -> pd.DataFrame:
        soup = BeautifulSoup(html, "lxml")
        rows = []
        # 新格式：header row = [日付, 売残, 買残, 売残増減, 買残増減, 信用倍率]
        # 資料行：<th>date</th> + <td>売残</td><td>買残</td>...<td>倍率</td>
        for table in soup.find_all("table"):
            col_headers = [th.get_text(strip=True) for th in table.find_all("tr")[0].find_all("th")]
            if not any(k in col_headers for k in ("売残", "買残", "信用倍率")):
                continue
            for tr in table.find_all("tr")[1:]:
                th_cells = tr.find_all("th")
                td_cells = tr.find_all("td")
                if not th_cells or len(td_cells) < 2:
                    continue
                week = th_cells[0].get_text(strip=True)
                vals = [td.get_text(strip=True).replace(",", "") for td in td_cells]
                def _f(v: str):
                    try:
                        return float(v) if v not in ("", "-") else None
                    except ValueError:
                        return None
                # 欄位順序：売残, 買残, 売残増減, 買残増減, 信用倍率
                rows.append({
                    "week": week,
                    "margin_short": _f(vals[0]),   # 売残
                    "margin_long":  _f(vals[1]),   # 買残
                    "ratio":        _f(vals[4]) if len(vals) > 4 else None,
                })
        if not rows:
            raise RuntimeError(f"Yahoo JP: 無法解析信用残表格 for {code}")
        return pd.DataFrame(rows)
