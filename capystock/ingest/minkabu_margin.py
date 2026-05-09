"""Minkabu 信用残 fallback 爬蟲。"""
from __future__ import annotations

import time
from typing import Literal

import pandas as pd
import requests
from bs4 import BeautifulSoup

from capystock import config
from capystock.ingest.base import IngestionSource


class MinkabuMarginSource(IngestionSource):
    name = "minkabu"
    kind: Literal["margin"] = "margin"

    def fetch(self, code: str) -> pd.DataFrame:
        # Minkabu 已移除 /stock/{code}/credit 頁面，此來源不再可用
        raise RuntimeError(f"Minkabu 信用残頁面已停止服務（/stock/{code}/credit 404）")
        return self._parse(resp.text, code)

    def health_check(self) -> bool:
        try:
            resp = requests.get(
                "https://minkabu.jp/",
                headers={"User-Agent": config.USER_AGENT},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _parse(self, html: str, code: str) -> pd.DataFrame:
        soup = BeautifulSoup(html, "lxml")
        rows = []
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if not any("融資" in h or "信用" in h or "残" in h for h in headers):
                continue
            for tr in table.find_all("tr")[1:]:
                tds = [td.get_text(strip=True).replace(",", "") for td in tr.find_all("td")]
                if len(tds) < 2:
                    continue
                try:
                    week = tds[0]
                    long_val = float(tds[1]) if tds[1] not in ("", "-") else None
                    short_val = float(tds[2]) if len(tds) > 2 and tds[2] not in ("", "-") else None
                    ratio_str = tds[3] if len(tds) > 3 else ""
                    ratio = float(ratio_str) if ratio_str not in ("", "-") else None
                    # Minkabu 單位為「千株」
                    rows.append({
                        "week": week,
                        "margin_long": long_val,
                        "margin_short": short_val,
                        "ratio": ratio,
                    })
                except (ValueError, IndexError):
                    continue
        if not rows:
            raise RuntimeError(f"Minkabu: 無法解析信用残表格 for {code}")
        df = pd.DataFrame(rows)
        return df
