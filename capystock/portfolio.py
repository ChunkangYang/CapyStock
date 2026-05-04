"""持倉（Portfolio）讀寫。與追蹤清單（watchlist）獨立分開。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from . import config


def _load() -> dict[str, dict]:
    if not config.PORTFOLIO_PATH.exists():
        return {}
    with config.PORTFOLIO_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict[str, dict]) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with config.PORTFOLIO_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_lot(
    code: str,
    name: str,
    entry_price: float,
    quantity: int,
    entry_date: Optional[str] = None,
    note: str = "",
) -> dict:
    data = _load()
    lot = {
        "id": str(uuid.uuid4()),
        "entry_price": float(entry_price),
        "quantity": int(quantity),
        "entry_date": entry_date or datetime.now().strftime("%Y-%m-%d"),
        "exit_price": None,
        "exit_date": None,
        "note": note,
    }
    if code not in data:
        data[code] = {"code": code, "name": name, "lots": []}
    else:
        data[code]["name"] = name or data[code].get("name", "")
    data[code]["lots"].append(lot)
    _save(data)
    return lot


def close_lot(code: str, lot_id: str, exit_price: float) -> Optional[dict]:
    data = _load()
    if code not in data:
        return None
    for lot in data[code]["lots"]:
        if lot["id"] == lot_id and lot["exit_date"] is None:
            lot["exit_price"] = float(exit_price)
            lot["exit_date"] = datetime.now().strftime("%Y-%m-%d")
            _save(data)
            return lot
    return None


def list_open() -> list[dict]:
    """回傳所有未平倉 lot，附帶 code / name。"""
    data = _load()
    result = []
    for entry in data.values():
        for lot in entry["lots"]:
            if lot["exit_date"] is None:
                result.append({**lot, "code": entry["code"], "name": entry["name"]})
    return result


def list_all() -> dict[str, dict]:
    return _load()


def get_entry(code: str) -> Optional[dict]:
    return _load().get(code)
