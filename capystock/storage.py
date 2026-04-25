"""追蹤清單 (JSON) 與警示 log (CSV) 的讀寫。"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from . import config


def _ensure_dirs() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ---------- watchlist ----------

def load_watchlist() -> dict[str, dict]:
    _ensure_dirs()
    if not config.WATCHLIST_PATH.exists():
        return {}
    with config.WATCHLIST_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_watchlist(data: dict[str, dict]) -> None:
    _ensure_dirs()
    with config.WATCHLIST_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_watch(code: str, start_price: float, name: str = "") -> None:
    wl = load_watchlist()
    wl[code] = {
        "code": code,
        "name": name,
        "start_price": float(start_price),
        "added_date": datetime.now().strftime("%Y-%m-%d"),
    }
    save_watchlist(wl)


def remove_watch(code: str) -> bool:
    wl = load_watchlist()
    if code in wl:
        del wl[code]
        save_watchlist(wl)
        return True
    return False


# ---------- log.csv ----------

LOG_FIELDS = ["timestamp", "code", "name", "alert_type", "severity", "message"]


def append_log(code: str, name: str, alert_type: str, severity: str, message: str) -> None:
    _ensure_dirs()
    new_file = not config.LOG_PATH.exists()
    with config.LOG_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "code": code,
            "name": name,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
        })


def read_log(days: int = 30) -> list[dict]:
    if not config.LOG_PATH.exists():
        return []
    cutoff = datetime.now().timestamp() - days * 86400
    rows: list[dict] = []
    with config.LOG_PATH.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                ts = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S").timestamp()
            except (ValueError, KeyError):
                continue
            if ts >= cutoff:
                rows.append(row)
    return rows


# ---------- per-stock cache ----------

def cache_path(code: str, kind: str) -> Path:
    """kind: price | margin | flow"""
    _ensure_dirs()
    return config.CACHE_DIR / f"{code}_{kind}.csv"
