"""每日三盤濾網選股 — 全市場掃描服務。

讀真實個股資料來源：
  - 第一盤：EDINET 每日快取 `data/cache/edinet/daily/*.json`（每檔的真實申報列表）
  - 第二盤：個股股價 CSV `data/cache/{code}_price.csv`
  - 第三盤：個股信用残 CSV `data/cache/{code}_margin.csv`

產出口袋名單（三關全過）+ 三盤漏斗計數，存成 parquet 快照供前端讀取。
"""
from __future__ import annotations

import glob
import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from capystock import config, pocket_filter, storage
from api.deps import DATA_DIR

logger = logging.getLogger(__name__)

EDINET_DAILY_DIR = config.EDINET_CACHE_DIR / "daily"
SCAN_SNAPSHOTS_DIR = DATA_DIR / "scan_snapshots"


def load_edinet_filings_by_code() -> dict[str, list[dict]]:
    """彙整 EDINET 每日快取 → {sec_code: [filing, ...]}（真實申報資料，每檔不同）。"""
    by_code: dict[str, list[dict]] = defaultdict(list)
    for fp in sorted(glob.glob(str(EDINET_DAILY_DIR / "*.json"))):
        try:
            with open(fp, encoding="utf-8") as f:
                rows = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for r in rows:
            code = (r.get("sec_code") or "").strip()
            if code:
                by_code[code].append(r)
    return dict(by_code)


def _load_price(code: str) -> Optional[pd.DataFrame]:
    path = storage.cache_path(code, "price")
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        if "date" in df.columns and "close" in df.columns and len(df):
            return df
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        pass
    return None


def _load_margin(code: str) -> Optional[pd.DataFrame]:
    path = storage.cache_path(code, "margin")
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        if "week" in df.columns and "margin_long" in df.columns and len(df):
            return df
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        pass
    return None


def _name_map() -> dict[str, str]:
    out: dict[str, str] = {}
    path = DATA_DIR / "universe.csv"
    if path.exists():
        try:
            df = pd.read_csv(path, dtype={"code": str})
            for _, row in df.iterrows():
                out[str(row.get("code", "")).strip()] = str(row.get("name", "") or "")
        except (OSError, pd.errors.ParserError):
            pass
    return out


def scan_pocket_list(
    *,
    min_filings: int = config.POCKET_GATE1_MIN_FILINGS,
    window_days: int = config.POCKET_GATE1_WINDOW_DAYS,
    cost_tolerance: float = config.POCKET_GATE2_COST_TOLERANCE_PCT,
    margin_weeks: int = config.POCKET_GATE3_MARGIN_DECLINE_WEEKS,
    as_of: Optional[str] = None,
    limit: Optional[int] = None,
    progress_callback=None,
) -> dict:
    """全市場跑三盤濾網。回傳 funnel 計數 + 評估結果列表（含口袋名單）。

    候選池＝有 EDINET 申報的個股（第一盤的前提）。對每檔讀真實 price/margin CSV。
    """
    filings_by_code = load_edinet_filings_by_code()
    names = _name_map()

    codes = sorted(filings_by_code.keys())
    if limit:
        codes = codes[:limit]

    results: list[pocket_filter.PocketResult] = []
    total = len(codes)
    for i, code in enumerate(codes):
        price_df = _load_price(code)
        margin_df = _load_margin(code)
        res = pocket_filter.evaluate_stock(
            code,
            filings_by_code.get(code, []),
            price_df,
            margin_df,
            name=names.get(code, ""),
            min_filings=min_filings,
            window_days=window_days,
            cost_tolerance=cost_tolerance,
            margin_weeks=margin_weeks,
            as_of=as_of,
        )
        results.append(res)
        if progress_callback and (i % 50 == 0 or i == total - 1):
            progress_callback(i + 1, total)

    # 漏斗：候選 → 過第一盤 → 過第一+二盤 → 三關全過
    candidates = len(results)
    pass1 = [r for r in results if r.passed_gate1]
    pass12 = [r for r in pass1 if r.passed_gate2]
    pocket = [r for r in pass12 if r.passed_gate3]

    funnel = {
        "candidates": candidates,
        "gate1_continuity": len(pass1),
        "gate2_cost": len(pass12),
        "gate3_margin": len(pocket),
    }

    pocket_rows = sorted(
        (r.to_dict() for r in pocket),
        key=lambda d: d["gate3"].get("drop_pct") or 0.0,
        reverse=True,
    )
    # 附「差一關」名單供觀察（過 1~2 關）
    near_miss = sorted(
        (r.to_dict() for r in results if r.gates_passed == 2 and not r.in_pocket),
        key=lambda d: d["gates_passed"],
        reverse=True,
    )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "params": {
            "min_filings": min_filings,
            "window_days": window_days,
            "cost_tolerance": cost_tolerance,
            "margin_weeks": margin_weeks,
            "as_of": as_of,
        },
        "funnel": funnel,
        "pocket": pocket_rows,
        "near_miss": near_miss,
    }


def snapshot_path(date_str: str) -> Path:
    return SCAN_SNAPSHOTS_DIR / f"pocket_{date_str}.json"


def write_snapshot(result: dict, date_str: Optional[str] = None) -> Path:
    SCAN_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    path = snapshot_path(date_str)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return path


def latest_snapshot() -> Optional[dict]:
    SCAN_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(glob.glob(str(SCAN_SNAPSHOTS_DIR / "pocket_*.json")))
    if not files:
        return None
    try:
        with open(files[-1], encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
