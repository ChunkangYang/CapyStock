"""CapyStock CLI 入口。

用法：
  python -m capystock.main add <code> <start_price>
  python -m capystock.main remove <code>
  python -m capystock.main check [--code CODE]
  python -m capystock.main log [--days 30]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from tabulate import tabulate

from . import analyzer, config, edinet, fundamental, portfolio, scraper, storage


def _fmt_pct(v: float | None) -> str:
    return "—" if v is None else f"{v*100:+.1f}%"


def _fmt_num(v: float | None) -> str:
    return "—" if v is None else f"{v:,.0f}"


def cmd_add(args: argparse.Namespace) -> int:
    code = args.code
    name = scraper.fetch_name(code) or ""
    storage.add_watch(
        code, args.start_price, name,
        master_cost=args.master_cost,
        target_price=args.target,
        stop_price=args.stop,
        last_step_price=args.last_step,
    )
    extras = []
    if args.master_cost is not None:
        extras.append(f"主力成本 {args.master_cost:,.0f}")
    if args.target is not None:
        extras.append(f"目標 {args.target:,.0f}")
    if args.stop is not None:
        extras.append(f"停損 {args.stop:,.0f}")
    if args.last_step is not None:
        extras.append(f"最後一階 {args.last_step:,.0f}")
    if args.target is not None and args.stop is not None and args.start_price > args.stop:
        rr = (args.target - args.start_price) / (args.start_price - args.stop)
        flag = "✓" if rr >= config.RISK_REWARD_MIN_RATIO else "⚠️ <1:3"
        extras.append(f"RR 1:{rr:.2f} {flag}")
    extra_str = f"  [{' / '.join(extras)}]" if extras else ""
    print(f"✓ 加入追蹤：{code}（{name or '未知'}）起始價 {args.start_price:,.0f}{extra_str}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    if storage.remove_watch(args.code):
        print(f"✓ 已移除 {args.code}")
        return 0
    print(f"✗ {args.code} 不在追蹤清單")
    return 1


def cmd_check(args: argparse.Namespace) -> int:
    wl = storage.load_watchlist()
    if not wl:
        print("追蹤清單為空，先用 `add` 加入股票。")
        return 0

    codes = [args.code] if args.code else list(wl.keys())

    # EDINET 5% rule 事件一併帶出
    edinet_by_code: dict[str, list[dict]] = {}
    if config.EDINET_API_KEY and not args.no_edinet:
        wanted = set(codes)
        try:
            reports = edinet.fetch_since(days=args.edinet_days, codes=wanted)
            for r in reports:
                edinet_by_code.setdefault(r["sec_code"], []).append(r)
        except Exception as e:
            print(f"  (EDINET 查詢失敗：{e})")
    elif not config.EDINET_API_KEY:
        print("  (未設定 EDINET_API_KEY，跳過 5% rule 監控；見 data/.env)")

    table_rows: list[list[str]] = []
    today = datetime.now().strftime("%Y-%m-%d")

    for code in codes:
        if code not in wl:
            print(f"[{code}] 不在追蹤清單")
            continue
        entry = wl[code]
        name = entry.get("name") or scraper.fetch_name(code) or ""
        if name and not entry.get("name"):
            entry["name"] = name
            wl[code] = entry
            storage.save_watchlist(wl)

        price_df, source = scraper.fetch_price(code)
        margin_df = scraper.fetch_margin(code)

        if price_df is not None:
            scraper.cache_save(code, "price", price_df)

        snap, alerts = analyzer.analyze(
            code, name, entry["start_price"], price_df, margin_df,
            master_cost=entry.get("master_cost"),
            target_price=entry.get("target_price"),
            stop_price=entry.get("stop_price"),
            last_step_price=entry.get("last_step_price"),
            added_date=entry.get("added_date"),
        )

        # 輸出詳盡區塊
        print()
        print(f"[{today}] {code}（{name or '—'}） 來源：{source}")
        if snap.latest_price is not None:
            print(f"  最新收盤：{snap.latest_price:,.0f} 円"
                  f"  / 起始價：{snap.start_price:,.0f}"
                  f"  / 相對起始：{_fmt_pct(snap.price_vs_start_pct)}"
                  f"  / 離近期低點：{_fmt_pct(snap.price_vs_recent_low_pct)}")
            anchors = []
            if snap.master_cost:
                anchors.append(f"主力成本 {snap.master_cost:,.0f}"
                               f"（vs現價 {_fmt_pct(snap.price_vs_master_cost_pct)}）")
            if snap.last_step_price:
                anchors.append(f"最後一階 {snap.last_step_price:,.0f}")
            if snap.target_price:
                anchors.append(f"目標 {snap.target_price:,.0f}")
            if snap.stop_price:
                anchors.append(f"停損 {snap.stop_price:,.0f}")
            if snap.risk_reward_ratio is not None:
                anchors.append(f"RR 1:{snap.risk_reward_ratio:.2f}")
            if anchors:
                print(f"  心法錨點：{' / '.join(anchors)}")
        if snap.margin_trend_note:
            print(f"  信用残：{snap.margin_trend_note} ⚠️")
        for note in snap.notes:
            print(f"  · {note}")
        for a in alerts:
            icon = {"critical": "🛑", "warn": "⚠️", "info": "ℹ️"}.get(a["severity"], "▶")
            print(f"  {icon} {a['alert_type']}：{a['message']}")
            storage.append_log(code, name, a["alert_type"], a["severity"], a["message"])

        for r in edinet_by_code.get(code, []):
            msg = edinet.format_report(r)
            print(f"  📄 {msg}")
            storage.append_log(code, name, "edinet_5pct", "info", msg)

        # 表格列
        table_rows.append([
            code,
            (name or "")[:10],
            _fmt_num(snap.latest_price),
            _fmt_pct(snap.price_vs_start_pct),
            _fmt_pct(snap.price_vs_recent_low_pct),
            "✓" if snap.cond_inst_sell else "",
            "✓" if snap.cond_margin_surge else "",
            "✓" if snap.cond_price_rise else "",
            "🛑" if snap.stop_loss_triggered else ("📥" if snap.accumulation_signal else ""),
        ])

    print()
    print(tabulate(
        table_rows,
        headers=["Code", "Name", "Close", "vs起始", "vs低點",
                 "C1賣", "C2融", "C3漲", "訊號"],
        tablefmt="github",
    ))
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    rows = storage.read_log(days=args.days)
    if not rows:
        print(f"過去 {args.days} 日無警示紀錄")
        return 0
    print(tabulate(
        [[r["timestamp"], r["code"], r.get("name", ""), r["alert_type"],
          r["severity"], r["message"]] for r in rows],
        headers=["Time", "Code", "Name", "Type", "Sev", "Message"],
        tablefmt="github",
    ))
    return 0


def cmd_edinet(args: argparse.Namespace) -> int:
    if not config.EDINET_API_KEY:
        print("✗ 未設定 EDINET_API_KEY，請在 data/.env 加入")
        return 1
    codes = None
    if not args.all:
        wl = storage.load_watchlist()
        codes = set(wl.keys())
        if not codes:
            print("watchlist 為空，用 --all 掃全部，或先 add 股票")
            return 0
    reports = edinet.fetch_since(days=args.days, codes=codes)
    if not reports:
        print(f"過去 {args.days} 日無 5% rule 申報"
              + ("（watchlist 範圍內）" if codes else ""))
        return 0
    rows = [[r["submit_date"], r["sec_code"],
             "変更" if r["doc_type_code"] == "360" else "新規",
             r["filer_name"][:30], r["pdf_url"]]
            for r in reports]
    print(tabulate(rows, headers=["Date", "Code", "Kind", "Filer", "URL"],
                   tablefmt="github"))
    return 0


def cmd_fundamental(args: argparse.Namespace) -> int:
    code = args.code
    wl = storage.load_watchlist()
    name = ""
    if code in wl:
        name = wl[code].get("name", "") or ""
    if not name:
        name = scraper.fetch_name(code) or ""

    report, err = fundamental.analyze_fundamental(code, name)
    if err:
        print(err)
        return 1

    print(f"=== Fundamental Analysis: {code}（{name or '—'}）===")
    rows = []
    for m in report.metrics:
        rows.append([fundamental.METRIC_DISPLAY[m.metric], m.score, m.note])
    print(tabulate(rows, headers=["Metric", "Score", "Value / Trend"],
                   tablefmt="github"))

    c = report.counts()
    print()
    print(f"Overall: {report.overall} "
          f"({c['PASS']} PASS / {c['WARN']} WARN / {c['FAIL']} FAIL"
          + (f" / {c['N/A']} N/A" if c["N/A"] else "")
          + ")")

    storage.append_log(
        code, name, "fundamental", report.overall,
        fundamental.report_to_details_json(report),
    )
    return 0


def cmd_portfolio_add(args: argparse.Namespace) -> int:
    name = scraper.fetch_name(args.code) or ""
    lot = portfolio.add_lot(
        code=args.code,
        name=name,
        entry_price=args.entry_price,
        quantity=args.quantity,
        note=args.note or "",
    )
    print(f"✓ 持倉新增：{args.code}（{name or '未知'}）"
          f" {args.quantity}股 @ {args.entry_price:,.0f}  lot_id={lot['id']}")
    return 0


def cmd_portfolio_list(_args: argparse.Namespace) -> int:
    open_lots = portfolio.list_open()
    if not open_lots:
        print("目前無持倉")
        return 0
    rows = []
    for lot in open_lots:
        df, _ = scraper.fetch_price(lot["code"])
        current = float(df["close"].iloc[-1]) if df is not None and not df.empty else None
        unrealized = ((current - lot["entry_price"]) * lot["quantity"]) if current else None
        pct = ((current / lot["entry_price"] - 1) * 100) if current else None
        rows.append([
            lot["code"],
            lot["name"],
            f"{lot['entry_price']:,.0f}",
            lot["quantity"],
            f"{current:,.0f}" if current else "—",
            f"{unrealized:+,.0f}" if unrealized is not None else "—",
            f"{pct:+.1f}%" if pct is not None else "—",
            lot["entry_date"],
            lot["id"][:8],
        ])
    print(tabulate(
        rows,
        headers=["Code", "Name", "買入價", "數量", "現價", "未實現損益", "報酬率", "買入日", "lot_id(前8)"],
        tablefmt="github",
    ))
    return 0


def cmd_portfolio_close(args: argparse.Namespace) -> int:
    lot = portfolio.close_lot(args.code, args.lot_id, args.exit_price)
    if lot is None:
        print(f"✗ 找不到 {args.code} 的 lot_id={args.lot_id}（或已平倉）")
        return 1
    pnl = (args.exit_price - lot["entry_price"]) * lot["quantity"]
    pct = (args.exit_price / lot["entry_price"] - 1) * 100
    print(f"✓ 平倉完成：{args.code} @ {args.exit_price:,.0f}  損益 {pnl:+,.0f}（{pct:+.1f}%）")
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    wl = storage.load_watchlist()
    if not wl:
        print("追蹤清單為空")
        return 0
    print(tabulate(
        [[v["code"], v.get("name", ""), f"{v['start_price']:,.0f}", v.get("added_date", "")]
         for v in wl.values()],
        headers=["Code", "Name", "StartPrice", "Added"],
        tablefmt="github",
    ))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="capystock", description="日股籌碼分析工具")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="加入追蹤股票")
    p_add.add_argument("code")
    p_add.add_argument("start_price", type=float, help="進場價（你買進的價格）")
    p_add.add_argument("--master-cost", type=float, default=None,
                       dest="master_cost",
                       help="主力成本（停損錨點，心法第七篇）")
    p_add.add_argument("--target", type=float, default=None,
                       help="目標價（用於風報比與出場條件 3）")
    p_add.add_argument("--stop", type=float, default=None,
                       help="使用者指定停損價（覆寫主力成本錨點）")
    p_add.add_argument("--last-step", type=float, default=None,
                       dest="last_step",
                       help="主力最後一階均價（跌破 3%% 連 2 日警告）")
    p_add.set_defaults(func=cmd_add)

    p_rm = sub.add_parser("remove", help="移除追蹤股票")
    p_rm.add_argument("code")
    p_rm.set_defaults(func=cmd_remove)

    p_chk = sub.add_parser("check", help="分析所有（或指定）追蹤股票")
    p_chk.add_argument("--code", help="只分析指定代號")
    p_chk.add_argument("--edinet-days", type=int, default=3,
                       help="EDINET 回掃天數（預設 3）")
    p_chk.add_argument("--no-edinet", action="store_true",
                       help="停用 EDINET 5% rule 監控")
    p_chk.set_defaults(func=cmd_check)

    p_ed = sub.add_parser("edinet", help="單獨查 EDINET 5% rule 報告")
    p_ed.add_argument("--days", type=int, default=7, help="回掃天數（預設 7）")
    p_ed.add_argument("--all", action="store_true",
                      help="查全部個股（不限 watchlist）")
    p_ed.set_defaults(func=cmd_edinet)

    p_log = sub.add_parser("log", help="顯示歷史警示")
    p_log.add_argument("--days", type=int, default=30)
    p_log.set_defaults(func=cmd_log)

    p_fund = sub.add_parser("fundamental", help="IR Bank 基本面 8 指標評分")
    p_fund.add_argument("code")
    p_fund.set_defaults(func=cmd_fundamental)

    p_list = sub.add_parser("list", help="顯示追蹤清單")
    p_list.set_defaults(func=cmd_list)

    # portfolio 子命令群
    p_pf = sub.add_parser("portfolio", help="持倉管理")
    pf_sub = p_pf.add_subparsers(dest="pf_cmd", required=True)

    p_pf_add = pf_sub.add_parser("add", help="新增買入紀錄")
    p_pf_add.add_argument("code")
    p_pf_add.add_argument("entry_price", type=float, help="買入價")
    p_pf_add.add_argument("quantity", type=int, help="買入股數")
    p_pf_add.add_argument("--note", default="", help="備注")
    p_pf_add.set_defaults(func=cmd_portfolio_add)

    p_pf_list = pf_sub.add_parser("list", help="顯示未平倉持倉")
    p_pf_list.set_defaults(func=cmd_portfolio_list)

    p_pf_close = pf_sub.add_parser("close", help="平倉")
    p_pf_close.add_argument("code")
    p_pf_close.add_argument("lot_id", help="lot ID（前8碼即可唯一識別）")
    p_pf_close.add_argument("exit_price", type=float, help="賣出價")
    p_pf_close.set_defaults(func=cmd_portfolio_close)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
