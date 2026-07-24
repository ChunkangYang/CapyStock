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

# PoC 預設代碼：大型權值股 + 中型股，混合驗證
POC_CODES = ["7203", "6758", "9984", "8035", "6367"]

CLOUD_CACHE_DIR = ROOT / "data" / "cloud-cache"


def fetch_margin(code: str, market_df=None) -> dict:
    """從 JPX 官方週末信用残（全市場 PDF，已於 run 起始預載為 market_df）切出個股，
    寫 cloud-cache 並與既有歷史合併。

    改用 JPX 而非 irbank 的原因：irbank 走 Cloudflare，對 GitHub Actions 的
    datacenter IP 回 403（本地住宅 IP 正常），導致雲端信用残長期抓不到。JPX 為
    官方 bulk 來源、不擋 datacenter IP，一次下載即涵蓋全市場。

    單位：JPX 原始為「株」，此處 ÷1000 轉「千株」與既有 CSV / analyzer 對齊。

    回傳 ok 語意：
      - market_df 為 None（JPX 下載/解析整批失敗）→ ok=False（會累積觸發熔斷，讓 run 紅燈）
      - code 不在 PDF（該股無信用交易）→ ok=True rows=<既有>，note=no_margin（非失敗，不觸發熔斷）
      - 正常 → ok=True 並寫檔
    """
    try:
        import pandas as pd

        if market_df is None or market_df.empty:
            return {"ok": False, "source": "jpx", "rows": 0, "error": "jpx_unavailable"}

        sub = market_df[market_df["code"] == str(code)]
        if sub.empty:
            # 該股無信用交易資料屬正常，不算失敗（否則會誤觸連續失敗熔斷）
            return {"ok": True, "source": "jpx", "rows": 0, "note": "no_margin"}

        fresh = sub[["week", "margin_long", "margin_short"]].copy()
        # 株 → 千株
        fresh["margin_long"] = fresh["margin_long"] / 1000.0
        fresh["margin_short"] = fresh["margin_short"] / 1000.0
        # ratio 與歷史 irbank 列一致採「信用倍率 = 融資買残 / 融券売残」
        # （JPX 原始 ratio 為 short/long，語意相反；ratio 未被 analyzer 使用，
        #  此處重算僅為同序列語意一致）。融券残為 0 時倍率無定義 → NaN。
        import numpy as np
        fresh["ratio"] = np.where(
            fresh["margin_short"] > 0,
            (fresh["margin_long"] / fresh["margin_short"]).round(2),
            np.nan,
        )
        fresh["week"] = pd.to_datetime(fresh["week"], errors="coerce")
        fresh = fresh.dropna(subset=["week"])

        out = CLOUD_CACHE_DIR / f"{code}_margin.csv"
        if out.exists():
            try:
                existing = pd.read_csv(out)
                existing["week"] = pd.to_datetime(existing["week"], format="mixed", errors="coerce")
                existing = existing.dropna(subset=["week"])
                combined = pd.concat([existing, fresh], ignore_index=True)
                combined = combined.drop_duplicates(subset=["week"], keep="last").sort_values("week")
                fresh = combined
            except Exception:
                pass
        fresh.to_csv(out, index=False)
        return {"ok": True, "source": "jpx", "rows": len(fresh), "path": str(out.relative_to(ROOT))}
    except Exception as e:
        return {"ok": False, "source": "jpx", "rows": 0, "error": str(e)}


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


_PRICE_HEADER = ["date", "open", "high", "low", "close", "adj close", "volume", "dividends", "stock splits"]
_PRICE_TRIM_ROWS = 260  # 約 1 年交易日，讓每日 git diff 只有 1-2 行


def _reshape_price_for_cloud(df, code: str):
    """把 yfinance 單檔 DataFrame reshape 成與既有 cloud-cache 檔完全相同的 9 欄 header。"""
    import pandas as pd

    if df is None or df.empty:
        return None
    out = df.reset_index()
    out.columns = [str(c).lower() for c in out.columns]
    # yfinance reset_index 後可能叫 'date' 或 'datetime'
    if "datetime" in out.columns and "date" not in out.columns:
        out = out.rename(columns={"datetime": "date"})
    if "date" not in out.columns:
        return None
    out["date"] = out["date"].astype(str).str.slice(0, 10)
    for col in _PRICE_HEADER:
        if col not in out.columns:
            out[col] = 0.0  # 缺 dividends / stock splits / adj close 補 0.0
    out = out[_PRICE_HEADER]
    out = out.dropna(subset=["close"])
    return out if len(out) else None


def _merge_and_trim_price(code: str, fresh) -> int:
    """增量合併既有 CSV：concat → dedupe by date → sort → trim 最後 260 列。寫檔，回傳列數。"""
    import pandas as pd

    out_path = CLOUD_CACHE_DIR / f"{code}_price.csv"
    combined = fresh
    if out_path.exists():
        try:
            existing = pd.read_csv(out_path)
            existing["date"] = existing["date"].astype(str).str.slice(0, 10)
            combined = pd.concat([existing, fresh], ignore_index=True)
        except Exception:
            combined = fresh
    combined = combined.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    combined = combined.tail(_PRICE_TRIM_ROWS).reset_index(drop=True)
    combined.to_csv(out_path, index=False)
    return len(combined)


def fetch_price_bulk_cloud(codes: list[str], batch_size: int = 100) -> list[dict]:
    """價格 bulk 模式：yf.download 一次抓多檔（每批 100），增量合併進 cloud-cache。

    與 fetch_price 不同：批次抓取（5–10 分鐘跑完全市場，不需 batch chaining）、
    增量合併只留最後 260 列（避免 6mo 全檔覆寫造成 repo 膨脹）。
    既有檔不存在 → 該檔改用 period="6mo" 單獨初始化。
    回傳與 fetch_price 相同形狀的 result dict list。
    """
    import time as _time

    import pandas as pd
    import yfinance as yf

    results: list[dict] = []
    for batch_start in range(0, len(codes), batch_size):
        batch = codes[batch_start:batch_start + batch_size]
        tickers = [f"{c}.T" for c in batch]
        try:
            hist = yf.download(
                tickers, period="7d", auto_adjust=False,
                group_by="ticker", threads=True, progress=False,
            )
        except Exception as e:
            for c in batch:
                results.append({"ok": False, "source": "yfinance", "rows": 0,
                                "code": c, "kind": "price", "error": f"download: {e}"})
            _time.sleep(1.0)
            continue

        multi = isinstance(hist.columns, pd.MultiIndex)
        lvl0 = set(hist.columns.get_level_values(0)) if multi else set()

        for c, ticker in zip(batch, tickers):
            out_path = CLOUD_CACHE_DIR / f"{c}_price.csv"
            try:
                if not out_path.exists():
                    # 初始化：單檔抓 6mo
                    init = yf.Ticker(ticker).history(period="6mo", auto_adjust=False)
                    fresh = _reshape_price_for_cloud(init, c)
                else:
                    if multi:
                        df_t = hist[ticker].dropna(how="all") if ticker in lvl0 else None
                    else:
                        df_t = hist  # 單 ticker，flat columns
                    fresh = _reshape_price_for_cloud(df_t, c) if df_t is not None else None

                if fresh is None or fresh.empty:
                    results.append({"ok": False, "source": "yfinance", "rows": 0,
                                    "code": c, "kind": "price", "error": "empty"})
                    continue
                rows = _merge_and_trim_price(c, fresh)
                try:
                    rel = str(out_path.relative_to(ROOT))
                except ValueError:
                    rel = str(out_path)
                results.append({"ok": True, "source": "yfinance", "rows": rows,
                                "code": c, "kind": "price", "path": rel})
            except Exception as e:
                results.append({"ok": False, "source": "yfinance", "rows": 0,
                                "code": c, "kind": "price", "error": str(e)})
        _time.sleep(1.0)

    return results


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
    ap.add_argument("--price-bulk", action="store_true",
                    help="price 改走 yf.download 批次模式（一次跑完全市場，不需 batch chaining）")
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
    # price-bulk：price 從 per-code 迴圈移除，改走批次函式（margin 迴圈照舊不動）
    price_bulk = args.price_bulk and "price" in kinds
    if price_bulk:
        kinds = [k for k in kinds if k != "price"]
    CLOUD_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # margin 走 JPX 全市場 PDF：整個 run 只下載/解析一次，per-code 迴圈再切片。
    # 下載失敗 → market_margin_df=None → 每檔 ok=False → 觸發熔斷讓 run 紅燈。
    market_margin_df = None
    if "margin" in kinds:
        try:
            from capystock.ingest.jpx_margin import fetch_market_margin
            market_margin_df = fetch_market_margin(force=True)
            print(f"[cloud_fetch] JPX market margin loaded: {len(market_margin_df)} rows, "
                  f"{market_margin_df['code'].nunique()} codes")
        except Exception as e:
            print(f"[cloud_fetch] JPX market margin load FAILED: {type(e).__name__}: {e}")
            market_margin_df = None

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
                    r = fetch_margin(code, market_margin_df)
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

    # 價格 bulk 模式：批次 yf.download 全部 codes（不走 per-code 迴圈）
    if price_bulk:
        t0 = time.time()
        bulk_results = fetch_price_bulk_cloud(codes)
        report["results"].extend(bulk_results)
        ok_n = sum(1 for r in bulk_results if r["ok"])
        print(f"  [price-bulk] {len(codes)} 檔 → ok={ok_n} fail={len(bulk_results) - ok_n} "
              f"t={round(time.time() - t0, 1)}s")

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

    # 非零退出讓 Actions 顯示紅燈：
    #   1) 全失敗（ok==0）
    #   2) 觸發連續失敗熔斷 —— 即使 EDINET 等其他 kind 有 ok，也不得被遮成綠燈
    #      （舊 bug：margin 全掛 + EDINET ok=1 → ok!=0 → 假成功）
    if report["summary"]["ok"] == 0 or report["summary"].get("aborted") == "consecutive_failures":
        sys.exit(2)


if __name__ == "__main__":
    main()
