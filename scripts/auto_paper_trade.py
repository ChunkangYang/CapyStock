#!/usr/bin/env python
"""每日自動模擬交易 driver（GitHub Actions paper-trade.yml 呼叫）。

流程：
  1. `--materialize`：把 repo 內的 `data/cloud-cache/*` 複製成 `data/cache/*`
     （runner 沒有 data/cache，且服務層一律讀 data/cache — 不改程式碼路徑）
  2. `--backfill-edinet N`：補全市場 EDINET 每日申報（三盤第一盤的輸入，需 EDINET_API_KEY）
  3. 跑三盤濾網 → 口袋名單快照
  4. `auto_trade_service.run_daily()`：推進停損出場 → 依規則進場 → 寫帳本與當日 log
  5. 印出 Telegram 日報文字，並寫到 `data/auto_trade_log/latest_report.txt`

用法：
  python scripts/auto_paper_trade.py --materialize --backfill-edinet 7
  python scripts/auto_paper_trade.py --dry-run                 # 不寫檔，只看結果
  python scripts/auto_paper_trade.py --replay 2026-05-01:2026-07-18   # 歷史重放驗證策略
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capystock import config  # noqa: E402

CLOUD_CACHE = PROJECT_ROOT / "data" / "cloud-cache"
LOCAL_CACHE = PROJECT_ROOT / "data" / "cache"


def _emit_gh_output(key: str, value: str) -> None:
    """寫 GitHub Actions step output（本機執行時無此環境變數，直接略過）。"""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{key}={value}\n")


def materialize_cache() -> int:
    """cloud-cache → cache（runner 上沒有 data/cache；本地跑則是無害的覆寫更新）。"""
    if not CLOUD_CACHE.exists():
        print(f"[materialize] 找不到 {CLOUD_CACHE}，略過")
        return 0
    LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
    n = 0
    for src in CLOUD_CACHE.rglob("*"):
        if src.is_dir():
            continue
        dst = LOCAL_CACHE / src.relative_to(CLOUD_CACHE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    print(f"[materialize] 複製 {n} 檔 cloud-cache → cache")
    return n


def backfill_edinet(days: int) -> dict:
    from capystock import edinet
    if not config.EDINET_API_KEY:
        print("[edinet] EDINET_API_KEY 未設定 → 略過回補（第一盤將吃既有快取）")
        return {"skipped": True}
    r = edinet.backfill_daily(days=days, refetch_recent=3)
    print(f"[edinet] backfill_daily(days={days}) → {r}")
    return r


def scan_pocket(as_of: str | None = None) -> dict:
    from api.services import pocket_service
    t0 = time.time()
    result = pocket_service.scan_pocket_list(as_of=as_of)
    f = result["funnel"]
    print(f"[pocket] 候選 {f['candidates']} → 一盤 {f['gate1_continuity']} "
          f"→ 二盤 {f['gate2_cost']} → 口袋 {f['gate3_margin']}"
          f"（{round(time.time() - t0, 1)}s）")
    return result


def _write_report(text: str) -> Path:
    from api.services import auto_trade_service
    auto_trade_service.DAILY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = auto_trade_service.DAILY_LOG_DIR / "latest_report.txt"
    path.write_text(text, encoding="utf-8")
    return path


def run_once(as_of: date | None, dry_run: bool, pocket_result: dict | None) -> dict:
    from api.services import auto_trade_service
    log = auto_trade_service.run_daily(as_of=as_of, pocket_result=pocket_result, dry_run=dry_run)
    report = auto_trade_service.format_report(log)
    print("\n" + report + "\n")
    if not dry_run:
        _write_report(report)
    return log


def replay(span: str, dry_run: bool) -> None:
    """歷史重放：用「當前」口袋名單快照 + 各日收盤逐日推進，驗證策略與程式流程。

    注意：EDINET/margin 資料無法還原到過去某日的狀態，所以第一/三盤條件用的是
    目前快照（有前視偏差）。這是「程式流程與績效量級」的煙霧測試，不是嚴謹回測。
    """
    from api.services import auto_trade_service, pocket_service
    a, _, b = span.partition(":")
    d0 = datetime.strptime(a, "%Y-%m-%d").date()
    d1 = datetime.strptime(b, "%Y-%m-%d").date() if b else date.today()
    snapshot = pocket_service.latest_snapshot() or {}
    print(f"[replay] {d0} → {d1}（口袋名單快照 {snapshot.get('generated_at')}，"
          f"{len(snapshot.get('pocket', []))} 檔）")
    d = d0
    while d <= d1:
        if d.weekday() < 5:  # 只在平日推進
            log = auto_trade_service.run_daily(as_of=d, pocket_result=snapshot, dry_run=dry_run)
            if log["opened"] or log["closed"]:
                print(f"  {d} 進 {len(log['opened'])} 出 {len(log['closed'])} "
                      f"權益 ¥{round(log['equity_jpy']):,}")
        d += timedelta(days=1)
    s = auto_trade_service.summary()
    print(f"\n[replay] 結束權益 ¥{round(s['equity_jpy']):,}（報酬 {s['total_return_pct']:.2%}）"
          f"｜持倉 {s['open_count']}｜已出場 {s['closed_count']}"
          f"｜勝率 {('%.0f%%' % (s['win_rate'] * 100)) if s['win_rate'] is not None else '—'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="每日自動模擬交易（三盤進場 + 棘輪停損出場）")
    ap.add_argument("--materialize", action="store_true", help="先把 cloud-cache 複製到 data/cache")
    ap.add_argument("--backfill-edinet", type=int, default=0, help="回補 EDINET 每日申報 N 天（0=不做）")
    ap.add_argument("--no-scan", action="store_true", help="不重跑三盤，直接用最新快照")
    ap.add_argument("--dry-run", action="store_true", help="不寫帳本/log，只印結果")
    ap.add_argument("--as-of", default="", help="指定交易日 YYYY-MM-DD（預設今天）")
    ap.add_argument("--replay", default="", help="歷史重放 YYYY-MM-DD:YYYY-MM-DD")
    ap.add_argument("--skip-if-logged", action="store_true",
                    help="當日（JST）已有交易 log 就跳過（cloud-fetch 觸發 + 保險排程可能重複觸發）")
    ap.add_argument("--require-fetch-done", action="store_true",
                    help="cloud-fetch 分批鏈尚未跑完（_fetch_state.json done=false）就不交易")
    args = ap.parse_args()

    if args.require_fetch_done and not args.replay:
        state = PROJECT_ROOT / "data" / "cloud-cache" / "_fetch_state.json"
        if state.exists():
            import json
            try:
                done = json.loads(state.read_text(encoding="utf-8")).get("done", True)
            except (OSError, ValueError):
                done = True
            if not done:
                print("[skip] cloud-fetch 分批鏈尚未完成（margin 資料不齊）→ 等鏈跑完會自動觸發交易")
                _emit_gh_output("paper_trade_skipped", "true")
                return 0

    if args.skip_if_logged and not args.replay:
        from api.services import auto_trade_service
        d = (datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of
             else auto_trade_service.jst_today())
        if auto_trade_service.read_daily_log(d) is not None:
            print(f"[skip] {d} 已有交易 log → 本次跳過（要重跑請用 --force / dispatch force=true）")
            _emit_gh_output("paper_trade_skipped", "true")
            return 0

    if args.materialize:
        materialize_cache()
    if args.backfill_edinet:
        backfill_edinet(args.backfill_edinet)

    if args.replay:
        replay(args.replay, args.dry_run)
        return 0

    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else None
    pocket_result = None
    if not args.no_scan:
        pocket_result = scan_pocket()
        if not args.dry_run:
            from api.services import pocket_service
            pocket_service.write_snapshot(pocket_result)

    log = run_once(as_of, args.dry_run, pocket_result)
    return 0 if log else 1


if __name__ == "__main__":
    raise SystemExit(main())
