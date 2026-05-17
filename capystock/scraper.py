"""資料抓取：kabutan 優先，yfinance 備援。

回傳統一使用 pandas.DataFrame，欄位：
  price  : date(datetime), open, high, low, close, volume (千株)
  margin : week(datetime), margin_long, margin_short, ratio
  flow   : date(datetime), foreign_net, institution_net, individual_net (千株)
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from . import config, storage

_last_request_at = 0.0


def _throttle() -> None:
    global _last_request_at
    gap = time.time() - _last_request_at
    if gap < config.REQUEST_DELAY_SECONDS:
        time.sleep(config.REQUEST_DELAY_SECONDS - gap)
    _last_request_at = time.time()


def _get(url: str) -> Optional[str]:
    _throttle()
    try:
        r = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.REQUEST_TIMEOUT,
        )
        r.encoding = r.apparent_encoding or "utf-8"
        if r.status_code == 200:
            return r.text
    except requests.RequestException:
        pass
    return None


def _to_num(s: str) -> Optional[float]:
    s = (s or "").replace(",", "").replace("円", "").replace("%", "").strip()
    if not s or s in {"-", "--", "―"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---------- 股價 ----------

def _fetch_price_kabutan(code: str, pages: int = 3) -> Optional[pd.DataFrame]:
    rows: list[dict] = []
    current_year = datetime.now().year
    for page in range(1, pages + 1):
        url = f"https://kabutan.jp/stock/kabuka?code={code}&ashi=day&page={page}"
        html = _get(url)
        if not html:
            break
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", class_=re.compile(r"stock_kabuka"))
        if not table:
            # kabutan 常用 class 組合備援
            tables = soup.select("table.stock_kabuka_dwm, table.stock_kabuka0, table.stock_kabuka1")
            table = tables[0] if tables else None
        if not table:
            break
        for tr in table.select("tbody tr"):
            tds = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
            if len(tds) < 5:
                continue
            date_text = tds[0]
            m = re.match(r"(\d{2})/(\d{2})/(\d{2})", date_text)
            if m:
                yy, mm, dd = map(int, m.groups())
                year = 2000 + yy
            else:
                m = re.match(r"(\d{2})/(\d{2})", date_text)
                if not m:
                    continue
                mm, dd = map(int, m.groups())
                year = current_year
            try:
                dt = datetime(year, mm, dd)
            except ValueError:
                continue
            o, h, l, c = (_to_num(tds[i]) for i in range(1, 5))
            # 成交量通常是最後一欄（kabutan 格式：日付,始値,高値,安値,終値,前日比,前日比%,売買高(株)）
            vol = _to_num(tds[-1])
            if None in (o, h, l, c) or vol is None:
                continue
            rows.append({
                "date": dt,
                "open": o, "high": h, "low": l, "close": c,
                "volume": vol / 1000.0,  # 股 → 千股
            })
    if not rows:
        return None
    df = pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date")
    return df.reset_index(drop=True)


def _fetch_price_yfinance(code: str, days: int = 90) -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
    except ImportError:
        return None
    try:
        from datetime import datetime, timedelta
        t = yf.Ticker(f"{code}.T")
        if days > 90:
            start = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
            hist = t.history(start=start, auto_adjust=False)
        else:
            hist = t.history(period="3mo", auto_adjust=False)
    except Exception:
        return None
    if hist is None or hist.empty:
        return None
    df = hist.reset_index().rename(columns={
        "Date": "date", "Open": "open", "High": "high",
        "Low": "low", "Close": "close", "Volume": "volume",
    })
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df["volume"] = df["volume"] / 1000.0  # 股 → 千股
    return df[["date", "open", "high", "low", "close", "volume"]].sort_values("date").reset_index(drop=True)


def _normalize_yfinance_df(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """yfinance DataFrame → 標準格式（date, open, high, low, close, volume 千股）"""
    try:
        df = df.copy()
        # reset_index 處理 DatetimeIndex
        if df.index.name in ("Date", "Datetime", "date"):
            df = df.reset_index()
        df = df.rename(columns={
            "Date": "date", "Datetime": "date",
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Adj Close": "adj_close", "Volume": "volume",
        })
        if "date" not in df.columns:
            return None
        needed = ["date", "open", "high", "low", "close", "volume"]
        for col in needed:
            if col not in df.columns:
                return None
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df[needed].dropna(subset=["close", "open"]).copy()
        df["volume"] = df["volume"] / 1000.0
        df = df.sort_values("date").reset_index(drop=True)
        return df if len(df) >= 5 else None
    except Exception:
        return None


def fetch_price_bulk(
    codes: list[str],
    days: int = 90,
    batch_size: int = 100,
) -> dict[str, Optional[pd.DataFrame]]:
    """yfinance 批次下載多支股票價格（掃描加速用）。
    回傳 code → DataFrame（失敗為 None）。
    """
    try:
        import yfinance as yf
    except ImportError:
        return {code: None for code in codes}

    results: dict[str, Optional[pd.DataFrame]] = {}
    period = "6mo" if days > 90 else "3mo"

    for batch_start in range(0, len(codes), batch_size):
        batch_codes = codes[batch_start:batch_start + batch_size]
        batch_tickers = [f"{c}.T" for c in batch_codes]

        try:
            if len(batch_tickers) == 1:
                t = yf.Ticker(batch_tickers[0])
                hist = t.history(period=period, auto_adjust=False)
                results[batch_codes[0]] = _normalize_yfinance_df(hist.reset_index()) if (hist is not None and not hist.empty) else None
            else:
                hist = yf.download(
                    batch_tickers,
                    period=period,
                    auto_adjust=False,
                    group_by="ticker",
                    progress=False,
                    threads=True,
                    timeout=60,
                )
                if hist.empty:
                    for code in batch_codes:
                        results[code] = None
                else:
                    if isinstance(hist.columns, pd.MultiIndex):
                        lvl0 = hist.columns.get_level_values(0).unique()
                        for code, ticker in zip(batch_codes, batch_tickers):
                            if ticker in lvl0:
                                df_t = hist[ticker].dropna(how="all").reset_index()
                                results[code] = _normalize_yfinance_df(df_t)
                            else:
                                results[code] = None
                    else:
                        # 只有一個 ticker 被處理，flat columns
                        results[batch_codes[0]] = _normalize_yfinance_df(hist.reset_index())
                        for code in batch_codes[1:]:
                            results[code] = None
        except Exception:
            for code in batch_codes:
                if code not in results:
                    results[code] = None

        # 批次間禮貌等待
        time.sleep(1.0)

    return results


def fetch_price(code: str, days: int = 90) -> tuple[Optional[pd.DataFrame], str]:
    # cache-first：與 fetch_margin / fetch_flow 對齊，避免每次都 HTTP 爬 kabutan
    path = storage.cache_path(code, "price")
    if path.exists():
        try:
            df = pd.read_csv(path)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
                df = df.dropna(subset=["date"])
            if len(df) >= 5:
                return df, "cache"
        except Exception:
            pass
    df = _fetch_price_kabutan(code)
    if df is not None and len(df) >= 5:
        try:
            df.to_csv(path, index=False)
        except Exception:
            pass
        return df, "kabutan"
    df = _fetch_price_yfinance(code, days=days)
    if df is not None:
        try:
            df.to_csv(path, index=False)
        except Exception:
            pass
        return df, "yfinance"
    return None, "none"


# ---------- 信用残 ----------

def fetch_margin(code: str) -> Optional[pd.DataFrame]:
    """週度信用残（融資/融券/倍率）。

    kabutan 免費 tier 不穩定提供個股信用残歷史。本函數：
    1. 先讀本地 CSV `data/cache/{code}_margin.csv`
       （欄位：week,margin_long,margin_short,ratio）
    2. 若無則回傳 None，analyzer 會跳過條件 2。
    """
    path = storage.cache_path(code, "margin")
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if "week" not in df.columns or "margin_long" not in df.columns:
        return None
    # format='mixed' 兼容 JPX ingester 的 'YYYY-MM-DD' 與舊 yahoo/minkabu 的 'YYYY/M/D'
    df["week"] = pd.to_datetime(df["week"], format="mixed", errors="coerce")
    df = df.dropna(subset=["week"])
    return df.sort_values("week").reset_index(drop=True)


# ---------- 投資部門別（個股每日） ----------

def fetch_flow(code: str) -> Optional[pd.DataFrame]:
    """個股每日法人/外資/個人買賣超。

    日本公開免費資料不穩定提供此數據。本函數先嘗試讀本地手動 CSV
    (data/cache/{code}_flow.csv)，若不存在回傳 None，analyzer 會跳過相關條件。
    CSV 欄位：date,foreign_net,institution_net,individual_net （單位：千株）
    """
    path = storage.cache_path(code, "flow")
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if "date" not in df.columns:
        return None
    df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
    df = df.dropna(subset=["date"])
    return df.sort_values("date").reset_index(drop=True)


# ---------- 股票名稱 ----------

def fetch_name(code: str) -> Optional[str]:
    url = f"https://kabutan.jp/stock/?code={code}"
    html = _get(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    h2 = soup.find("h2")
    if h2:
        txt = h2.get_text(strip=True)
        # 形如 "7203トヨタ自動車" 或 "7203 トヨタ自動車"
        m = re.match(rf"{re.escape(code)}\s*(.+)$", txt)
        if m:
            return m.group(1).strip()
    h1 = soup.find("h1")
    if h1:
        txt = h1.get_text(strip=True)
        m = re.match(r"(.+?)\(\d+\)", txt)
        if m:
            return m.group(1).strip()
    return None


# ---------- 快取寫入 ----------

def cache_save(code: str, kind: str, df: pd.DataFrame) -> None:
    df.to_csv(storage.cache_path(code, kind), index=False)
