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

    def fetch(self, code: str) -> pd.DataFrame:
        url = f"https://finance.yahoo.co.jp/quote/{code}.T/credit_balance"
        headers = {"User-Agent": config.USER_AGENT}
        time.sleep(config.REQUEST_DELAY_SECONDS)
        resp = requests.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
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
        # 找信用残表格：日期 / 融資残 / 融券残 / 信用倍率
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if not any("融資" in h or "信用" in h for h in headers):
                continue
            for tr in table.find_all("tr")[1:]:
                tds = [td.get_text(strip=True).replace(",", "") for td in tr.find_all("td")]
                if len(tds) < 3:
                    continue
                try:
                    week = tds[0]
                    long_val = float(tds[1]) if tds[1] not in ("", "-") else None
                    short_val = float(tds[2]) if tds[2] not in ("", "-") else None
                    ratio = float(tds[3]) if len(tds) > 3 and tds[3] not in ("", "-") else None
                    # Yahoo 單位為「千株」，直接保留
                    rows.append({
                        "week": week,
                        "margin_long": long_val,
                        "margin_short": short_val,
                        "ratio": ratio,
                    })
                except (ValueError, IndexError):
                    continue
        if not rows:
            raise RuntimeError(f"Yahoo JP: 無法解析信用残表格 for {code}")
        df = pd.DataFrame(rows)
        return df
