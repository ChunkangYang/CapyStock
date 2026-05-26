"""Ingest Service：fallback chain + cache 管理。"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional

import pandas as pd

from api.schemas.ingest import CacheStatus, IngestionResult, IngestStatusResponse
from capystock import config
from capystock.ingest.base import IngestionSource
from capystock.ingest.manual_csv import ManualCsvSource
from capystock.ingest.minkabu_margin import MinkabuMarginSource
from capystock.ingest.yahoo_jp_margin import YahooJpMarginSource

logger = logging.getLogger(__name__)

_MARGIN_SOURCES: list[IngestionSource] = [
    YahooJpMarginSource(),
    MinkabuMarginSource(),
]

_SOURCE_META_FILE = config.CACHE_DIR / "_ingest_meta.json"


def _load_meta() -> dict:
    if _SOURCE_META_FILE.exists():
        try:
            return json.loads(_SOURCE_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_meta(meta: dict) -> None:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _SOURCE_META_FILE.write_text(json.dumps(meta, default=str, ensure_ascii=False, indent=2), encoding="utf-8")


def _cache_path(code: str, kind: str) -> Path:
    return config.CACHE_DIR / f"{code}_{kind}.csv"


def _cache_age(code: str, kind: str) -> Optional[timedelta]:
    p = _cache_path(code, kind)
    if not p.exists():
        return None
    mtime = date.fromtimestamp(p.stat().st_mtime)
    return date.today() - mtime


class IngestService:
    def fetch_margin(self, code: str, force: bool = False) -> IngestionResult:
        """依序試 margin sources；第一個成功即停。force=True 時繞過 24h cache。"""
        cache = _cache_path(code, "margin")
        age = _cache_age(code, "margin")
        if not force and age is not None and age.days < 1:
            return IngestionResult(
                code=code, kind="margin", source="cache",
                rows_fetched=0, written_path=str(cache), ok=True,
                error="cache still fresh",
            )

        errors: list[str] = []
        for src in _MARGIN_SOURCES:
            try:
                df = src.fetch(code)
                if df.empty:
                    errors.append(f"{src.name}: empty dataframe")
                    continue
                config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
                df.to_csv(cache, index=False)
                date_range = None
                if "week" in df.columns and len(df) >= 1:
                    dates = pd.to_datetime(df["week"], errors="coerce").dropna()
                    if len(dates):
                        date_range = (dates.min().date(), dates.max().date())
                meta = _load_meta()
                meta[f"{code}_margin"] = {"last_source": src.name, "updated": str(date.today())}
                _save_meta(meta)
                return IngestionResult(
                    code=code, kind="margin", source=src.name,
                    rows_fetched=len(df), date_range=date_range,
                    written_path=str(cache), ok=True,
                )
            except Exception as e:
                msg = f"{src.name}: {e}"
                logger.warning(msg)
                errors.append(msg)

        return IngestionResult(
            code=code, kind="margin", source="none",
            rows_fetched=0, ok=False,
            error="; ".join(errors),
        )

    def import_manual(self, code: str, kind: Literal["margin"], file_content: bytes, filename: str = "") -> IngestionResult:
        """解析手動上傳的 CSV / XLSX，寫入 cache。"""
        src = ManualCsvSource(kind=kind)
        try:
            df = src.parse_bytes(file_content, filename)
            if df.empty:
                return IngestionResult(code=code, kind=kind, source="manual_csv", rows_fetched=0, ok=False, error="empty file")
            cache = _cache_path(code, kind)
            config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache, index=False)
            meta = _load_meta()
            meta[f"{code}_{kind}"] = {"last_source": "manual_csv", "updated": str(date.today())}
            _save_meta(meta)
            return IngestionResult(
                code=code, kind=kind, source="manual_csv",
                rows_fetched=len(df), written_path=str(cache), ok=True,
            )
        except Exception as e:
            return IngestionResult(code=code, kind=kind, source="manual_csv", rows_fetched=0, ok=False, error=str(e))

    def get_status(self, code: str) -> IngestStatusResponse:
        meta = _load_meta()
        statuses: list[CacheStatus] = []
        for kind in ("margin", "price"):
            age = _cache_age(code, kind)
            key = f"{code}_{kind}"
            last_source = meta.get(key, {}).get("last_source")
            last_updated_str = meta.get(key, {}).get("updated")
            last_updated = date.fromisoformat(last_updated_str) if last_updated_str else None
            statuses.append(CacheStatus(
                kind=kind,
                last_updated=last_updated,
                age_days=age.days if age is not None else None,
                last_source=last_source,
                exists=_cache_path(code, kind).exists(),
            ))
        return IngestStatusResponse(code=code, statuses=statuses)

    def cache_age(self, code: str, kind: str) -> Optional[timedelta]:
        return _cache_age(code, kind)
