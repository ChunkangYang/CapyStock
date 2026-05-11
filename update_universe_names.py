#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""從 Kabutan 更新 universe.csv 的日文名稱（只爬英文的股票）"""

import pandas as pd
from capystock import scraper
import sys
import io
import time
from datetime import datetime

# 設定 UTF-8 編碼
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 準備 log 檔案
log_file = open('update_universe.log', 'a', encoding='utf-8')

def log_print(msg):
    """同時輸出到螢幕和 log 檔案"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    log_file.write(full_msg + "\n")
    log_file.flush()

def is_japanese(text):
    """檢查是否為日文"""
    if not text:
        return False
    return any(ord(c) > 0x3040 for c in str(text))

# 讀現有清單
universe = pd.read_csv('data/universe.csv')
total = len(universe)

# 找出還是英文的股票
english_rows = universe[~universe['name'].apply(is_japanese)]
english_count = len(english_rows)

log_print(f"\n{'='*70}")
log_print(f"Start updating {english_count} English stocks from Kabutan...")
log_print(f"Estimated time: ~{english_count * 2 / 60:.0f} minutes")
log_print(f"{'='*70}\n")

updated = 0
failed = 0
start_time = time.time()

for idx, row in universe.iterrows():
    code = str(row['code']).zfill(4)
    old_name = row['name']

    # 只爬英文名稱的股票
    if is_japanese(old_name):
        continue

    # 從 Kabutan 取日文名稱
    name = scraper.fetch_name(code)

    if name and name != old_name:
        universe.at[idx, 'name'] = name
        updated += 1

        # 每個都輸出
        elapsed = time.time() - start_time
        remaining = (english_count - updated) * 2 / 60  # 分鐘
        progress_pct = updated / english_count * 100

        log_print(f"[{updated:4d}/{english_count}] Code: {code} UPDATED | Progress: {progress_pct:5.1f}% | Remaining: {remaining:5.1f}min")
    elif not name:
        failed += 1

    # 每 20 個存一次進度
    if (updated > 0) and (updated % 20 == 0):
        universe.to_csv('data/universe.csv', index=False, encoding='utf-8')
        elapsed = time.time() - start_time
        log_print(f"  [SAVED] {updated}/{english_count} records saved to file")

# 最終保存
universe.to_csv('data/universe.csv', index=False, encoding='utf-8')
total_time = time.time() - start_time

log_print(f"\n{'='*70}")
log_print(f"DONE! Updated: {updated} stocks")
log_print(f"Failed: {failed} stocks")
log_print(f"Total time: {total_time/60:.1f} minutes")
log_print(f"{'='*70}\n")

log_file.close()
