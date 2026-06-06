# 全市場「三個訊號都不觸發」資料流審計

- 日期：2026-06-06
- 觸發問題：抓了最新資料後，全市場畫面看不到任何「吃貨 / 出貨 / 停損」訊號
- 結論先講：**這不是「資料平淡沒 hit」，而是三個彼此獨立的原因**——其中出貨明明有 250+ 檔 hit，是快取與快照雙重 stale 害你看不到。

---

## 0. 一句話總結

| 條件 | 全市場快照現況 | 真實原因 | 是不是資料問題 |
|------|----------------|----------|----------------|
| 吃貨 accumulation | 恆 0 | analyzer 裡產生 accumulation 的程式碼被 commit `bf333049` 移除 | ❌ 程式碼問題 |
| 停損 stop_loss | 恆 0 | 全市場非持倉、無進場價，停損錨點退化成「最新價×0.95」，結構上不可能觸發 | ❌ 結構問題 |
| 出貨 exit | 顯示 0，實際 250+ | data/cache 與快照雙重 stale；fresh 重算其實有大量 exit | ⚠️ 快取/快照 stale |

---

## 1. 根因：兩個 source of truth + 斷掉的 invalidation chain

```
雲端抓取 (scripts/cloud_fetch.py，GitHub Action)
   └─> data/cloud-cache/*.csv        ← 你「剛抓的最新」寫這裡
            │
            │  ❌ sync 複製步驟（api/routers/data.py 把 cloud-cache → cache）沒被執行
            ▼
        data/cache/*.csv             ← analyzer / scan 唯一實際讀取的來源
            │                          （capystock/config.py: CACHE_DIR = data/cache）
            ▼
        analyzer.analyze()
            ▼
        全市場快照 data/scan_snapshots/signals_YYYY-MM-DD.parquet  ← 前端全市場畫面讀這個
```

兩個快取沒有任何 invalidation chain 串接：
- `data/cloud-cache/`：雲端抓取寫入。目前部分到 **2026-06-05**，但**只有 318 檔**更新到 6/05，**3359 檔**還停在 **5/26**（雲端抓取分批、尚未抓完）。
- `data/cache/`：analyzer/scan 唯一讀取來源。目前停在 **5/22~5/26**（mtime 5/23 之後沒被寫過）。
- `api/routers/data.py` 的 sync 端點（line 232-233：複製 cloud-cache → cache）**沒有被執行**，所以「按了抓取」只更新了 cloud-cache，analyzer 讀的 data/cache 仍是舊的。

### 證據（135A）

| 來源 | 最後日期 | close | mtime |
|------|----------|-------|-------|
| data/cloud-cache/135A_price.csv | 2026-06-05 | 3820 | 06-06 17:26 |
| data/cache/135A_price.csv | 2026-05-22 | 4480 | 05-23 08:42 |

快照 signals_2026-06-06.parquet 的 latest_price：**3746/3746 筆全部對應 cloud-cache，0 筆對應 data/cache**。
→ 快照是對 cloud-cache 算的，但 analyzer 平時讀的是 data/cache。兩條讀取路徑指向不同資料。

---

## 2. 三條失效路徑逐一拆解

### ① 吃貨 accumulation —— 程式碼被刪，永遠不會觸發
- 全專案 grep `accumulation`，產生 alert 的程式碼**完全不存在**，只剩 `capystock/analyzer.py:7` 的註解字串。
- commit `bf333049 fix: 移除 Snapshot 已刪除的 cond_inst_sell / accumulation_signal 引用` 把吃貨邏輯整包移除。
- 因此 `SignalScanRow.has_accumulation`（`api/services/scan_service.py:132`）**恆為 False**，與資料新舊無關。

### ② 停損 stop_loss —— 全市場結構性不可能觸發
- 全市場股票非 watchlist，`api/services/signal_service.py:131-133` 把 `start_price` 設為「最新收盤價自己」。
- `capystock/analyzer.py:215` 停損錨點 = `start_price × (1 - 5%)` = 最新價 × 0.95，最新價永遠不會 < 自己的 95%。
- 三階段移動停損（`_check_trailing_stop`）同理：entry = 最新價、profit_pct = 0%、stop = entry×0.95，最新價不會跌破。
- 因此 `has_stop_loss` 在全市場**恆為 False**。停損本來就只對「使用者的進場價 / 主力成本」有意義，全市場沒有錨點。

### ③ 出貨 exit —— 資料其實有 hit，快照 stale
- 出貨採二選一：`cond_margin_surge`（融資連 3 週增 + 本週增幅 ≥ 8 週均 2 倍）或 `cond_price_rise`（漲離 30 日低點 ≥ 30%）。
- Fresh 重算數量：
  - data/cache（現況）：270 檔符合 cond_price_rise
  - cloud-cache（6/05）：257 檔符合 cond_price_rise + 21 檔 margin surge
- 但 17:31 的快照 `has_exit` 總數 = **0**。
- 決定性不一致：快照 1436（latest_price=1763，= cloud-cache 6/05 值）用 production 路徑 `run_signals_scan` 重算 = **has_exit=True**，快照卻記 **False**。同一份資料、同一條程式路徑、結果相反 → 快照旗標沒反映真實重算（stale）。

#### 實測對帳（production 路徑 run_signals_scan）

| 讀取來源 | 135A | 1436 | 1407 |
|----------|------|------|------|
| data/cache（4480/5-22） | exit=True | exit=True | exit=True |
| cloud-cache（6-05） | exit=False(0.224) | **exit=True(0.549)** | exit=False(0.108) |
| 17:31 快照 | False | **False（不一致）** | False |

---

## 3. 修復方向（待 review，本次未動程式）

1. **接通 cache invalidation（最優先）**：把「抓取/同步」做成單一原子動作鏈——cloud-cache → 複製進 data/cache → 重算快照，讓三者單一 source of truth，根治 exit stale。
2. **還原吃貨邏輯**：把 accumulation 訊號（外資/法人連買 + 融資餘額下降）重新實作回 analyzer，需 flow CSV 資料。
3. **修停損在全市場的定義**：全市場無進場價，停損欄目前恆 0。改成只對 watchlist/持倉顯示，或改用技術性破位判準。

---

## 4. 驗證指令備忘（重現本審計）

```bash
# 快照三旗標統計（應全 0）
python -c "import pandas as pd; df=pd.read_parquet('data/scan_snapshots/signals_2026-06-06.parquet'); print(df[['has_accumulation','has_exit','has_stop_loss']].sum())"

# 快照 latest_price 對應哪個快取（應 100% 對 cloud-cache）
# cloud-cache fresh 重算 exit 數量（應 250+）
# production 路徑對 1436 重算（cloud-cache）應得 has_exit=True
```
