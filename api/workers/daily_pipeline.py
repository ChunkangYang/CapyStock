"""每日通知管線。

流程：
  1. 確保今日 signals scan 已存在（沒有就現跑）
  2. analyze_watchlist → 收集 alerts
  3. process_realtime_alert(每個 critical alert)
  4. process_daily_digest(today)

Idempotent：重跑同日不會重發 digest（rule 內 last_run 控制），
realtime 由 24h dedupe 控制。
"""
from __future__ import annotations

from datetime import date as _date, datetime
from pathlib import Path
from typing import Optional


def _today_signals_exists(today: _date) -> bool:
    from api.services import scan_service
    p = scan_service.snapshot_path("signals", today.strftime("%Y-%m-%d"))
    return p.exists()


def _run_signals_scan(today: _date) -> int:
    from api.services import scan_service

    universe_path = "data/universe.csv"
    try:
        universe = scan_service.load_universe(universe_path)
    except Exception:
        return 0
    rows, errors = scan_service.run_signals_scan(universe, clock=today)
    scan_service.write_snapshot("signals", rows, today.strftime("%Y-%m-%d"))
    if errors:
        scan_service.write_errors("signals", errors, today.strftime("%Y-%m-%d"))
    return len(rows)


def _analyze_watchlist(today: _date) -> dict[str, list]:
    """組 code → alerts dict。"""
    try:
        from capystock import storage
        from api.services import signal_service
    except Exception:
        return {}
    out: dict[str, list] = {}
    try:
        wl = storage.load_watchlist()
    except Exception:
        return {}
    for code in wl.keys():
        try:
            res = signal_service.analyze_one(code, datetime.combine(today, datetime.min.time()))
            if res and res.alerts:
                out[code] = list(res.alerts)
        except Exception:
            continue
    return out


def run(
    today: Optional[_date] = None,
    dry_run: bool = False,
    notification_service=None,
) -> dict:
    """主入口。"""
    today = today or _date.today()
    summary = {
        "scan_rows": 0,
        "alerts_total": 0,
        "realtime_sent": 0,
        "digest_sent": 0,
        "scan_skipped": False,
    }

    if _today_signals_exists(today):
        summary["scan_skipped"] = True
    else:
        try:
            summary["scan_rows"] = _run_signals_scan(today)
        except Exception as e:
            summary["scan_error"] = str(e)

    alerts_by_code = _analyze_watchlist(today)
    summary["alerts_total"] = sum(len(v) for v in alerts_by_code.values())

    if notification_service is None:
        from api.services import notification_service as ns_module
        notification_service = ns_module.build_default_service()

    realtime_sent = 0
    for code, alerts in alerts_by_code.items():
        for a in alerts:
            sev = getattr(a, "severity", None) or (a.get("severity") if isinstance(a, dict) else "info")
            if sev != "critical":
                continue
            try:
                results = notification_service.process_realtime_alert(a, code, dry_run=dry_run)
                realtime_sent += sum(1 for r in results if r.ok)
            except Exception:
                continue
    summary["realtime_sent"] = realtime_sent

    try:
        digest_results = notification_service.process_daily_digest(
            today, dry_run=dry_run, alerts_by_code=alerts_by_code,
        )
        summary["digest_sent"] = sum(1 for r in digest_results if r.ok)
    except Exception as e:
        summary["digest_error"] = str(e)

    return summary


def main():
    print(run())


if __name__ == "__main__":
    main()
