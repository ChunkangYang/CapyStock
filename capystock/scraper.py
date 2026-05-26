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

def _fetch_margin_irbank(code: str) -> Optional[pd.DataFrame]:
    """從 irbank.net 爬取週頻信用残（免費公開，不需登入）。

    URL: https://irbank.net/{CODE}/margin
    欄位：日付, 買い残高（含増減）, 一般/制度, 売り残高（含増減）, 一般/制度, 倍率, 逆日歩
    數值單位為「株」，轉換為千株後回傳。
    """
    url = f"https://irbank.net/{code}/margin"
    html = _get(url)
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return None

    rows: list[dict] = []
    current_year = datetime.now().year

    for tr in table.select("tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
        if not tds:
            continue
        # 年份行：僅包含 4 位數年份
        if len(tds) >= 1 and re.match(r"^\d{4}$", tds[0]):
            current_year = int(tds[0])
            continue
        # 資料行：日付格式 MM/DD
        if not re.match(r"^\d{2}/\d{2}$", tds[0]):
            continue
        mm, dd = map(int, tds[0].split("/"))
        try:
            dt = datetime(current_year, mm, dd)
        except ValueError:
            continue

        # 買い残高欄位可能含増減（如 "14,302,200+905,600"）→ 取第一個數字
        long_raw = re.split(r"[+\-]", tds[1])[0] if len(tds) > 1 else ""
        short_raw = re.split(r"[+\-]", tds[3])[0] if len(tds) > 3 else ""
        ratio_raw = tds[5] if len(tds) > 5 else ""

        long_ = _to_num(long_raw)
        short = _to_num(short_raw)
        ratio = _to_num(ratio_raw)
        if long_ is None:
            continue
        rows.append({
            "week": dt,
            "margin_long": long_ / 1000.0,
            "margin_short": short / 1000.0 if short is not None else None,
            "ratio": ratio,
        })

    if not rows:
        return None
    df = pd.DataFrame(rows).drop_duplicates(subset=["week"]).sort_values("week")
    return df.reset_index(drop=True)


def fetch_margin(code: str) -> Optional[pd.DataFrame]:
    """週度信用残（融資/融券/倍率）。

    1. 先讀本地 CSV `data/cache/{code}_margin.csv`
    2. 若 CSV 不存在或最新資料超過 14 天，改從 Yahoo Finance Japan 爬取並更新 CSV
    3. 若兩者都失敗回傳 None，analyzer 會跳過條件 2。
    """
    path = storage.cache_path(code, "margin")
    cached: Optional[pd.DataFrame] = None

    if path.exists():
        try:
            df = pd.read_csv(path)
            if "week" in df.columns and "margin_long" in df.columns:
                df["week"] = pd.to_datetime(df["week"], format="mixed", errors="coerce")
                df = df.dropna(subset=["week"]).sort_values("week").reset_index(drop=True)
                if len(df) >= 1:
                    cached = df
        except Exception:
            pass

    # 若快取存在且最新資料在 14 天內，直接回傳
    if cached is not None:
        latest = cached["week"].max()
        age_days = (pd.Timestamp.now() - latest).days
        if age_days <= 8:
            return cached

    # 嘗試從 irbank.net 取得新資料
    fresh = _fetch_margin_irbank(code)
    if fresh is not None:
        if cached is not None:
            # 合併：保留舊資料，以 Yahoo 新資料覆蓋/補充
            combined = pd.concat([cached, fresh], ignore_index=True)
            combined = combined.drop_duplicates(subset=["week"], keep="last")
            combined = combined.sort_values("week").reset_index(drop=True)
        else:
            combined = fresh
        try:
            combined.to_csv(path, index=False)
        except Exception:
            pass
        return combined

    return cached


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
