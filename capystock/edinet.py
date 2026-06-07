"""EDINET 大量保有報告書（5% rule）自動監控。

API 文件：https://disclosure2.edinet-fsa.go.jp/weee0020.aspx
- v2 需 Subscription-Key 參數 `Subscription-Key`（免費申請）
- docTypeCode 350 = 大量保有報告書、360 = 変更報告書

流程：
  list_reports(date) → 回傳當日所有文件 metadata
  filter_watchlist(metas, codes) → 過濾 watchlist 內的股票代號
  fetch_since(days) → 回掃 N 日（週末/假日跳過）

回傳 dict 結構：
  {
    "doc_id": str, "submit_date": str, "sec_code": str(4碼),
    "filer_name": str, "issuer_name": str,
    "doc_type_code": "350" | "360",
    "doc_description": str,
    "pdf_url": str,
  }
"""
from __future__ import annotations

import csv
import io
import json
import time
import zipfile
from datetime import date, datetime, timedelta
from typing import Optional

import requests

from . import config

_API_BASE = "https://api.edinet-fsa.go.jp/api/v2"
DAILY_DIR = config.EDINET_CACHE_DIR / "daily"  # 全市場每日申報快取（三盤第一盤輸入來源）
_DOC_TYPE_LARGE_HOLDING = {"350", "360"}  # 大量保有 / 変更報告書
_EDINET_CODE_LIST_URL = (
    "https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip"
)
_last_request_at = 0.0
_code_map: Optional[dict[str, str]] = None  # edinetCode -> 4碼證券代號


def _throttle() -> None:
    global _last_request_at
    gap = time.time() - _last_request_at
    if gap < 1.0:
        time.sleep(1.0 - gap)
    _last_request_at = time.time()


def _get(path: str, params: dict) -> Optional[dict]:
    if not config.EDINET_API_KEY:
        return None
    _throttle()
    params = dict(params)
    params["Subscription-Key"] = config.EDINET_API_KEY
    try:
        r = requests.get(
            f"{_API_BASE}{path}",
            params=params,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.REQUEST_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def _code_map_path():
    return config.EDINET_CACHE_DIR / "edinet_code_map.csv"


def _load_code_map(force_refresh: bool = False) -> dict[str, str]:
    """下載 EDINET 官方 edinetCode → 証券コード 對照表並快取。"""
    global _code_map
    if _code_map is not None and not force_refresh:
        return _code_map
    config.EDINET_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _code_map_path()
    if force_refresh or not path.exists():
        try:
            r = requests.get(
                _EDINET_CODE_LIST_URL,
                headers={"User-Agent": config.USER_AGENT},
                timeout=60,
            )
            if r.status_code != 200:
                _code_map = {}
                return _code_map
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                csv_name = next((n for n in zf.namelist() if n.endswith(".csv")), None)
                if not csv_name:
                    _code_map = {}
                    return _code_map
                raw = zf.read(csv_name)
            # EDINET CSV 為 CP932 編碼
            text = raw.decode("cp932", errors="replace")
            path.write_text(text, encoding="utf-8")
        except Exception:
            _code_map = {}
            return _code_map

    mapping: dict[str, str] = {}
    text = path.read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(text))
    header = None
    for row in reader:
        if not row:
            continue
        if header is None and any("ＥＤＩＮＥＴコード" in c or "EDINETコード" in c or "ｺｰﾄﾞ" in c for c in row):
            header = row
            continue
        if header is None:
            # skip intro line
            continue
        # 欄位：ＥＤＩＮＥＴコード(0), 提出者種別(1), 上場区分(2), 連結の有無(3),
        #       資本金(4), 決算日(5), 提出者名(6), 提出者名（英字）(7),
        #       提出者名（ヨミ）(8), 所在地(9), 提出者業種(10),
        #       証券コード(11), 提出者法人番号(12)
        if len(row) < 12:
            continue
        edinet_code = row[0].strip()
        sec = row[11].strip()
        if edinet_code and sec and sec.isdigit():
            mapping[edinet_code] = sec[:4]
    _code_map = mapping
    return mapping


def list_reports(d: date) -> list[dict]:
    """列出指定日期的大量保有報告 + 変更報告書。"""
    data = _get("/documents.json", {
        "date": d.strftime("%Y-%m-%d"),
        "type": 2,  # 2 = 文件清單 + 提出書類情報
    })
    if not data or "results" not in data:
        return []
    code_map = _load_code_map()
    out: list[dict] = []
    for r in data["results"]:
        dtc = r.get("docTypeCode")
        if dtc not in _DOC_TYPE_LARGE_HOLDING:
            continue
        # secCode: "72030"（4 碼 + 種類 1 碼）；若空則用 issuerEdinetCode 對照
        sec = (r.get("secCode") or "").strip()
        sec4 = sec[:4] if len(sec) >= 4 else ""
        if not sec4:
            issuer_edinet = (r.get("issuerEdinetCode") or "").strip()
            if issuer_edinet:
                sec4 = code_map.get(issuer_edinet, "")
        out.append({
            "doc_id": r.get("docID", ""),
            "submit_date": r.get("submitDateTime", "")[:10],
            "sec_code": sec4,
            "filer_name": r.get("filerName", "") or "",
            "issuer_name": r.get("issuerEdinetCode", "") or "",
            "doc_type_code": dtc,
            "doc_description": r.get("docDescription", "") or "",
            "pdf_url": f"https://disclosure2.edinet-fsa.go.jp/WZEK0040.aspx?S100={r.get('docID','')}",
        })
    return out


def fetch_since(days: int = 7, codes: Optional[set[str]] = None) -> list[dict]:
    """回掃最近 N 日的大量保有報告。codes 為 watchlist 4 碼集合；None 表示全部。"""
    results: list[dict] = []
    today = date.today()
    for i in range(days):
        d = today - timedelta(days=i)
        # 週末 EDINET 通常無新件，但 API 仍可查；不特別跳過（文件可能延後公告）
        for meta in list_reports(d):
            if codes is None or meta["sec_code"] in codes:
                results.append(meta)
    # 新到舊
    results.sort(key=lambda x: x["submit_date"], reverse=True)
    return results


def daily_cache_path(d: date) -> "object":
    return DAILY_DIR / f"{d.strftime('%Y-%m-%d')}.json"


def backfill_daily(days: int = 7, refetch_recent: int = 3) -> dict:
    """回補「全市場」EDINET 每日大量保有/変更報告書到 `data/cache/edinet/daily/`。

    這是三盤濾網第一盤的輸入來源（candidates 由此而來）。供排程每日呼叫，
    寫進容器的 named volume → 解決「git pull / 重建不會帶 daily 快取」的缺口。

    參數：
      days：回看最近 N 個日曆日。
      refetch_recent：最近 N 日即使檔案已存在也重抓（晚報的変更報告會補進近幾日）。

    防呆：
      - 無 EDINET_API_KEY → 直接回報，不動既有檔。
      - 某日 API 回空但既有檔已有內容 → 視為暫時失敗，**不用空蓋掉**既有檔。
    """
    if not config.EDINET_API_KEY:
        return {"ok": False, "error": "EDINET_API_KEY 未設定", "days_fetched": 0, "reports_written": 0}

    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()
    days_fetched = 0
    reports_written = 0
    skipped = 0
    for i in range(days):
        d = today - timedelta(days=i)
        path = daily_cache_path(d)
        if path.exists() and i >= refetch_recent:
            skipped += 1
            continue
        reports = list_reports(d)
        if not reports and path.exists():
            # API 暫時失敗 / 限流；保留既有內容，不覆寫
            skipped += 1
            continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(reports, f, ensure_ascii=False)
        days_fetched += 1
        reports_written += len(reports)
    return {
        "ok": True,
        "days_fetched": days_fetched,
        "reports_written": reports_written,
        "skipped": skipped,
    }


def format_report(r: dict) -> str:
    kind = "大量保有" if r["doc_type_code"] == "350" else "變更報告"
    return (
        f"[{r['submit_date']}] {r['sec_code']} {kind}："
        f"{r['filer_name']} 申報 "
        f"({r['doc_description'] or '詳見 PDF'}) "
        f"{r['pdf_url']}"
    )
