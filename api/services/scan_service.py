import csv
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from api.deps import DATA_DIR
from api.schemas.scan import DividendScanRow, SignalScanRow
from api.services.dividend_service import get_fundamental_report
from api.services.signal_service import analyze_one, get_edinet_events

SCAN_SNAPSHOTS_DIR = DATA_DIR / "scan_snapshots"
CACHE_DIR = DATA_DIR / "cache"


def snapshot_path(kind: str, date_str: str) -> Path:
    return SCAN_SNAPSHOTS_DIR / f"{kind}_{date_str}.parquet"


def error_path(kind: str, date_str: str) -> Path:
    return SCAN_SNAPSHOTS_DIR / f"_errors_{kind}_{date_str}.csv"


def compute_score(result, events, include_technical: bool = True) -> int:
    """計算訊號評分：accumulation +3, exit -2, stop_loss -3, EDINET 350 +2, 360 +1, technical_score"""
    score = 0

    for alert in result.alerts:
        if alert.alert_type == "accumulation":
            score += 3
        elif alert.alert_type == "exit":
            score -= 2
        elif alert.alert_type == "stop_loss":
            score -= 3

    # EDINET: 350 新規 +2, 360 变更 +1
    for event in events:
        doc_type_code = event.get("doc_type_code", "")
        if doc_type_code == "350":
            score += 2
        elif doc_type_code == "360":
            score += 1

    if include_technical:
        score += int(round(getattr(result, "technical_score", 0.0)))

    return score


# NOTE: _signal_cache_path / _is_signal_scanned_today / _write_signal_cache 已移除。
# 過去用 cache/{code}_signal_scan.json 當「今日已掃描」的 skip-cache 機制，
# 但這層 cache 跨日 / 跨資料更新後會 stale，是「同檔股票在不同 tab 顯示不一致」
# 的元兇之一。改為單一 source of truth = data/cache/*.csv，每次重算。
# 既有的 *_signal_scan.json 檔案可由使用者手動清理（規則允許改名為 DELETE_ prefix）。


def _load_edinet_by_code() -> dict[str, list]:
    """一次性取得 3 天內的所有 EDINET 報告，建立 code → events 快篩表。"""
    try:
        from capystock import edinet, config
        if not config.EDINET_API_KEY:
            return {}
        all_edinet_reports = edinet.fetch_since(days=3)
        edinet_by_code: dict[str, list] = {}
        for report in all_edinet_reports:
            sec_code = str(report.get("securities_code", "")).zfill(4)
            edinet_by_code.setdefault(sec_code, []).append({
                "date": report.get("submit_date"),
                "filer": report.get("filer_name"),
                "doc_type_code": report.get("doc_type_code"),
                "pdf_url": report.get("pdf_url"),
            })
        return edinet_by_code
    except Exception:
        return {}


def run_signals_scan(
    universe: list[dict],
    clock: Optional[date] = None,
    include_technical: bool = True,
    progress_callback: Optional[callable] = None,
    snapshot_callback: Optional[callable] = None,
    max_workers: int = 16,
) -> tuple[list[SignalScanRow], list[dict]]:
    """掃描所有股票的訊號 — 永遠從 data/cache/*.csv 即時重算，無 stale cache。

    Single source of truth：data/cache/*.csv（cloud-sync 寫入）
    Single compute path：analyze_one（cache-first，每檔 ~16ms）

    過往的 _is_signal_scanned_today / _write_signal_cache 跨日 stale 機制已移除，
    fetch_price 改為 cache-first 後，3700 檔並行 ~2-3 秒，沒必要靠跨日 skip-cache 加速。
    watchlist start_price 在這裡注入，與 /signals/{code} 共用同一 compute path。
    """
    if clock is None:
        clock = date.today()
    now = datetime.combine(clock, datetime.min.time())

    # watchlist：用於對裡面的股票傳 start_price，與 /signals/{code} 對齊
    try:
        from capystock import storage as _storage
        wl = _storage.load_watchlist()
    except Exception:
        wl = {}

    # 一次性 EDINET 查詢
    edinet_by_code = _load_edinet_by_code()

    rows: list[SignalScanRow] = []
    errors: list[dict] = []
    completed = 0
    _lock = threading.Lock()
    _snapshot_lock = threading.Lock()  # snapshot 寫入序列化

    def _process_one(entry: dict) -> tuple[Optional[SignalScanRow], Optional[dict]]:
        code = entry["code"]
        name = entry["name"]
        try:
            wl_entry = wl.get(code) if isinstance(wl, dict) else None
            start_price = wl_entry.get("start_price") if isinstance(wl_entry, dict) else None
            result = analyze_one(code, name=name, start_price=start_price)
            events = edinet_by_code.get(str(code).zfill(4), [])
            score = compute_score(result, events, include_technical=include_technical)

            row = SignalScanRow(
                code=code, name=name,
                latest_price=result.latest_price,
                has_accumulation=any(a.alert_type == "accumulation" for a in result.alerts),
                has_exit=any(a.alert_type == "exit" for a in result.alerts),
                has_stop_loss=any(a.alert_type == "stop_loss" for a in result.alerts),
                edinet_recent_count=len(events),
                score=score,
                generated_at=now,
            )
            return row, None
        except Exception as e:
            return None, {"code": code, "name": name, "error": str(e)}

    to_scan = universe

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, entry): entry for entry in to_scan}
        for future in as_completed(futures):
            row, err = future.result()
            with _lock:
                if row:
                    rows.append(row)
                if err:
                    errors.append(err)
                completed += 1
                curr = completed

            if progress_callback:
                progress_callback(curr)

            # 每完成 50 支更新一次快照
            if curr % 50 == 0 and snapshot_callback:
                with _snapshot_lock:
                    with _lock:
                        snap_rows = list(rows)
                        snap_errs = list(errors)
                    snapshot_callback(snap_rows, snap_errs)

    # 最終進度
    if progress_callback:
        progress_callback(len(universe))

    return rows, errors


def run_dividend_scan(universe: list[dict], clock: Optional[date] = None, progress_callback: Optional[callable] = None, snapshot_callback: Optional[callable] = None) -> tuple[list[DividendScanRow], list[dict]]:
    """掃描所有股票的基本面，邊掃邊存快照，回傳 (rows, errors)"""
    if clock is None:
        clock = date.today()

    rows = []
    errors = []
    now = datetime.combine(clock, datetime.min.time())

    for i, entry in enumerate(universe):
        code = entry["code"]
        name = entry["name"]

        try:
            result = analyze_one(code, name=name)  # 取最新價
            report = get_fundamental_report(code)

            if report is None:
                # 無基本面資料，skip
                errors.append({"code": code, "name": name, "error": "No fundamental report"})
                continue

            # 計算估算殖利率
            latest_dps = None
            dps_streak = 0
            payout_avg = None
            if report.metrics:
                for m in report.metrics:
                    if m.metric == "DPS":
                        latest_dps = float(m.score) if m.score not in ("N/A", "PASS", "WARN", "FAIL") else None
                    if m.metric == "Payout Ratio":
                        payout_avg = float(m.score) if m.score not in ("N/A", "PASS", "WARN", "FAIL") else None

            est_yield = None
            if latest_dps is not None and result.latest_price is not None and result.latest_price > 0:
                est_yield = latest_dps / result.latest_price

            # 信用残連續無減配日數 (簡化：沒有實際資料就用 0)
            dps_streak = 0

            # 自己資本比
            equity_ratio = None
            eps_growth = None
            if report.metrics:
                for m in report.metrics:
                    if m.metric == "Equity Ratio":
                        equity_ratio = float(m.score) if m.score not in ("N/A", "PASS", "WARN", "FAIL") else None
                    if m.metric == "EPS":
                        eps_growth = float(m.score) if m.score not in ("N/A", "PASS", "WARN", "FAIL") else None

            # 統計 pass/warn/fail
            pass_count = 0
            warn_count = 0
            fail_count = 0
            if report.metrics:
                for m in report.metrics:
                    if m.score == "PASS":
                        pass_count += 1
                    elif m.score == "WARN":
                        warn_count += 1
                    elif m.score == "FAIL":
                        fail_count += 1

            row = DividendScanRow(
                code=code,
                name=name,
                overall=report.overall,
                pass_count=pass_count,
                warn_count=warn_count,
                fail_count=fail_count,
                latest_dps=latest_dps,
                dps_streak_no_cut=dps_streak,
                est_yield=est_yield,
                payout_avg=payout_avg,
                equity_ratio_latest=equity_ratio,
                eps_growth=eps_growth,
                generated_at=now,
            )
            rows.append(row)

        except Exception as e:
            errors.append({"code": code, "name": name, "error": str(e)})

        # 每掃 50 檔就更新一次快照
        if (i + 1) % 50 == 0 and snapshot_callback:
            snapshot_callback(rows, errors)

        # 更新進度
        if progress_callback:
            progress_callback(i + 1)

    return rows, errors


def write_snapshot(kind: str, rows: list[SignalScanRow | DividendScanRow], date_str: str) -> Path:
    """寫 parquet 快照（存在則覆寫）"""
    SCAN_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # 轉換為 DataFrame
    df_dict = [r.model_dump() for r in rows]
    df = pd.DataFrame(df_dict)

    path = snapshot_path(kind, date_str)
    df.to_parquet(path, index=False)
    return path


def write_errors(kind: str, errors: list[dict], date_str: str) -> None:
    """寫失敗清單 CSV"""
    if not errors:
        return

    SCAN_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = error_path(kind, date_str)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "name", "error"])
        writer.writeheader()
        writer.writerows(errors)


def load_latest_snapshot(kind: str, date_str: Optional[str] = None) -> Optional[pd.DataFrame]:
    """讀取最新（或指定日期）快照"""
    if date_str is None:
        # 找最新的快照
        SCAN_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        parquets = sorted(SCAN_SNAPSHOTS_DIR.glob(f"{kind}_*.parquet"), reverse=True)
        if not parquets:
            return None
        path = parquets[0]
    else:
        path = snapshot_path(kind, date_str)

    if not path.exists():
        return None

    return pd.read_parquet(path)


def list_snapshots(kind: Optional[str] = None) -> list[dict]:
    """列出所有快照日期"""
    SCAN_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    snapshots = []
    for parquet_file in sorted(SCAN_SNAPSHOTS_DIR.glob("*.parquet"), reverse=True):
        name = parquet_file.stem
        if name.startswith("_"):
            continue
        parts = name.split("_", 1)
        if len(parts) != 2:
            continue
        file_kind, date_str = parts

        if kind and file_kind != kind:
            continue

        df = pd.read_parquet(parquet_file)
        snapshots.append({"date": date_str, "kind": file_kind, "rows": len(df), "path": str(parquet_file)})

    return snapshots


def load_universe(path: Optional[str] = None) -> list[dict]:
    """讀 universe.csv，回傳 [{code, name, market}, ...]"""
    if path is None:
        path = str(DATA_DIR / "universe.csv")

    df = pd.read_csv(path)
    return df.to_dict("records")
