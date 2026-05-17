# Evidence：訊號顯示單一資料流重構

## 背景
2026-05-17 重構前，訊號顯示有 5 層獨立快取互不通知，每次資料更新後同一檔股票在不同 tab / endpoint 顯示不一致。詳見根因分析：[memory feedback_architecture_discipline](../../C:/Users/cky19/.claude/projects/c--Users-cky19-Documents-workspace-CapyStock/memory/feedback_architecture_discipline.md)。

## 重構後架構

```
唯一 source of truth：data/cache/*.csv  ← cloud-sync 寫入

           ↓ analyze_one (cache-first，~16ms/檔)

  /scan/signals 即時計算          /signals/{code} 即時計算
  （in-mem cache by CSV mtime）   （讀 watchlist 為 start_price）

           ↓ 都走同一條 compute path → 結果永遠一致

  前端 localStorage（純性能優化，「全部更新」按鈕清掉）
```

歷史 parquet 仍存在於 `data/scan_snapshots/`，但**只有指定 `?date=YYYY-MM-DD` 時才會被讀取**，預設一律即時算。

## 一鍵 fresh 流程
使用者操作：**只按一個按鈕**

```
資料設定頁 → 雲端同步
  ↓
後端：1. GitHub 拉最新 cloud-cache → data/cache/
      2. 自動觸發 run_signals_scan
      3. 寫 today's parquet（給歷史回溯）
      4. 回傳 {copied_count, rescan: {rows, errors}}
  ↓
前端：偵測到回應有 rescan 結果，自動清 localStorage signals 快取
  ↓
使用者打開「投機訊號」任一 tab → 看到一致的最新訊號
```

## 驗收測試（人類執行）

### TC-1：cloud-sync 後三個 tab 顯示一致
1. 跑 `POST /api/data/cloud-sync` body `{"pull": true}`，等候回應
2. 回應應含 `rescan.rows == 3747`（universe 大小）`errors == 0`
3. 打開「投機訊號 → 全市場訊號」，找 3103 ユニチカ → 應看到 🔴 + 🛑 + score 約 -5
4. 切「追蹤清單」tab，找 3103 → 應看到**相同**的 🔴 + 🛑 + 同一個 score

### TC-2：watchlist 改動立刻反映在全市場 tab
1. `python -m capystock.main add 8035 60000`（故意設遠高於現價）
2. 開「投機訊號 → 全市場訊號」，按右上「全部更新」
3. 找 8035 東京エレクトロン → 應看到 🔴 停損訊號（threshold = 60000 × 0.95 = 57000，現價 ~50000 顯然低於）
4. 切「追蹤清單」→ 8035 行的訊號 dot 應**相同**

### TC-3：兩次同步間打開頁面是即時的（in-memory cache 命中）
1. cloud-sync 後再打開「投機訊號」3 次
2. 首次 ~60 秒（CSV 變動觸發重算），後續 2 次應 < 1 秒
3. 證據：瀏覽器 Network tab 看 `/scan/signals` 的 response time

## 不變條件（invariant）
- **任何時候 `/scan/signals` 跟 `/signals/{code}` 對同一檔股票回的訊號必須相同**
- **`data/cache/*.csv` mtime 改變後，下次 `/scan/signals` 必須重新計算**
- **加股票進 watchlist 後不需任何手動 trigger，下次 `/scan/signals` 必須反映新的 start_price**

任一條被打破即代表單一 source of truth 假設被破壞，應立刻檢查是否有人偷偷加了新的快取層。

## 改動檔案
- `api/services/scan_service.py`：run_signals_scan 移除跨日 skip-cache，注入 watchlist start_price，砍 `_is_signal_scanned_today` / `_write_signal_cache`
- `api/routers/scan.py`：`/scan/signals` 預設走即時計算（in-mem cache by CSV mtime），歷史 parquet 僅在 `?date=` 時讀
- `api/routers/data.py`：cloud-sync 鏈式觸發 run_signals_scan，回傳含 rescan 結果
- `frontend/src/routes/data/+page.svelte`：sync 完成後清前端 signals 快取
- `tests/api/test_scan_router.py`：測試契約更新為新的「預設即時 / `?date=` 歷史」
- `tests/unit/test_scan_service.py`：side_effect 接受新的 analyze_one 簽章
