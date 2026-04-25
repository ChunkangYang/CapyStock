"""基本面分析：IR Bank 高股息金雞 8 指標評分。

資料流：
  scrape (IR Bank) → 快取 CSV (data/cache/{code}_fundamental.csv)
                   → 分數 (PASS/WARN/FAIL)
                   → Overall（STRONG / HEALTHY / CAUTION / RISKY）

CSV 欄位：year, sales, eps, op_margin, equity_ratio, op_cf, cash, dps, payout
  - sales / op_cf / cash：百万円（直接存原始值）
  - eps / dps：円
  - op_margin / equity_ratio / payout：百分比（以小數存，例 0.12 = 12%）
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from . import config, storage

CACHE_TTL_HOURS = 24
IRBANK_BASE = "https://irbank.net"

# 指標欄位順序（CSV 與顯示一致）
METRIC_FIELDS = [
    "sales", "eps", "op_margin", "equity_ratio",
    "op_cf", "cash", "dps", "payout",
]

# 中文顯示名
METRIC_DISPLAY = {
    "sales": "Sales",
    "eps": "EPS",
    "op_margin": "Op. Margin",
    "equity_ratio": "Equity Ratio",
    "op_cf": "Operating CF",
    "cash": "Cash & Equiv.",
    "dps": "DPS",
    "payout": "Payout Ratio",
}

# IR Bank 頁面表格 row label 關鍵字（模糊比對）
METRIC_LABELS = {
    "sales":        ("売上高", "売上収益"),
    "eps":          ("EPS", "一株当り利益", "1株当り利益", "一株利益"),
    "op_margin":    ("営業利益率",),
    "equity_ratio": ("自己資本比率",),
    "op_cf":        ("営業CF", "営業活動によるCF", "営業活動によるキャッシュ", "営業キャッシュ"),
    "cash":         ("現金等", "現金及び預金", "現金同等物", "現預金"),
    "dps":          ("一株配当", "1株配当", "配当金"),
    "payout":       ("配当性向",),
}

_last_request_at = 0.0


# ---------- HTTP ----------

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


# ---------- 字串 → 數值 ----------

def _parse_value(s: str) -> Optional[float]:
    """IR Bank 數字格式：'1,234百万', '12.3%', '45円', '-' 等。

    百分比回傳小數（0.12）。金額直接回傳原始單位下的數字（不作億/百万轉換）。
    """
    if s is None:
        return None
    s = str(s).replace(",", "").replace(" ", "").replace("\xa0", "").strip()
    if not s or s in {"-", "--", "―", "N/A", "n/a"}:
        return None
    pct = s.endswith("%")
    s = s.rstrip("%").rstrip("倍").rstrip("円").rstrip("株")
    # 去掉尾部單位字（百万/億/万）— 僅保留純數字；IR Bank 大多已在欄頭標單位
    for suf in ("百万", "十億", "億", "万"):
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    try:
        v = float(s)
    except ValueError:
        return None
    return v / 100.0 if pct else v


# ---------- 爬蟲 ----------

def _scrape_tables(html: str) -> list[dict[str, list[str]]]:
    """回傳多個 table：{row_label: [cell texts...]}。"""
    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, list[str]]] = []
    for table in soup.find_all("table"):
        rows: dict[str, list[str]] = {}
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True)
            if not label:
                continue
            vals = [c.get_text(strip=True) for c in cells[1:]]
            rows[label] = vals
        if rows:
            results.append(rows)
    return results


def _find_row(tables: list[dict[str, list[str]]], keywords: tuple[str, ...]) -> Optional[list[str]]:
    for tbl in tables:
        for label, vals in tbl.items():
            for kw in keywords:
                if kw in label:
                    return vals
    return None


def _fetch_irbank(code: str) -> Optional[dict[str, list[float | None]]]:
    """回傳 {metric: [値...]}；全部指標都抓不到則回傳 None。"""
    html_settlement = _get(f"{IRBANK_BASE}/{code}/settlement")
    html_dividend = _get(f"{IRBANK_BASE}/{code}/dividend")
    if not html_settlement and not html_dividend:
        return None

    tables: list[dict[str, list[str]]] = []
    if html_settlement:
        tables.extend(_scrape_tables(html_settlement))
    if html_dividend:
        tables.extend(_scrape_tables(html_dividend))

    result: dict[str, list[float | None]] = {}
    for metric, kws in METRIC_LABELS.items():
        vals = _find_row(tables, kws)
        if vals is None:
            result[metric] = []
            continue
        result[metric] = [_parse_value(v) for v in vals]

    # 至少要抓到 3 個指標且每個有 ≥3 個年度才視為有效
    valid = sum(1 for v in result.values() if len([x for x in v if x is not None]) >= 3)
    if valid < 3:
        return None
    return result


# ---------- 快取 ----------

def _cache_path(code: str) -> Path:
    storage._ensure_dirs()
    return config.CACHE_DIR / f"{code}_fundamental.csv"


def _cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age_hr = (time.time() - path.stat().st_mtime) / 3600.0
    return age_hr < CACHE_TTL_HOURS


def _save_cache(code: str, data: dict[str, list[float | None]]) -> None:
    # 找最長的 series 決定年度欄位數；年度用相對索引（-N, -N+1, ..., 0）
    max_len = max((len(v) for v in data.values()), default=0)
    rows: list[dict] = []
    for i in range(max_len):
        row = {"year_idx": i - (max_len - 1)}  # 0 = 最新年度
        for m in METRIC_FIELDS:
            series = data.get(m, [])
            row[m] = series[i] if i < len(series) else None
        rows.append(row)
    df = pd.DataFrame(rows, columns=["year_idx"] + METRIC_FIELDS)
    df.to_csv(_cache_path(code), index=False)


def _load_cache(code: str) -> Optional[dict[str, list[float | None]]]:
    path = _cache_path(code)
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    result: dict[str, list[float | None]] = {}
    for m in METRIC_FIELDS:
        if m not in df.columns:
            result[m] = []
            continue
        series = []
        for v in df[m].tolist():
            if pd.isna(v):
                series.append(None)
            else:
                series.append(float(v))
        result[m] = series
    return result


def load_or_fetch(code: str, force_refresh: bool = False) -> Optional[dict[str, list[float | None]]]:
    path = _cache_path(code)
    if not force_refresh and _cache_fresh(path):
        cached = _load_cache(code)
        if cached is not None:
            return cached
    data = _fetch_irbank(code)
    if data is None:
        # 抓取失敗 → 嘗試退回舊快取（即使過期）
        return _load_cache(code)
    _save_cache(code, data)
    return data


# ---------- 評分 ----------

@dataclass
class MetricScore:
    metric: str
    score: str  # PASS / WARN / FAIL / N/A
    note: str


@dataclass
class FundamentalReport:
    code: str
    name: str
    metrics: list[MetricScore] = field(default_factory=list)
    overall: str = "N/A"

    def counts(self) -> dict[str, int]:
        c = {"PASS": 0, "WARN": 0, "FAIL": 0, "N/A": 0}
        for m in self.metrics:
            c[m.score] = c.get(m.score, 0) + 1
        return c


def _clean(series: list[float | None]) -> list[float]:
    return [v for v in series if v is not None]


def _trend_slope(vals: list[float]) -> float:
    """簡易趨勢：末期相對初期的成長率。"""
    if len(vals) < 2 or vals[0] == 0:
        return 0.0
    return (vals[-1] - vals[0]) / abs(vals[0])


def _score_monotonic_up(vals: list[float], strong: float = 0.15, weak: float = 0.0) -> tuple[str, str]:
    if len(vals) < 3:
        return "N/A", "資料不足"
    g = _trend_slope(vals)
    ups = sum(1 for i in range(1, len(vals)) if vals[i] >= vals[i - 1])
    ratio = ups / (len(vals) - 1)
    if g >= strong and ratio >= 0.7:
        return "PASS", f"穩定成長（{g*100:+.0f}%，{len(vals)} 年）"
    if g <= -0.10 or ratio <= 0.3:
        return "FAIL", f"衰退趨勢（{g*100:+.0f}%）"
    if abs(g) <= weak + 0.05:
        return "WARN", f"停滯（{g*100:+.0f}%）"
    return "WARN", f"不穩定（{g*100:+.0f}%，上升 {ups}/{len(vals)-1} 年）"


def _score_sales(series: list[float | None]) -> MetricScore:
    vals = _clean(series)
    s, n = _score_monotonic_up(vals)
    return MetricScore("sales", s, n)


def _score_eps(series: list[float | None]) -> MetricScore:
    vals = _clean(series)
    s, n = _score_monotonic_up(vals)
    return MetricScore("eps", s, n)


def _score_op_margin(series: list[float | None]) -> MetricScore:
    vals = _clean(series)
    if len(vals) < 3:
        return MetricScore("op_margin", "N/A", "資料不足")
    avg = sum(vals) / len(vals)
    note = f"{avg*100:.1f}% 平均"
    if avg >= 0.10:
        return MetricScore("op_margin", "PASS", note + "（≥10%）")
    if avg >= 0.05:
        return MetricScore("op_margin", "WARN", note + "（5–10%）")
    return MetricScore("op_margin", "FAIL", note + "（<5%）")


def _score_equity_ratio(series: list[float | None]) -> MetricScore:
    vals = _clean(series)
    if not vals:
        return MetricScore("equity_ratio", "N/A", "資料不足")
    latest = vals[-1]
    note = f"{latest*100:.0f}%"
    if latest >= 0.60:
        return MetricScore("equity_ratio", "PASS", note + "（≥60%）")
    if latest >= 0.40:
        return MetricScore("equity_ratio", "WARN", note + "（40–60%）")
    return MetricScore("equity_ratio", "FAIL", note + "（<40%）")


def _score_op_cf(series: list[float | None]) -> MetricScore:
    vals = _clean(series)
    if len(vals) < 3:
        return MetricScore("op_cf", "N/A", "資料不足")
    neg = sum(1 for v in vals if v < 0)
    if neg == 0:
        return MetricScore("op_cf", "PASS", f"全部 {len(vals)} 年為正")
    if neg <= 2:
        return MetricScore("op_cf", "WARN", f"{neg} 年為負")
    return MetricScore("op_cf", "FAIL", f"{neg} 年為負（頻繁）")


def _score_cash(series: list[float | None]) -> MetricScore:
    vals = _clean(series)
    s, n = _score_monotonic_up(vals)
    return MetricScore("cash", s, n)


def _score_dps(series: list[float | None]) -> MetricScore:
    vals = _clean(series)
    if len(vals) < 3:
        return MetricScore("dps", "N/A", "資料不足")
    cuts = sum(1 for i in range(1, len(vals)) if vals[i] < vals[i - 1])
    increases = sum(1 for i in range(1, len(vals)) if vals[i] > vals[i - 1])
    if cuts == 0:
        return MetricScore("dps", "PASS", f"{increases} 次增配，無減配（{len(vals)} 年）")
    if cuts == 1:
        return MetricScore("dps", "WARN", f"1 次減配（{len(vals)} 年中）")
    return MetricScore("dps", "FAIL", f"{cuts} 次減配")


def _score_payout(series: list[float | None]) -> MetricScore:
    vals = _clean(series)
    if not vals:
        return MetricScore("payout", "N/A", "資料不足")
    avg = sum(vals) / len(vals)
    note = f"{avg*100:.0f}% 平均"
    if avg > 1.0 or avg > 0.70:
        return MetricScore("payout", "FAIL", note + "（>70% 或 >100%）")
    if avg >= 0.30 and avg <= 0.50:
        return MetricScore("payout", "PASS", note + "（30–50%）")
    if avg > 0.50:
        return MetricScore("payout", "WARN", note + "（50–70%）")
    return MetricScore("payout", "WARN", note + "（<30%）")


_SCORERS = {
    "sales":        _score_sales,
    "eps":          _score_eps,
    "op_margin":    _score_op_margin,
    "equity_ratio": _score_equity_ratio,
    "op_cf":        _score_op_cf,
    "cash":         _score_cash,
    "dps":          _score_dps,
    "payout":       _score_payout,
}


def evaluate(code: str, name: str, data: dict[str, list[float | None]]) -> FundamentalReport:
    report = FundamentalReport(code=code, name=name)
    for m in METRIC_FIELDS:
        report.metrics.append(_SCORERS[m](data.get(m, [])))

    c = report.counts()
    fails, passes = c["FAIL"], c["PASS"]
    if fails >= 3:
        report.overall = "RISKY"
    elif fails >= 1:
        report.overall = "CAUTION"
    elif passes >= 7:
        report.overall = "STRONG"
    elif passes >= 5:
        report.overall = "HEALTHY"
    else:
        report.overall = "CAUTION"
    return report


# ---------- 對外主入口 ----------

def analyze_fundamental(code: str, name: str = "") -> tuple[Optional[FundamentalReport], Optional[str]]:
    """回傳 (report, error_msg)。失敗時 report 為 None。"""
    data = load_or_fetch(code)
    if data is None:
        msg = (
            f"[ERROR] Could not fetch IR Bank data for {code}. "
            f"Try again later or add data manually to data/cache/{code}_fundamental.csv"
        )
        return None, msg
    return evaluate(code, name, data), None


def report_to_details_json(report: FundamentalReport) -> str:
    return json.dumps(
        {
            "overall": report.overall,
            "counts": report.counts(),
            "metrics": [
                {"metric": m.metric, "score": m.score, "note": m.note}
                for m in report.metrics
            ],
        },
        ensure_ascii=False,
    )
