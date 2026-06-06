import argparse
from datetime import datetime

from api.services import scan_service


def main():
    parser = argparse.ArgumentParser(description="全市場掃描 worker")
    parser.add_argument("--kind", required=True, choices=["signals", "dividend"], help="掃描種類")
    parser.add_argument("--universe", default="data/universe.csv", help="universe.csv 路徑")
    parser.add_argument("--limit", type=int, default=None, help="只掃前 N 檔")
    args = parser.parse_args()

    # 載入 universe
    universe = scan_service.load_universe(args.universe)
    if args.limit:
        universe = universe[: args.limit]

    today_str = datetime.now().strftime("%Y-%m-%d")

    print(f"開始掃描 {args.kind}（{len(universe)} 檔，日期 {today_str}）...")

    try:
        if args.kind == "signals":
            rows, errors = scan_service.run_signals_scan(universe)
        else:  # dividend
            rows, errors = scan_service.run_dividend_scan(universe)

        # 寫快照（signals 開 degraded 防呆）
        snapshot_path = scan_service.write_snapshot(
            args.kind, rows, today_str, guard=(args.kind == "signals")
        )
        print(f"✓ 寫入快照：{snapshot_path}（{len(rows)} 筆）")

        # 寫失敗紀錄
        if errors:
            scan_service.write_errors(args.kind, errors, today_str)
            error_path = scan_service.error_path(args.kind, today_str)
            print(f"⚠ 寫入失敗紀錄：{error_path}（{len(errors)} 筆）")

        print(f"掃描完成！")

    except Exception as e:
        print(f"✗ 掃描失敗：{e}")
        raise


if __name__ == "__main__":
    main()
