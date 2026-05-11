#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用新的 universe.csv 中的日文名稱，替換快照中的英文名稱"""

import pandas as pd
from pathlib import Path
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = Path("data")
SNAPSHOTS_DIR = DATA_DIR / "scan_snapshots"

# 讀新的 universe.csv（含日文名稱）
print("讀取 universe.csv...")
universe = pd.read_csv(DATA_DIR / "universe.csv")
print(f"  載入 {len(universe)} 筆股票資料\n")

# 建立 code -> name 的映射
code_to_name = dict(zip(
    universe['code'].astype(str).str.zfill(4),
    universe['name']
))

# 處理所有 parquet 快照
snapshots = list(SNAPSHOTS_DIR.glob("*.parquet"))
snapshots = [s for s in snapshots if not s.name.startswith("DELETE_")]
snapshots.sort(key=lambda x: x.stat().st_mtime, reverse=True)

print(f"找到 {len(snapshots)} 個快照：\n")

for snapshot_path in snapshots:
    print(f"處理: {snapshot_path.name}")

    try:
        # 讀快照
        df = pd.read_parquet(snapshot_path)
        original_count = len(df)

        # 將 code 轉成字串，補前導 0
        df['code'] = df['code'].astype(str).str.zfill(4)

        # 映射新名稱
        df['name'] = df['code'].map(code_to_name)

        # 統計更新結果
        updated = (~df['name'].isna()).sum()
        not_found = df['name'].isna().sum()

        print(f"  原筆數: {original_count}")
        print(f"  已映射: {updated}")
        print(f"  未找到映射: {not_found}")

        if not_found > 0:
            failed_codes = df[df['name'].isna()]['code'].unique().tolist()
            print(f"  未找到的 code: {failed_codes[:5]}")

        # 存回快照（強制覆蓋）
        print(f"  正在寫入...", end=' ', flush=True)
        df.to_parquet(snapshot_path, index=False, engine='pyarrow')
        print("✓ 成功")

        # 驗證
        verify_df = pd.read_parquet(snapshot_path)
        verify_count = (~verify_df['name'].isna()).sum()
        print(f"  驗證: {verify_count}/{original_count} 筆已更新\n")

    except Exception as e:
        print(f"  ❌ 錯誤: {e}\n")

print("完成！")
