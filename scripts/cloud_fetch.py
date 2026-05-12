"""Cloud Fetch PoC — 在 GitHub Actions runner 上執行批量抓取。

驗證目標：
  1. yahoo finance JP / minkabu / JPX 在 Azure IP 上能否正常抓取
  2. 全流程耗時與穩定性

輸出：
  - data/cloud-cache/{code}_margin.csv
  - data/cloud-cache/{code}_flow.csv
  - data/cloud-cache/_fetch_report.json  (本次抓取摘要)

執行：
  python scripts/cloud_fetch.py            # 預設 PoC 5 檔
  python scripts/cloud_fetch.py --all      # 讀 data/universe.csv 全市場
  python scripts/cloud_fetch.py --codes 7203,6758
  python scripts/cloud_fetch.py --kinds margin  # 只抓信用残
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# 確保 repo root 在 import path 上
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from capystock import config  # noqa: E402
from capystock.ingest.jpx_flow import JpxFlowSource  # noqa: E402
from capystock.ingest.minkabu_margin import MinkabuMarginSource  # noqa: E402
from capystock.ingest.yahoo_jp_margin import YahooJpMarginSource  # noqa: E402

# PoC 預設代碼：大型權值股 + 中型股，混合驗證
POC_CODES = ["7203", "6758", "9984", "8035", "6367"]

CLOUD_CACHE_DIR = ROOT / "data" / "cloud-cache"

_MARGIN_SOURCES = [YahooJpMarginSource(), MinkabuMarginSource()]


def fetch_margin(code: str) -> dict:
    """嘗試所有 margin 來源，第一個成功即停。"""
    errors = []
    for src in _MARGIN_SOURCES:
        try:
            df = src.fetch(code)
            if df.empty:
                errors.append(f"{src.name}: empty")
                continue
            out = CLOUD_CACHE_DIR / f"{code}_margin.csv"
            df.to_csv(out, index=False)
            return {"ok": True, "source": src.name, "rows": len(df), "path": str(out.relative_to(ROOT))}
        except Exception as e:
            errors.append(f"{src.name}: {e}")
    return {"ok": False, "source": "none", "rows": 0, "error": "; ".join(errors)}


def fetch_flow(code: str) -> dict:
    """JPX flow 每次只回當週一筆；append 到既有 cloud-cache CSV 並去重，雲端自己累積歷史。"""
    import pandas as pd

    try:
        df = JpxFlowSource().fetch(code)
        if df.empty:
            return {"ok": False, "source": "jpx_flow", "rows": 0, "error": "empty"}
        out = CLOUD_CACHE_DIR / f"{code}_flow.csv"
        appended = False
        if out.exists():
            try:
                existing = pd.read_csv(out)
                df_merged = pd.concat([existing, df], ignore_index=True)
                date_col = "date" if "date" in df_merged.columns else ("week" if "week" in df_merged.columns else None)
                if date_col:
                    df_merged = df_merged.drop_duplicates(date_col, keep="last").sort_values(date_col)
                df = df_merged
                appended = True
            except Exception:
                pass  # 既有 CSV 壞了就直接覆寫
        df.to_csv(out, index=False)
        return {
            "ok": True, "source": "jpx_flow", "rows": len(df),
            "path": str(out.relative_to(ROOT)),
            "appended": appended,
        }
    except Exception as e:
        return {"ok": False, "source": "jpx_flow", "rows": 0, "error": str(e)}


def load_watchlist_codes() -> list[str]:
    p = ROOT / "data" / "watchlist.json"
    if not p.exists():
        return []
    wl = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(wl, list):
        return [str(item.get("code", "")).strip() for item in wl if item.get("code")]
    return [str(k).strip() for k in wl.keys()]


def load_universe_codes() -> list[str]:
    p = ROOT / "data" / "universe.csv"
    codes = []
    with p.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            c = (row.get("code") or "").strip()
            if c:
                codes.append(c)
    return codes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", help="逗號分隔代碼，覆蓋預設 PoC 清單")
    ap.add_argument("--all", action="store_true", help="抓 universe.csv 全部")
    ap.add_argument("--watchlist", action="store_true", help="抓 data/watchlist.json 內所有股票")
    ap.add_argument("--kinds", default="margin,flow", help="margin / flow / margin,flow")
    ap.add_argument("--limit", type=int, default=0, help=">0 時截斷代碼數（避免 Actions 超時）")
    args = ap.parse_args()

    if args.all:
        codes = load_universe_codes()
    elif args.watchlist:
        codes = load_watchlist_codes()
    elif args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        codes = POC_CODES

    if args.limit > 0:
        codes = codes[: args.limit]

    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    CLOUD_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc)
    print(f"[cloud_fetch] start ts={started.isoformat()} codes={len(codes)} kinds={kinds}")

    report = {
        "started_utc": started.isoformat(),
        "codes_total": len(codes),
        "kinds": kinds,
        "results": [],
        "summary": {},
    }

    fail_streak = 0
    for i, code in enumerate(codes, 1):
        for kind in kinds:
            t0 = time.time()
            try:
                if kind == "margin":
                    r = fetch_margin(code)
                elif kind == "flow":
                    r = fetch_flow(code)
                else:
                    r = {"ok": False, "error": f"unknown kind {kind}", "source": "n/a", "rows": 0}
            except Exception as e:
                r = {"ok": False, "error": f"{type(e).__name__}: {e}", "source": "exception", "rows": 0}
                traceback.print_exc()
            elapsed = round(time.time() - t0, 2)
            r.update({"code": code, "kind": kind, "elapsed_sec": elapsed})
            report["results"].append(r)
            status = "OK" if r["ok"] else "FAIL"
            print(f"  [{i}/{len(codes)}] {code} {kind:6s} {status:4s} src={r.get('source')} rows={r.get('rows')} t={elapsed}s"
                  + (f"  err={r.get('error')}" if not r["ok"] else ""))

            # 連續失敗熔斷（避免被擋還繼續打 100 檔）
            fail_streak = 0 if r["ok"] else fail_streak + 1
            if fail_streak >= 10:
                print(f"[cloud_fetch] 連續 {fail_streak} 次失敗，中止以節省 Actions 額度")
                report["summary"]["aborted"] = "consecutive_failures"
                break
        else:
            continue
        break

    ended = datetime.now(timezone.utc)
    total_ok = sum(1 for r in report["results"] if r["ok"])
    report["ended_utc"] = ended.isoformat()
    report["elapsed_sec"] = round((ended - started).total_seconds(), 1)
    report["summary"].update({
        "ok": total_ok,
        "fail": len(report["results"]) - total_ok,
        "total": len(report["results"]),
    })

    report_path = CLOUD_CACHE_DIR / "_fetch_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[cloud_fetch] done {report['summary']} elapsed={report['elapsed_sec']}s")
    print(f"[cloud_fetch] report -> {report_path.relative_to(ROOT)}")

    # 全失敗時非零退出，讓 Actions 顯示紅燈
    if report["summary"]["ok"] == 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
