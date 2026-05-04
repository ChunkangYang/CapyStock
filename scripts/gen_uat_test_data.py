"""UAT 測試資料生成器

依 docs/UAT.md 列出的測試案例，補齊：
1. 9432 / 6758 的 price / margin / flow / fundamental cache
2. 今日 scan_snapshots（signals + dividend parquet）
3. notification_rules.json 範例
4. _ingest_meta.json 補上對應條目

執行：python -m scripts.gen_uat_test_data
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
SNAP = DATA / "scan_snapshots"
SNAP.mkdir(parents=True, exist_ok=True)


# ---------- 1. 補抓 9432 / 6758 price ----------
def fetch_price_yf(code: str, days: int = 90) -> pd.DataFrame:
    end = datetime.now()
    start = end - timedelta(days=days + 30)
    df = yf.Ticker(f"{code}.T").history(start=start, end=end, interval="1d")
    if df.empty:
        raise RuntimeError(f"yfinance empty for {code}")
    df = df.reset_index()
    df["date"] = df["Date"].dt.strftime("%Y-%m-%d")
    out = df[["date", "Open", "High", "Low", "Close", "Volume"]].copy()
    out.columns = ["date", "open", "high", "low", "close", "volume"]
    out["volume"] = (out["volume"] / 1000).round(1)  # 千株
    return out.tail(days).reset_index(drop=True)


def gen_margin(code: str, weeks: int = 12) -> pd.DataFrame:
    """合成週信用残（kabutan/yahoo Premium 限制 → 用合成資料）"""
    base_long = {"9432": 5500, "6758": 12000}.get(code, 6000)
    base_short = base_long // 2
    rows = []
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    for i in range(weeks):
        wk = monday - timedelta(weeks=weeks - 1 - i)
        ml = base_long + i * 60 + (i % 3) * 25
        ms = base_short + i * 20
        rows.append({"week": wk.strftime("%Y-%m-%d"), "margin_long": ml, "margin_short": ms, "ratio": round(ml / ms, 2)})
    return pd.DataFrame(rows)


def gen_flow(code: str, days: int = 30) -> pd.DataFrame:
    """合成投資部門別日流量（千株）"""
    rng = pd.date_range(end=date.today(), periods=days, freq="B")
    rows = []
    for i, d in enumerate(rng):
        sign = 1 if i % 5 < 3 else -1
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "foreign_net": sign * (3000 + i * 50 + (i % 4) * 200),
            "institution_net": sign * (800 + i * 10),
            "individual_net": -sign * (3500 + i * 40),
        })
    return pd.DataFrame(rows)


def gen_fundamental(code: str) -> pd.DataFrame:
    """合成 IR Bank 風格基本面（15 年）"""
    base = {
        "9432": dict(sales=12000000, eps=120, op_margin=18, equity_ratio=38, op_cf=2800000, cash=1500000, dps=120, payout=40),
        "6758": dict(sales=10500000, eps=900, op_margin=11, equity_ratio=33, op_cf=1500000, cash=1300000, dps=85, payout=10),
    }.get(code)
    if not base:
        return pd.DataFrame()
    rows = []
    for idx in range(-15, 1):
        growth = 1 + idx * 0.03
        rows.append({
            "year_idx": idx,
            "sales": int(base["sales"] * growth),
            "eps": round(base["eps"] * growth, 1),
            "op_margin": round(base["op_margin"] + idx * 0.1, 1),
            "equity_ratio": round(base["equity_ratio"] + idx * 0.2, 1),
            "op_cf": int(base["op_cf"] * growth),
            "cash": int(base["cash"] * (1 + idx * 0.04)),
            "dps": round(base["dps"] * (1 + idx * 0.04), 1),
            "payout": round(base["payout"] - idx * 0.5, 1),
        })
    return pd.DataFrame(rows)


def write_price_caches() -> dict[str, float]:
    out = {}
    for code in ("9432", "6758"):
        target = CACHE / f"{code}_price.csv"
        try:
            df = fetch_price_yf(code, days=90)
        except Exception as e:
            print(f"[warn] yfinance 失敗 {code}: {e}，改合成")
            base = 150.0 if code == "9432" else 13000.0
            rng = pd.date_range(end=date.today(), periods=90, freq="B")
            df = pd.DataFrame({
                "date": [d.strftime("%Y-%m-%d") for d in rng],
                "open": [base + i * 0.4 for i in range(len(rng))],
                "high": [base + i * 0.4 + 5 for i in range(len(rng))],
                "low": [base + i * 0.4 - 5 for i in range(len(rng))],
                "close": [base + i * 0.4 + (i % 3) for i in range(len(rng))],
                "volume": [50000 + i * 100 for i in range(len(rng))],
            })
        df.to_csv(target, index=False)
        out[code] = float(df["close"].iloc[-1])
        print(f"  ✓ {target.name}: {len(df)} rows, latest close = {out[code]}")
    return out


def write_margin_flow_fundamental() -> None:
    for code in ("9432", "6758"):
        if not (CACHE / f"{code}_margin.csv").exists():
            gen_margin(code).to_csv(CACHE / f"{code}_margin.csv", index=False)
            print(f"  ✓ {code}_margin.csv")
        if not (CACHE / f"{code}_flow.csv").exists():
            gen_flow(code).to_csv(CACHE / f"{code}_flow.csv", index=False)
            print(f"  ✓ {code}_flow.csv")
    # fundamental
    for code in ("9432",):
        target = CACHE / f"{code}_fundamental.csv"
        if not target.exists():
            df = gen_fundamental(code)
            if not df.empty:
                df.to_csv(target, index=False)
                print(f"  ✓ {target.name}")


# ---------- 2. scan_snapshots ----------
def write_scan_snapshots() -> None:
    today_str = date.today().strftime("%Y-%m-%d")
    universe = pd.read_csv(DATA / "universe.csv")
    now = datetime.now().replace(microsecond=0)

    # signals
    sig_rows = []
    for i, row in universe.iterrows():
        score = 8 - (i % 9) + (1 if i % 3 == 0 else 0)
        sig_rows.append({
            "code": str(row["code"]),
            "name": row["name"],
            "latest_price": round(1000 + i * 137.7, 1),
            "has_accumulation": (i % 4 == 0),
            "has_exit": (i % 6 == 1),
            "has_stop_loss": (i % 11 == 2),
            "edinet_recent_count": (i % 3),
            "score": int(score),
            "generated_at": now,
        })
    pd.DataFrame(sig_rows).to_parquet(SNAP / f"signals_{today_str}.parquet", index=False)
    print(f"  ✓ signals_{today_str}.parquet ({len(sig_rows)} rows)")

    # dividend
    div_rows = []
    overalls = ["STRONG", "HEALTHY", "CAUTION", "RISKY"]
    for i, row in universe.iterrows():
        latest_dps = round(40 + i * 3.5, 1)
        latest_price = round(1000 + i * 137.7, 1)
        div_rows.append({
            "code": str(row["code"]),
            "name": row["name"],
            "overall": overalls[i % 4],
            "pass_count": 4 + (i % 3),
            "warn_count": 2,
            "fail_count": 1 + (i % 2),
            "latest_dps": latest_dps,
            "dps_streak_no_cut": 3 + (i % 5),
            "est_yield": round(latest_dps / latest_price, 5),
            "payout_avg": round(30 + (i % 4) * 5.5, 1),
            "equity_ratio_latest": round(35 + (i % 6) * 1.2, 1),
            "eps_growth": round(5 + (i % 7) * 1.1, 1),
            "generated_at": now,
        })
    pd.DataFrame(div_rows).to_parquet(SNAP / f"dividend_{today_str}.parquet", index=False)
    print(f"  ✓ dividend_{today_str}.parquet ({len(div_rows)} rows)")


# ---------- 3. notification_rules sample ----------
def write_notification_rules() -> None:
    target = DATA / "notification_rules.json"
    rules = {
        "rules": [
            {
                "id": "rule_signal_high_score",
                "enabled": True,
                "name": "投機 score ≥ 80 即時 push",
                "trigger": {"type": "signal", "min_score": 80},
                "channels": ["email"],
                "delivery": "realtime",
            },
            {
                "id": "rule_daily_digest",
                "enabled": True,
                "name": "每日 18:00 digest",
                "trigger": {"type": "digest"},
                "schedule": "0 18 * * *",
                "channels": ["email"],
                "delivery": "digest",
            },
        ]
    }
    target.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ notification_rules.json ({len(rules['rules'])} 條)")


# ---------- 4. _ingest_meta.json 補條目 ----------
def update_ingest_meta() -> None:
    target = CACHE / "_ingest_meta.json"
    meta = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    today = date.today().strftime("%Y-%m-%d")
    for code in ("9432", "6758"):
        meta.setdefault(f"{code}_margin", {"last_source": "yahoo_jp", "updated": today})
        meta.setdefault(f"{code}_flow", {"last_source": "manual_csv", "updated": today})
    target.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ _ingest_meta.json updated")


# ---------- 5. log.csv 補幾筆 ----------
def append_log_entries() -> None:
    target = DATA / "log.csv"
    new_rows = [
        ("2026-05-02 09:30:00", "9984", "ソフトバンクグループ", "accumulation", "info", "吃貨訊號：外資連續 5 日買超 + 融資餘額下降"),
        ("2026-05-03 09:30:00", "7203", "トヨタ自動車", "exit", "warn", "符合 2/3 出場條件：法人連賣、股價離低點 +32%"),
        ("2026-05-04 09:30:00", "9432", "NTT", "accumulation", "info", "吃貨訊號：法人連續 6 日買超"),
    ]
    with target.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in new_rows:
            w.writerow(r)
    print(f"  ✓ log.csv 追加 {len(new_rows)} 筆")


def main():
    print("== 1. price/margin/flow/fundamental cache ==")
    write_price_caches()
    write_margin_flow_fundamental()
    print("== 2. scan_snapshots ==")
    write_scan_snapshots()
    print("== 3. notification_rules.json ==")
    write_notification_rules()
    print("== 4. _ingest_meta.json ==")
    update_ingest_meta()
    print("== 5. log.csv 追加 ==")
    append_log_entries()
    print("\n完成。")


if __name__ == "__main__":
    main()
