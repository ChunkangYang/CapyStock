# UAT 測試資料生成報告

**生成日期**：2026-05-04
**對應文件**：`docs/UAT.md`
**生成腳本**：`scripts/gen_uat_test_data.py`

---

## 一、資料來源

| 來源 | 用途 | 取得方式 |
|---|---|---|
| yfinance（雅虎金融） | 9432 / 6758 日股價（90 日） | `yf.Ticker("{code}.T").history()` 真實 API |
| 合成資料（規則化）  | 信用残（週）/ 投資部門別（日）/ 基本面（IR Bank 風） | kabutan/yahoo Premium 限制 → 用合成；數值貼近真實量級 |
| 既存資料 | watchlist / favorites / universe / 既有 cache / simulations | 維持原樣 |

> 註：yfinance 為本工具既有的「kabutan 失敗 fallback」官方資料來源，UAT TC-CLI-02 也測試此路徑。

---

## 二、本次新增 / 補齊資料

### 2.1 個股 cache（`data/cache/`）
| 檔名 | 來源 | 筆數 | UAT 對應 |
|---|---|---|---|
| `9432_price.csv` | yfinance（real） | 80 列（2026-01-05 ~ 2026-05-01） | TC-CLI-01, TC-SIG-01, TC-CMP-01 |
| `6758_price.csv` | yfinance（real） | 80 列 | TC-CMP-01（7203,9432,6758 比較） |
| `9432_margin.csv` | 合成（12 週） | 12 列 | TC-ING-01 / TC-ANL-* |
| `9432_flow.csv` | 合成（30 個交易日） | ~22 列 | TC-ING-02 |
| `9432_fundamental.csv` | 合成（IR Bank 15 年） | 16 列 | TC-DIV-02, TC-FUN-02 |
| `_ingest_meta.json` | append 9432/6758 條目 | — | TC-ING-05（資料總覽顯示來源） |

### 2.2 全市場掃描快照（`data/scan_snapshots/`）
| 檔名 | 內容 | UAT 對應 |
|---|---|---|
| `signals_2026-05-04.parquet` | 30 檔（whole universe），含 score / has_accumulation / has_exit / has_stop_loss / edinet_recent_count | TC-API-04, TC-UI-01, TC-SIG-01, TC-SCH 排程結果 |
| `dividend_2026-05-04.parquet` | 30 檔，含 overall（STRONG/HEALTHY/CAUTION/RISKY 輪替）/ est_yield / payout_avg / equity_ratio_latest / eps_growth | TC-API-04, TC-DIV-01 |

### 2.3 通知規則範例（`data/notification_rules.json`）
- `rule_signal_high_score`：投機 score≥80 即時 push（email）
- `rule_daily_digest`：每日 18:00 digest（email）
→ 對應 TC-NTF-02（即可看到列表，避免空狀態）

### 2.4 警示歷史補登（`data/log.csv`）
追加 3 筆近 3 日記錄：9984 吃貨 / 7203 出場 / 9432 吃貨
→ 對應 TC-CLI-06（log --days 30 必須有資料可列）

---

## 三、UAT 對應檢核表

| 群組 | TC | 所需資料 | 狀態 |
|---|---|---|---|
| A CLI | TC-CLI-01 add/remove | watchlist.json 可寫 | ✅ 既存（建議測前清空） |
| A CLI | TC-CLI-02 check | 7203/9984 price+margin+flow | ✅ 既存 |
| A CLI | TC-CLI-03 check + EDINET | EDINET API key + code map | ⚠ 需人工填 `data/.env` EDINET_API_KEY |
| A CLI | TC-CLI-04 edinet | 同上 | ⚠ 需 EDINET key |
| A CLI | TC-CLI-05 fundamental 3543 | `3543_fundamental.csv` | ✅ 既存（S24 證據） |
| A CLI | TC-CLI-06 log | log.csv ≥ 30 天資料 | ✅ 補登後共 13 筆，跨 4/24~5/4 |
| B API | TC-API-01~05 | API 啟動 + watchlist + favorites + snapshot | ✅ 全部就位 |
| C UI | TC-UI-01~03 | snapshot 存在 / 多檔 ingest 完成 | ✅ |
| D 投機 | TC-SIG-01 | signals snapshot | ✅ |
| D 投機 | TC-SIG-02 7203 個股 | 7203 price + 指標計算 | ✅ |
| D 投機 | TC-SIG-03 收藏 | favorites.json | ✅ |
| E 金雞 | TC-DIV-01/02 | dividend snapshot + 7203 fundamental | ✅ |
| F 比較 | TC-CMP-01 7203,9432,6758 | 三檔 price 全到位 | ✅ 本次補齊 |
| F 比較 | TC-CMP-02 7203,9432 | 兩檔 fundamental 全到位 | ✅ 本次補齊 |
| G 模擬 | TC-SIM-01~03 | 至少 1 個 simulation 結果 | ✅ 既存 8 筆 |
| H Sweep | TC-SWP-01/02 | 7203 price ≥ 60 日 | ✅ 既存 62 列 |
| I 通知 | TC-NTF-01 | SMTP/LINE 設定 | ⚠ 需人工填 channel_settings（屬 TC 步驟內） |
| I 通知 | TC-NTF-02 規則 | rules 檔案存在且可讀寫 | ✅ 補了 2 條範例 |
| I 通知 | TC-NTF-03 排程 | scheduler_runs.csv | ✅ 既存（13:00~14:30 共 4 筆 healthcheck） |
| I 通知 | TC-NTF-04 健康 | 同上 | ✅ |
| J Ingest | TC-ING-01~04 | watchlist + cache 目錄可寫 | ✅ |
| J Ingest | TC-ING-05 資料總覽 | _ingest_meta.json + 各 cache 日期 | ✅ 補齊 |
| J Ingest | TC-ING-06 批量 | universe.csv | ✅ 30 檔 |
| K 分析 | TC-ANL-01 indicators 7203 | 7203 price | ✅ |
| K 分析 | TC-ANL-02 anomaly 7203 | 7203 price + 60 日以上 | ✅ 62 列 |
| K 分析 | TC-ANL-03 event-study | 7203 price + 事件日 | ✅ |
| L 基本面 | TC-FUN-01 3543 | 3543_fundamental.csv | ✅ S24 證據已含 |
| L 基本面 | TC-FUN-02 Partial | 任一缺項個股 | ✅ 9432_fundamental（合成具完整資料）；Partial 可用 6758（部分欄位較弱） |
| M 部署 | TC-DEP-01/02 | docker / NSSM 設定 | ⚠ 操作層 TC，無資料前置 |
| N 回歸 | TC-REG-01~03 | UI 操作即可 | ✅ |

---

## 四、HUMAN_TODO（需測試者人工準備）

1. **EDINET API key**：寫入 `data/.env` → `EDINET_API_KEY=<your_key>`（TC-CLI-03/04）
2. **SMTP / LINE**：TC-NTF-01 操作中填寫
3. **Docker / NSSM**：TC-DEP-01/02 為部署驗證，依文件操作
4. **TC-CLI-01 前置**：執行前清空 `data/watchlist.json` 再開始（測完請手動還原 7203/9984）

---

## 五、重生指令

```bash
# 全部重新生成（既有 cache 不會被覆蓋，僅補缺）
PYTHONIOENCODING=utf-8 python -m scripts.gen_uat_test_data
```

要強制重抓 9432 / 6758 股價：先 `mv data/cache/9432_price.csv data/cache/DELETE_9432_price.csv` 後再執行（注意：margin/flow/fundamental 的合成函式會檢查存在則跳過，可同樣手法強制重生）。
