#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自動爬取日本全市場上市股票清單（3,700+ 家公司）

來源：kabutan.jp（日本股民最常用的資訊網站）

使用方式：
    python scripts/fetch_full_universe.py
"""
import csv
import sys
import time
from pathlib import Path
from typing import List, Set, Tuple
from urllib.parse import urljoin

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def fetch_from_kabutan() -> List[Tuple[str, str, str]]:
    """從 kabutan.jp 爬取所有上市股票"""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        print("❌ 缺少 requests 或 beautifulsoup4")
        print("   pip install requests beautifulsoup4")
        return []

    print("🔄 正在從 kabutan.jp 爬取全市場股票（這可能需要 5-10 分鐘）...\n")

    rows: List[Tuple[str, str, str]] = []
    seen_codes: Set[str] = set()

    # kabutan 的市場分類
    markets = {
        "Prime": "https://kabutan.jp/stock/market?market=0&sort=code",
        "Standard": "https://kabutan.jp/stock/market?market=2&sort=code",
        "Growth": "https://kabutan.jp/stock/market?market=3&sort=code",
    }

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'CapyStock/1.0 (+https://github.com/user/capystock)'
    })

    for market_name, base_url in markets.items():
        print(f"📍 正在爬取 {market_name} 市場...")
        page = 1
        market_count = 0

        while page <= 100:  # 安全上限
            try:
                url = f"{base_url}&page={page}"
                print(f"   ├─ 第 {page} 頁...", end=" ", flush=True)

                resp = session.get(url, timeout=10)
                resp.encoding = 'utf-8'
                soup = BeautifulSoup(resp.text, 'html.parser')

                # 找股票表格
                table = soup.find('table', {'class': 'stock_table'})
                if not table:
                    print("✓ (無更多數據，停止)")
                    break

                tr_list = table.find_all('tr')[1:]  # 跳過表頭
                if not tr_list:
                    print("✓ (無更多數據，停止)")
                    break

                page_found = 0
                for tr in tr_list:
                    try:
                        tds = tr.find_all('td')
                        if len(tds) < 3:
                            continue

                        # 提取代號、名稱
                        code_cell = tds[0].find('a')
                        if not code_cell:
                            continue

                        code = code_cell.text.strip()
                        if not code or not code.isdigit():
                            continue

                        name_cell = tds[1].find('a')
                        name = name_cell.text.strip() if name_cell else "Unknown"

                        # 去重
                        if code in seen_codes:
                            continue

                        rows.append((code, name, market_name))
                        seen_codes.add(code)
                        page_found += 1
                    except Exception as e:
                        continue

                print(f"✓ 找到 {page_found} 檔")

                if page_found == 0:
                    # 如果這頁沒找到，可能已到末頁
                    break

                market_count += page_found
                page += 1
                time.sleep(0.5)  # 禮貌延遲

            except requests.exceptions.RequestException as e:
                print(f"✗ 網路錯誤：{e}")
                continue
            except Exception as e:
                print(f"✗ 解析錯誤：{e}")
                continue

        print(f"   └─ {market_name} 合計：{market_count} 檔\n")

    print(f"\n📊 爬蟲完成統計：")
    print(f"   ├─ 總計：{len(rows)} 檔")
    for market in ["Prime", "Standard", "Growth"]:
        count = len([r for r in rows if r[2] == market])
        print(f"   ├─ {market}：{count} 檔")

    return rows

def fetch_fallback_hardcoded() -> List[Tuple[str, str, str]]:
    """備援：使用預設清單"""
    print("⚠️ 爬蟲失敗，使用備援清單...")
    rows = [
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
    ]
    return rows

def write_universe_csv(rows: List[Tuple[str, str, str]], output_path: Path) -> bool:
    """寫入 universe.csv"""
    if not rows:
        print("❌ 無股票數據，未寫入檔案")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['code', 'name', 'market'])
            writer.writerows(rows)

        print(f"\n✅ 成功！已寫入 {len(rows)} 檔股票到：")
        print(f"   {output_path}\n")

        print(f"📊 市場分佈：")
        for market in ["Prime", "Standard", "Growth"]:
            count = len([r for r in rows if r[2] == market])
            if count > 0:
                print(f"   ├─ {market}: {count} 檔")

        return True
    except Exception as e:
        print(f"❌ 寫檔失敗：{e}")
        return False

def main():
    output_path = Path(__file__).parent.parent / "data" / "universe.csv"

    print("=" * 60)
    print("  CapyStock 全市場股票清單生成器")
    print("=" * 60)
    print()

    # 嘗試爬蟲
    rows = fetch_from_kabutan()

    # 若失敗，使用備援
    if not rows or len(rows) < 100:
        print("⚠️ 爬蟲結果較少，可能網路不穩，嘗試備援...")
        rows = fetch_fallback_hardcoded()

    # 寫入檔案
    success = write_universe_csv(rows, output_path)

    if success:
        print(f"🚀 現在系統會用這個完整清單：")
        print(f"   ├─ 每天早上 6:00 → scan_signals（掃描全市場）")
        print(f"   ├─ 每週一 9:00 → weekly_universe_scan（深度掃描）")
        print(f"   └─ 結果會顯示在「投機」頁面")
        print()
        print(f"💡 重啟 Docker 後生效：")
        print(f"   docker-compose restart")
        return 0
    else:
        print("❌ 生成失敗")
        return 1

if __name__ == '__main__':
    sys.exit(main())
