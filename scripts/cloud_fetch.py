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
from capystock.ingest.jpx_margin import JpxMarginSource  # noqa: E402

# PoC 預設代碼：大型權值股 + 中型股，混合驗證
POC_CODES = ["7203", "6758", "9984", "8035", "6367"]

CLOUD_CACHE_DIR = ROOT / "data" / "cloud-cache"

_JPX_MARGIN = JpxMarginSource()


def fetch_margin(code: str) -> dict:
    """從 JPX 週次 PDF 取得信用残（全市場一次下載，不逐股爬蟲）。"""
    try:
        df = _JPX_MARGIN.fetch(code)
        if df.empty:
            return {"ok": False, "source": "jpx_margin", "rows": 0, "error": "empty"}
        out = CLOUD_CACHE_DIR / f"{code}_margin.csv"
        # append 既有歷史，去重
        import pandas as pd
        if out.exists():
            try:
                existing = pd.read_csv(out)
                df = pd.concat([existing, df], ignore_index=True).drop_duplicates("week", keep="last").sort_values("week")
            except Exception:
                pass
        df.to_csv(out, index=False)
        return {"ok": True, "source": "jpx_margin", "rows": len(df), "path": str(out.relative_to(ROOT))}
    except Exception as e:
        return {"ok": False, "source": "jpx_margin", "rows": 0, "error": str(e)}


def fetch_price(code: str) -> dict:
    """從 yfinance 抓股價，寫 cloud-cache。每次覆寫（yfinance 一次回完整歷史）。"""
    import yfinance as yf

    try:
        ticker = yf.Ticker(f"{code}.T")
        df = ticker.history(period="6mo", auto_adjust=False)
        if df.empty:
            return {"ok": False, "source": "yfinance", "rows": 0, "error": "empty"}
        df = df.reset_index()
        # 規一欄位名：與本地 cache 對齊
        df.columns = [c.lower() if isinstance(c, str) else c for c in df.columns]
        if "date" in df.columns:
            df["date"] = df["date"].astype(str).str.slice(0, 10)
        out = CLOUD_CACHE_DIR / f"{code}_price.csv"
        df.to_csv(out, index=False)
        return {"ok": True, "source": "yfinance", "rows": len(df), "path": str(out.relative_to(ROOT))}
    except Exception as e:
        return {"ok": False, "source": "yfinance", "rows": 0, "error": str(e)}


def fetch_edinet(days: int = 7, codes: list[str] | None = None) -> dict:
    """抓 EDINET 大量保有報告（>5% 持股申報）。不分股票，整批回掃 N 天。"""
    import os

    if not os.environ.get("EDINET_API_KEY"):
        return {"ok": False, "source": "edinet", "rows": 0, "error": "EDINET_API_KEY 未設定"}

    from capystock import edinet

    try:
        code_set = set(codes) if codes else None
        reports = edinet.fetch_since(days=days, codes=code_set)
        out = CLOUD_CACHE_DIR / "edinet_reports.json"
        # append + dedupe by (sec_code, doc_id-from-url, submit_date)
        existing = []
        if out.exists():
            try:
                existing = json.loads(out.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        merged = existing + reports
        seen = set()
        dedup = []
        for r in merged:
            key = (r.get("sec_code"), r.get("submit_date"), r.get("filer_name"), r.get("doc_type_code"))
            if key in seen:
                continue
            seen.add(key)
            dedup.append(r)
        dedup.sort(key=lambda x: x.get("submit_date", ""), reverse=True)
        out.write_text(json.dumps(dedup, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "source": "edinet", "rows": len(reports), "total_after_dedup": len(dedup),
                "path": str(out.relative_to(ROOT))}
    except Exception as e:
        return {"ok": False, "source": "edinet", "rows": 0, "error": str(e)}


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
    ap.add_argument("--kinds", default="margin,flow", help="margin / flow / price，可逗號組合；edinet 為整批回掃，需在 --edinet-days 指定天數")
    ap.add_argument("--limit", type=int, default=0, help=">0 時截斷代碼數（避免 Actions 超時）")
    ap.add_argument("--edinet-days", type=int, default=0, help=">0 時抓 EDINET 大量保有報告（回掃 N 日）")
    ap.add_argument("--offset", type=int, default=0, help="從 codes[offset] 開始（分批斷點續跑）")
    ap.add_argument("--batch-size", type=int, default=0, help=">0 時只處理這批 N 支")
    ap.add_argument("--time-limit", type=int, default=0, help=">0 時超過 N 秒後完成當前代碼即停（soft stop）")
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

    # 分批：先記錄完整總數，再切片
    total_universe = len(codes)
    batch_offset = args.offset
    if batch_offset > 0:
        codes = codes[batch_offset:]
    if args.batch_size > 0:
        codes = codes[: args.batch_size]

    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    CLOUD_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc)
    batch_label = f"offset={batch_offset} batch={len(codes)}" if args.batch_size else f"all={len(codes)}"
    print(f"[cloud_fetch] start ts={started.isoformat()} {batch_label} kinds={kinds}")

    report = {
        "started_utc": started.isoformat(),
        "codes_total": len(codes),
        "batch_offset": batch_offset,
        "universe_total": total_universe,
        "kinds": kinds,
        "results": [],
        "summary": {},
    }

    fail_streak = 0
    codes_done = 0
    time_exceeded = False
    for i, code in enumerate(codes, 1):
        # soft stop：完成上一支後才檢查時間
        if args.time_limit > 0 and (time.time() - started.timestamp()) > args.time_limit:
            print(f"[cloud_fetch] 時間限制 {args.time_limit}s 到達，停在 offset={batch_offset + i - 1}")
            time_exceeded = True
            break

        for kind in kinds:
            t0 = time.time()
            try:
                if kind == "margin":
                    r = fetch_margin(code)
                elif kind == "flow":
                    r = fetch_flow(code)
                elif kind == "price":
                    r = fetch_price(code)
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
            codes_done += 1
            continue
        # inner break（熔斷或時間）
        break
    else:
        codes_done = len(codes)

    # 額外：EDINET 整批模式（不依賴 codes 迴圈，因為是回掃日期）
    if args.edinet_days and args.edinet_days > 0:
        t0 = time.time()
        edinet_res = fetch_edinet(days=args.edinet_days, codes=codes if codes else None)
        edinet_res.update({"code": "*", "kind": "edinet", "elapsed_sec": round(time.time() - t0, 2)})
        report["results"].append(edinet_res)
        status = "OK" if edinet_res["ok"] else "FAIL"
        print(f"  [edinet days={args.edinet_days}] {status} rows={edinet_res.get('rows')} "
              f"t={edinet_res['elapsed_sec']}s"
              + (f"  err={edinet_res.get('error')}" if not edinet_res["ok"] else ""))

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

    # 寫入批次進度 state（供 Actions 決定是否觸發下一輪）
    if args.batch_size > 0 or args.offset > 0:
        next_offset = batch_offset + codes_done
        # 若因熔斷提早停，next_offset 停在實際跑完的位置
        if report["summary"].get("aborted") == "consecutive_failures":
            next_offset = batch_offset + codes_done
        batch_done = next_offset >= total_universe
        state = {
            "next_offset": next_offset,
            "total": total_universe,
            "batch_size": args.batch_size or len(codes),
            "done": batch_done,
            "updated_utc": ended.isoformat(),
        }
        state_path = CLOUD_CACHE_DIR / "_fetch_state.json"
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[cloud_fetch] state -> next_offset={next_offset}/{total_universe} done={batch_done}")

    # 全失敗時非零退出，讓 Actions 顯示紅燈
    if report["summary"]["ok"] == 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
