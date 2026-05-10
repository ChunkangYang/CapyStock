#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下載 JPX 官方上市公司清單並更新 universe.csv

來源：JPX Statistics API
URL: https://www.jpx.co.jp/english/markets/statistics-equities/misc/01.html

使用方式：
    python scripts/update_jpx_universe.py
"""
import csv
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple
from urllib.request import urlopen

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def download_jpx_list() -> List[Tuple[str, str, str]]:
    """從 JPX 官方下載上市公司清單"""
    try:
        import pandas as pd
    except ImportError:
        print("❌ 缺少 pandas")
        print("   pip install pandas openpyxl")
        return []

    print("🔄 正在從 JPX 官方下載上市公司清單...\n")

    try:
        # 官方 XLS 檔案
        url = "https://www.jpx.co.jp/english/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_e.xls"

        with tempfile.NamedTemporaryFile(suffix='.xls', delete=False) as tmp:
            tmp_path = tmp.name
            print(f"  ⬇️  下載中... {url}")
            with urlopen(url, timeout=30) as response:
                tmp.write(response.read())

        print(f"  ✓ 下載完成（{Path(tmp_path).stat().st_size / 1024:.1f} KB）\n")

        # 解析 XLS
        print("  📋 解析資料...")
        df = pd.read_excel(tmp_path, sheet_name=0)

        # 篩選股票市場（排除 ETF、REIT 等）
        domestic_markets = [
            'Prime Market (Domestic)',
            'Standard Market(Domestic)',
            'Growth Market(Domestic)'
        ]

        df_stocks = df[df['Section/Products'].isin(domestic_markets)].copy()

        # 標準化市場名稱
        market_mapping = {
            'Prime Market (Domestic)': 'Prime',
            'Standard Market(Domestic)': 'Standard',
            'Growth Market(Domestic)': 'Growth'
        }
        df_stocks['Market'] = df_stocks['Section/Products'].map(market_mapping)

        # 選取必要欄位
        df_stocks = df_stocks[['Local Code', 'Name (English)', 'Market']]
        df_stocks.columns = ['code', 'name', 'market']

        # 去重並排序
        df_stocks = df_stocks.drop_duplicates(subset=['code'])
        df_stocks = df_stocks.sort_values(['market', 'code'])

        rows = [tuple(row) for row in df_stocks.values]
        Path(tmp_path).unlink()  # 刪除暫存檔

        print(f"  ✓ 解析完成\n")
        return rows

    except Exception as e:
        print(f"  ✗ 下載失敗：{e}\n")
        return []


def write_universe_csv(rows: List[Tuple[str, str, str]], output_path: Path) -> dict:
    """寫入 universe.csv 並返回統計"""
    if not rows:
        return {
            'ok': False,
            'error': '無股票數據',
            'total': 0,
            'prime': 0,
            'standard': 0,
            'growth': 0
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['code', 'name', 'market'])
            writer.writerows(rows)

        # 統計
        stats = {
            'total': len(rows),
            'prime': len([r for r in rows if r[2] == 'Prime']),
            'standard': len([r for r in rows if r[2] == 'Standard']),
            'growth': len([r for r in rows if r[2] == 'Growth']),
        }

        print(f"✅ 成功！已寫入 {stats['total']} 檔股票到：")
        print(f"   {output_path}\n")

        print(f"📊 市場分佈：")
        print(f"   ├─ Prime: {stats['prime']} 檔")
        print(f"   ├─ Standard: {stats['standard']} 檔")
        print(f"   └─ Growth: {stats['growth']} 檔")

        return {
            'ok': True,
            'total': stats['total'],
            'prime': stats['prime'],
            'standard': stats['standard'],
            'growth': stats['growth']
        }
    except Exception as e:
        print(f"❌ 寫檔失敗：{e}")
        return {
            'ok': False,
            'error': str(e),
            'total': 0,
            'prime': 0,
            'standard': 0,
            'growth': 0
        }


def main():
    output_path = Path(__file__).parent.parent / "data" / "universe.csv"

    print("=" * 70)
    print("  CapyStock JPX 股票清單更新器")
    print("=" * 70)
    print()

    # 下載並解析
    rows = download_jpx_list()

    if not rows:
        print("❌ 無法取得股票清單")
        return 1

    # 寫入
    result = write_universe_csv(rows, output_path)

    if result['ok']:
        print(f"\n💡 Docker 容器會自動重載清單")
        print(f"   如未生效，手動重啟：docker-compose restart")
        return 0
    else:
        print(f"❌ 更新失敗：{result['error']}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
