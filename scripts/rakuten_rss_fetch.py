"""樂天 RSS 個股日頻信用残匯出腳本。

前提：
  1. Windows + Excel (Microsoft Office)
  2. マーケットスピード II 安裝完成並登入
  3. 樂天 RSS 利用權限已開通
  4. pip install pywin32 pandas

原理：
  RSS 是 Excel 的 RTD 函數，本身沒有 REST API。本腳本透過 win32com
  自動化開啟 Excel → 寫入 RSS 公式 → 等待 RTD 推送資料 → 讀回儲存格 → 寫 CSV。

輸出：
  - data/cache/{code}_margin_daily.csv   每股日頻信用残
    欄位：date, margin_long, margin_short, ratio
  - data/cache/_rakuten_rss_report.json  本次匯出摘要

執行：
  python scripts/rakuten_rss_fetch.py --codes 7203,6758,9984
  python scripts/rakuten_rss_fetch.py --watchlist
  python scripts/rakuten_rss_fetch.py --all

注意：
  - マーケットスピード II 必須在前景執行（最小化也可，但不能關閉）
  - 每檔股票 RTD 推送需 1-3 秒首次穩定，腳本內建等待
  - Excel 會在背景自動開關，請勿在執行中手動關閉
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "data" / "cache"
REPORT_PATH = OUT_DIR / "_rakuten_rss_report.json"

# RSS 函數對照表 (RssMarginVal 取信用残)
# 樂天 RSS 信用残相關欄位（看 マケスピ II 公式說明書）：
RSS_MARGIN_FIELDS = {
    "margin_long": "信用買残",       # 千株
    "margin_short": "信用売残",      # 千株
    "margin_long_chg": "信用買残前週比",
    "margin_short_chg": "信用売残前週比",
    "ratio": "信用倍率",
}

# 基本報價欄位（順便存）
RSS_QUOTE_FIELDS = {
    "price": "現在値",
    "volume": "出来高",
    "high": "高値",
    "low": "安値",
}


def _check_env() -> tuple[bool, str]:
    """執行前環境檢查"""
    if sys.platform != "win32":
        return False, f"OS 不支援：{sys.platform}（樂天 RSS 僅 Windows）"
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False, "缺套件：pip install pywin32"
    try:
        import pandas  # noqa: F401
    except ImportError:
        return False, "缺套件：pip install pandas"
    return True, "OK"


def _excel_session():
    """建立 Excel COM session（visible=False 但 RTD 需要 Excel 在記憶體）"""
    import win32com.client

    try:
        excel = win32com.client.DispatchEx("Excel.Application")
    except Exception as e:
        raise RuntimeError(
            f"無法啟動 Excel：{e}\n"
            "確認已安裝 Microsoft Office Excel（非 Excel Online / WPS）"
        )
    excel.Visible = False
    excel.DisplayAlerts = False
    wb = excel.Workbooks.Add()
    ws = wb.Worksheets(1)
    return excel, wb, ws


def _close_session(excel, wb):
    try:
        wb.Close(SaveChanges=False)
        excel.Quit()
    except Exception:
        pass


def _wait_rtd(ws, cell_ref: str, timeout: float = 5.0, poll: float = 0.2) -> object:
    """RTD 是非同步推送，寫入公式後要等 markespi II push 資料回來"""
    start = time.time()
    last = None
    while time.time() - start < timeout:
        v = ws.Range(cell_ref).Value
        if v is not None and v != "" and not (isinstance(v, str) and v.startswith("#")):
            return v
        last = v
        time.sleep(poll)
    return last  # 超時回最後一次（可能仍為 None 或 #N/A）


def fetch_margin_one(ws, code: str) -> dict:
    """單一股票拉信用残 + 即時報價，回 dict"""
    # 樂天 RSS 銘柄代碼格式：XXXX.T（東証）
    symbol = f"{code}.T"

    # 一次寫多個 cell，最後一次 read（減少等待）
    cell_map = {}
    row = 1
    for key, jp_field in RSS_MARGIN_FIELDS.items():
        cell = f"A{row}"
        ws.Range(cell).Formula = f'=RssMarginVal("{symbol}","{jp_field}")'
        cell_map[key] = cell
        row += 1
    for key, jp_field in RSS_QUOTE_FIELDS.items():
        cell = f"A{row}"
        ws.Range(cell).Formula = f'=RssMarket("{symbol}","{jp_field}")'
        cell_map[key] = cell
        row += 1

    # 等首個欄位 ready 表示 RSS 通了
    _wait_rtd(ws, cell_map["margin_long"], timeout=5.0)

    result = {"code": code, "date": date.today().strftime("%Y-%m-%d")}
    for key, cell in cell_map.items():
        v = ws.Range(cell).Value
        if isinstance(v, str) and v.startswith("#"):
            v = None  # #N/A、#NAME? 之類視為缺失
        result[key] = v

    # 清空儲存格給下檔用
    ws.Cells.Clear()
    return result


def write_margin_csv(code: str, row: dict) -> Path:
    """append 進 {code}_margin_daily.csv（dedupe by date）"""
    import pandas as pd

    out = OUT_DIR / f"{code}_margin_daily.csv"
    new_row = {
        "date": row["date"],
        "margin_long": row.get("margin_long"),
        "margin_short": row.get("margin_short"),
        "ratio": row.get("ratio"),
    }
    df_new = pd.DataFrame([new_row])

    if out.exists():
        try:
            existing = pd.read_csv(out)
            merged = pd.concat([existing, df_new], ignore_index=True)
            merged = merged.drop_duplicates("date", keep="last").sort_values("date")
            df_new = merged
        except Exception:
            pass
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df_new.to_csv(out, index=False)
    return out


def load_watchlist_codes() -> list[str]:
    p = ROOT / "data" / "watchlist.json"
    if not p.exists():
        return []
    wl = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(wl, list):
        return [str(item.get("code", "")).strip() for item in wl if item.get("code")]
    return [str(k).strip() for k in wl.keys()]


def load_universe_codes() -> list[str]:
    import csv
    p = ROOT / "data" / "universe.csv"
    out = []
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            c = (r.get("code") or "").strip()
            if c:
                out.append(c)
    return out


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--codes", help="逗號分隔代碼，如 7203,6758")
    g.add_argument("--watchlist", action="store_true", help="抓 data/watchlist.json 全部")
    g.add_argument("--all", action="store_true", help="抓 data/universe.csv 全部（>3000 檔，慢）")
    ap.add_argument("--delay", type=float, default=0.5, help="檔與檔之間延遲秒數（避免 RSS 過載）")
    args = ap.parse_args()

    ok, msg = _check_env()
    if not ok:
        print(f"[FAIL] 環境檢查：{msg}", file=sys.stderr)
        sys.exit(1)
    print(f"[OK] 環境檢查通過")

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    elif args.watchlist:
        codes = load_watchlist_codes()
    else:
        codes = load_universe_codes()

    if not codes:
        print("[FAIL] 沒有股票代碼", file=sys.stderr)
        sys.exit(1)
    print(f"[INFO] 共 {len(codes)} 檔股票")

    excel, wb, ws = _excel_session()
    print("[OK] Excel 開啟（背景），確認マーケットスピード II 已登入...")

    started = time.time()
    results = []
    fails = []
    try:
        for i, code in enumerate(codes, 1):
            try:
                row = fetch_margin_one(ws, code)
                if row.get("margin_long") is None and row.get("price") is None:
                    fails.append({"code": code, "error": "RSS 無回應（檢查 マケスピ 是否登入 / 代碼是否存在）"})
                else:
                    out = write_margin_csv(code, row)
                    results.append({"code": code, "rows": 1, "path": str(out.relative_to(ROOT))})
                if i % 10 == 0:
                    print(f"  [{i}/{len(codes)}] {code} ok={len(results)} fail={len(fails)}")
            except Exception as e:
                fails.append({"code": code, "error": str(e)})
            time.sleep(args.delay)
    finally:
        _close_session(excel, wb)

    elapsed = time.time() - started
    report = {
        "ts": datetime.now().isoformat(),
        "total": len(codes),
        "ok": len(results),
        "fail": len(fails),
        "elapsed_sec": round(elapsed, 1),
        "fails": fails[:20],  # 只記前 20 個失敗詳情
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[DONE] ok={len(results)} fail={len(fails)} elapsed={elapsed:.1f}s")
    print(f"       Report: {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
