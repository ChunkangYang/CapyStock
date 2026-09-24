#!/usr/bin/env python
"""每日海龜投資法模擬交易 driver（供 `.github/workflows/paper-trade-turtle.yml` 呼叫）。

流程（比照 `scripts/auto_paper_trade.py` 的舊模型 driver 風格，但完全獨立）：
  1. `--materialize`：把 repo 內的 `data/cloud-cache/*` 複製成 `data/cache/*`
     （runner 沒有 data/cache，服務層讀 data/cache）
  2. `turtle_trade_service.run_daily()`：出場 → 金字塔加碼 → 新突破進場 → 回撤節流
     → 寫獨立帳本（`data/ledgers/auto-turtle.json`）與當日 log
     （`data/auto_trade_log_turtle/YYYY-MM-DD.json`）

用法：
  python scripts/run_turtle_trade.py --materialize
  python scripts/run_turtle_trade.py --dry-run                 # 不寫檔，只看結果
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CLOUD_CACHE = PROJECT_ROOT / "data" / "cloud-cache"
LOCAL_CACHE = PROJECT_ROOT / "data" / "cache"


def _emit_gh_output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{key}={value}\n")


def materialize_cache() -> int:
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


def main() -> int:
    ap = argparse.ArgumentParser(description="每日海龜投資法模擬交易（55 日突破進場，20 日突破/停損出場）")
    ap.add_argument("--materialize", action="store_true", help="先把 cloud-cache 複製到 data/cache")
    ap.add_argument("--dry-run", action="store_true", help="不寫帳本/log，只印結果")
    ap.add_argument("--as-of", default="", help="指定交易日 YYYY-MM-DD（預設今天）")
    ap.add_argument("--skip-if-logged", action="store_true",
                    help="當日（JST）已有交易 log 就跳過")
    args = ap.parse_args()

    from api.services import turtle_trade_service as tts

    if args.skip_if_logged:
        d = (datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of
             else tts.jst_today())
        if tts.read_daily_log(d) is not None:
            print(f"[skip] {d} 已有交易 log → 本次跳過")
            _emit_gh_output("turtle_trade_skipped", "true")
            return 0

    if args.materialize:
        materialize_cache()

    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else None
    log = tts.run_daily(as_of=as_of, dry_run=args.dry_run)

    opened = log.get("opened") or []
    closed = log.get("closed") or []
    print(f"\n[turtle] 海龜模擬交易 {log['date']}")
    print(f"權益 ¥{round(log.get('equity_jpy', 0)):,}（現金 ¥{round(log.get('cash_jpy', 0)):,}，"
          f"未實現 ¥{round(log.get('unrealized_pnl_jpy', 0)):,}）"
          + ("｜節流中（unit_risk_pct 減半）" if log.get("throttled") else ""))
    print(f"今日新增 {len(opened)} unit：" +
          "、".join(f"{o['code']}({o['action']}) {o['shares']}股@¥{o['entry_price']}" for o in opened)
          if opened else "今日無新增 unit")
    print(f"今日出場 {len(closed)} unit：" +
          "、".join(f"{c['code']} @¥{c['exit_price']}（{c['exit_reason']}）" for c in closed)
          if closed else "今日無出場")

    return 0 if log else 1


if __name__ == "__main__":
    raise SystemExit(main())
