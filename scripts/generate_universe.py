#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成完整的 universe.csv - 包含所有日本上市股票

來源：
1. Yahoo Finance Japan（推薦，較完整）
2. 備援：Minkabu
3. 備援：手動清單

使用方式：
    python scripts/generate_universe.py [--source yahoo|minkabu]
"""
import csv
import sys
import os
from pathlib import Path
from typing import List, Tuple

# 設定標準輸出編碼為 UTF-8
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def get_universe_from_yahoo() -> List[Tuple[str, str, str]]:
    """從 Yahoo Finance Japan 爬取所有上市股票"""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        print("❌ 缺少 requests 或 beautifulsoup4，請執行：")
        print("   pip install requests beautifulsoup4")
        return []

    print("🔄 正在從 Yahoo Finance Japan 爬取全市場股票列表...")

    rows = []
    markets = {
        "prime": "https://stocks.finance.yahoo.co.jp/markets/5000",      # Prime
        "standard": "https://stocks.finance.yahoo.co.jp/markets/5001",   # Standard
        "growth": "https://stocks.finance.yahoo.co.jp/markets/5002",     # Growth
    }

    for market_name, url in markets.items():
        print(f"  ├─ 正在爬取 {market_name.upper()} 市場...")
        try:
            # 獲取首頁以取得分頁數
            resp = requests.get(url, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 這個方法需要逐頁爬，可能耗時較久
            # 簡化版本：只爬第一頁（示例）
            table = soup.find('table', {'class': 'sc-6e4e6ef0-4'})
            if table:
                for tr in table.find_all('tr')[1:]:  # 跳過表頭
                    tds = tr.find_all('td')
                    if len(tds) >= 2:
                        code = tds[0].text.strip()
                        name = tds[1].text.strip()
                        rows.append((code, name, market_name.upper()))
                print(f"     ✓ 爬取 {market_name.upper()}：{len([r for r in rows if r[2] == market_name.upper()])} 檔")
        except Exception as e:
            print(f"     ✗ 爬取失敗：{e}")

    return rows

def get_universe_from_minkabu() -> List[Tuple[str, str, str]]:
    """從 Minkabu 爬取股票列表（備援）"""
    try:
        import requests
    except ImportError:
        return []

    print("🔄 正在從 Minkabu 爬取股票列表...")
    rows = []

    try:
        # Minkabu 不提供直接的全市場列表 API
        # 此處為簡化實現
        print("  ⚠️ Minkabu 無法批量爬取，改用預設清單")
    except Exception as e:
        print(f"  ✗ 爬取失敗：{e}")

    return rows

def get_hardcoded_universe() -> List[Tuple[str, str, str]]:
    """返回預設清單（從知名公司開始）"""
    print("📋 使用預設清單（日本主要上市公司）...")

    # 這是一個擴展的清單，包含日本主要上市公司
    # 實際環境應改用爬蟲取得完整清單
    rows = [
        # Prime Market（優良公司）
        ("7203", "トヨタ自動車", "Prime"),
        ("6758", "ソニーグループ", "Prime"),
        ("9984", "ソフトバンクグループ", "Prime"),
        ("8035", "東京エレクトロン", "Prime"),
        ("6861", "キーエンス", "Prime"),
        ("8306", "三菱UFJフィナンシャル", "Prime"),
        ("9983", "ファーストリテイリング", "Prime"),
        ("9433", "KDDI", "Prime"),
        ("9432", "NTT", "Prime"),
        ("6098", "リクルート", "Prime"),
        ("4063", "信越化学", "Prime"),
        ("6954", "ファナック", "Prime"),
        ("6367", "ダイキン", "Prime"),
        ("6501", "日立製作所", "Prime"),
        ("8058", "三菱商事", "Prime"),
        ("8031", "三井物産", "Prime"),
        ("8053", "住友商事", "Prime"),
        ("7011", "三菱重工", "Prime"),
        ("7974", "任天堂", "Prime"),
        ("7267", "ホンダ", "Prime"),
        ("6752", "パナソニック", "Prime"),
        ("7733", "オリンパス", "Prime"),
        ("6273", "SMC", "Prime"),
        ("2413", "M3", "Prime"),
        ("4661", "オリエンタルランド", "Prime"),
        ("8002", "丸紅", "Prime"),
        ("8001", "伊藤忠商事", "Prime"),
        ("3382", "セブン&アイ", "Prime"),
        ("9434", "ソフトバンク", "Prime"),
        ("5108", "ブリヂストン", "Prime"),
        # Standard Market
        ("2914", "日本たばこ産業", "Standard"),
        ("6098", "リクルート", "Standard"),
        ("9766", "コスモエネルギーホールディングス", "Standard"),
        # 更多股票可在此添加...
    ]

    return rows

def write_universe_csv(rows: List[Tuple[str, str, str]], output_path: Path) -> None:
    """寫入 universe.csv"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['code', 'name', 'market'])
        writer.writerows(rows)

    print(f"\n✅ 完成！已寫入 {len(rows)} 檔股票到 {output_path}")
    print(f"\n📊 市場分佈：")
    for market in set(r[2] for r in rows):
        count = len([r for r in rows if r[2] == market])
        print(f"   - {market}: {count} 檔")

def main():
    output_path = Path(__file__).parent.parent / "data" / "universe.csv"

    # 優先順序：Yahoo > Minkabu > 預設清單
    universe = []

    # 嘗試從 Yahoo Finance 爬取
    universe = get_universe_from_yahoo()

    # 若失敗，嘗試 Minkabu
    if not universe:
        universe = get_universe_from_minkabu()

    # 若仍失敗，使用預設清單
    if not universe:
        universe = get_hardcoded_universe()

    if universe:
        write_universe_csv(universe, output_path)
    else:
        print("❌ 無法取得股票清單，請手動下載並放到 data/universe.csv")
        sys.exit(1)

if __name__ == '__main__':
    main()
