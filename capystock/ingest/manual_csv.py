"""手動 CSV / XLSX 引入（多欄位別名 + 單位自動轉換）。"""
from __future__ import annotations

import io
from typing import Literal

import pandas as pd

from capystock.ingest.base import IngestionSource

# margin 欄位別名對照（key=目標欄位, value=可接受的別名清單）
_MARGIN_ALIASES: dict[str, list[str]] = {
    "week": ["week", "date", "日付", "週"],
    "margin_long": ["margin_long", "融資残", "Long", "long", "買残", "融資"],
    "margin_short": ["margin_short", "融券残", "Short", "short", "売残", "融券"],
    "ratio": ["ratio", "信用倍率", "倍率", "信用", "Ratio"],
}

# flow 欄位別名
_FLOW_ALIASES: dict[str, list[str]] = {
    "date": ["date", "日付", "日期"],
    "foreign_net": ["foreign_net", "外資", "外国人", "Foreign"],
    "institution_net": ["institution_net", "機関", "機関投資家", "Institution"],
    "individual_net": ["individual_net", "個人", "Individual"],
}


def _normalize_columns(df: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    for target, candidates in aliases.items():
        for col in df.columns:
            if col in candidates and target not in rename_map.values():
                rename_map[col] = target
                break
    df = df.rename(columns=rename_map)
    return df


def _auto_convert_units(df: pd.DataFrame, numeric_cols: list[str]) -> pd.DataFrame:
    """若欄位原始值超過 1,000,000（推測為「株」而非「千株」），除以 1000。"""
    for col in numeric_cols:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) > 0 and series.abs().median() > 1_000_000:
            df[col] = pd.to_numeric(df[col], errors="coerce") / 1000
    return df


class ManualCsvSource(IngestionSource):
    name = "manual_csv"
    kind: Literal["margin", "flow"]

    def __init__(self, kind: Literal["margin", "flow"] = "margin"):
        self.kind = kind

    def fetch(self, code: str) -> pd.DataFrame:
        raise NotImplementedError("ManualCsvSource 只接受 parse_bytes() 呼叫")

    def health_check(self) -> bool:
        return True

    def parse_bytes(self, content: bytes, filename: str = "") -> pd.DataFrame:
        """解析上傳的 CSV / XLSX bytes，回傳 normalized DataFrame。"""
        if filename.lower().endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(content))
        else:
            for enc in ("utf-8", "shift_jis", "cp932"):
                try:
                    df = pd.read_csv(io.StringIO(content.decode(enc)))
                    break
                except (UnicodeDecodeError, Exception):
                    continue
            else:
                raise ValueError("無法解析 CSV 編碼")

        aliases = _MARGIN_ALIASES if self.kind == "margin" else _FLOW_ALIASES
        df = _normalize_columns(df, aliases)

        numeric_cols = (
            ["margin_long", "margin_short", "ratio"]
            if self.kind == "margin"
            else ["foreign_net", "institution_net", "individual_net"]
        )
        df = _auto_convert_units(df, numeric_cols)
        return df
