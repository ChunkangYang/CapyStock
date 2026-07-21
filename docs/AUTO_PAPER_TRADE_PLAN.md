# 自動模擬交易（GitHub Actions 每日跑，零 LLM）— 可行性與計畫

日期：2026-07-21　狀態：計畫（待實作）

## 結論：可行，且大部分零件已經在了

現成可複用：
- 訊號：`api/services/pocket_service.scan_pocket_list()`（三盤濾網，純本地 CSV + EDINET，門檻已是數值化 config，本來就不需要 LLM）
- 帳本：`api/services/ledger_service`（`add_trade` / `advance_trade` 棘輪移動停損 / `advance_all`）
- 資料：`data/cloud-cache/*_price.csv|_margin.csv` 已由 [price-fetch.yml](../.github/workflows/price-fetch.yml)（JST 15:40）與 cloud-fetch.yml 每天更新並 commit 進 repo
- 儲存：`data/ledgers/*.json` **已在版控內** → Actions commit 完，本地 `git pull` 就看得到，前端 `/ledger` 零改動直接顯示

要新寫的只有「資金/部位規則 + 每日 driver 腳本 + 一個 workflow」。

## 三個必須先解掉的坑（已查證）

1. **Actions runner 沒有 `data/cache/`**（.gitignore 排除），但 pocket/ledger 全部讀 `data/cache`。
   → 解法：workflow 第一步把 `data/cloud-cache/*` 複製成 `data/cache/*`（11k 檔，數秒），**不改任何程式碼路徑**，零回歸風險。
2. **第一盤輸入 `data/cache/edinet/daily/*.json` 不在 repo**（只有本地 scheduler 產生，最新只到 2026-06-07 已 stale）。
   → 解法：driver 先跑 `edinet.backfill_daily(days=7)`（Actions 已有 `EDINET_API_KEY` secret），並把 daily JSON 一併 commit 到 `data/cloud-cache/edinet/daily/`，順便治好本地那份 stale。
3. **雙寫衝突**：Actions 與本地 server 都會呼叫 `advance_all()` → 同一 JSON 兩邊改 → git 衝突 + 重複推進。
   → 解法：`Ledger` 加 `owner: "user" | "bot"` 欄位；bot 帳本固定 id `auto-pocket`（檔名 `auto-pocket.json`）。
   　本地 `advance_all()` **跳過 owner=="bot"**、API 的 add/delete trade 對 bot 帳本回 403；Actions 只碰 bot 帳本。單一寫入者，衝突歸零。

## 交易規則（寫死腳本，無 LLM）

進場（每個交易日收盤後）：
- 來源：當日 pocket 掃描的「三關全過」名單
- 排序：`gate3.drop_pct` 由大到小（融資減得最多＝籌碼最乾淨），與現行前端排序一致
- 過濾：已有 open 部位的同一 code 不重複買；價格資料日期非當日 → 該檔跳過（防 stale 進場）
- 部位：每筆固定金額 `AUTO_TRADE_POSITION_JPY`，股數 = `floor(金額 / 收盤價 / 100) × 100`（日股單位 100 股），不足 1 單位跳過
- 上限：`AUTO_TRADE_MAX_OPEN`（同時最多持倉檔數）、`AUTO_TRADE_MAX_NEW_PER_DAY`（單日最多新進場）、現金不足即停
- 成交價：**當日收盤價**（無 look-ahead；盤中價不可得也不該用）

出場：沿用既有棘輪移動停損 `advance_trade`（`stop_pct = AUTO_TRADE_STOP_PCT`），Actions 每日推進到最新收盤。

成本模型（可選開關）：`AUTO_TRADE_FEE_BPS`（單邊手續費 bps）+ `AUTO_TRADE_SLIPPAGE_BPS`，預設 0；建議進場價 ×(1+slippage)、出場 ×(1−slippage) 記帳，讓績效不虛胖。

預設值建議（`capystock/config.py`）：
```
AUTO_TRADE_ENABLED          = True
AUTO_TRADE_LEDGER_ID        = "auto-pocket"
AUTO_TRADE_INITIAL_CASH_JPY = 3_000_000
AUTO_TRADE_POSITION_JPY     = 300_000     # 每筆固定 30 萬 → 滿倉約 10 檔
AUTO_TRADE_MAX_OPEN         = 10
AUTO_TRADE_MAX_NEW_PER_DAY  = 3
AUTO_TRADE_STOP_PCT         = 0.10
AUTO_TRADE_FEE_BPS          = 0
AUTO_TRADE_SLIPPAGE_BPS     = 0
```
（2026-06-07 快照口袋名單 24 檔 → 若不設上限會一天開 24 個部位，所以上限是必要的。）

## 實作清單

| # | 檔案 | 內容 |
|---|---|---|
| 1 | `capystock/config.py` | 上表 `AUTO_TRADE_*` 參數 |
| 2 | `api/schemas/ledger.py` | `Ledger.owner: Literal["user","bot"] = "user"`；`Trade.entry_reason: str = ""`（記「pocket 三關 drop_pct=..」）；`Ledger.cash_jpy: float`（bot 帳本現金部位） |
| 3 | `api/services/ledger_service.py` | `advance_all(include_bot=False)` 預設跳過 bot；`get_or_create_bot_ledger()` |
| 4 | `api/routers/ledger.py` | bot 帳本禁止 add/delete trade（403），GET 照常 |
| 5 | **`scripts/auto_paper_trade.py`**（新，核心） | ① materialize cache ② `edinet.backfill_daily(7)` ③ `scan_pocket_list()` ④ `advance`（先出場再進場）⑤ 依規則選股下單 ⑥ 寫帳本 + `data/auto_trade_log/YYYY-MM-DD.json` 當日決策紀錄（含被跳過的原因，便於事後追）⑦ 印摘要供 Telegram |
| 6 | **`.github/workflows/paper-trade.yml`**（新） | `cron: "0 8 * * 1-5"`（JST 17:00，在 price-fetch 15:40 之後）+ `workflow_dispatch`（含 `dry_run` 輸入）；`concurrency: paper-trade`；commit 限定 `data/ledgers/auto-pocket.json data/auto_trade_log/ data/cloud-cache/edinet/daily/`；`git pull --rebase` 後 push；Telegram 通知「今日買 X 檔 / 停損出場 Y 檔 / 總市值 Z」 |
| 7 | `frontend/.../ledger` | bot 帳本顯示 🤖 badge + 隱藏「加入/刪除交易」鈕（唯讀） |
| 8 | `tests/unit/test_auto_paper_trade.py` | 純函式 `select_new_trades(pocket_rows, ledger, cash, config)`：上限/重複持股/不足 1 單位/現金不足/stale 價格跳過；`advance_all` 不碰 bot 帳本 |

## 驗證方式（不用等一週）

`scripts/auto_paper_trade.py --replay 2026-06-07..2026-07-18`：用既有 pocket 快照 + price CSV 逐日重放，一次跑出兩個月的模擬績效與交易明細。這同時是「策略到底有沒有用」的第一份實測，也是 workflow 上線前的煙霧測試。

## 風險 / 已知限制

- 進出場都是收盤價成交，實務有跳空與流動性問題（小型股尤其），績效偏樂觀 → 用 slippage 參數補
- 三盤依賴 EDINET 申報，候選池天生偏少且申報有 5 個營業日延遲；margin 週資料也有延遲，訊號本質是「慢訊號」
- Actions cron 會延遲，若 price-fetch 當天失敗，driver 應**偵測 price CSV 最新日期 ≠ 當日就整個跳過不交易**（寧可不交易，不要拿舊價下單）
- 這是模擬，不接券商；任何實盤化都是另一個決策

## 時序

```
JST 15:30 東證收盤
JST 15:40 price-fetch.yml   → cloud-cache 收盤價 commit
JST 17:00 paper-trade.yml   → 推進停損 + 依三盤下單 → ledgers commit  ← 新
JST 17:00 本地 price_sync（既有，只拉 price，不動 bot 帳本）
隔日 08:00 daily_pipeline（既有）
```
本地要看結果：`git pull` 或 Dashboard 雲端同步後開 `/ledger`。
