# CapyStock — 日股籌碼分析工具

## 🔴 絕對規則（最高優先，違反即 P0）

### 1. 嚴禁刪除指令
- **禁止使用任何刪除/清空指令**：`rm`（含任何旗標）、`Remove-Item`、`del`、`erase`、`git clean`、`git stash`、`git reset --hard`、`git checkout -- *`、`git restore .` 等
- **要「移除」檔案時，唯一作法**：改名加 `DELETE_` prefix，例如 `mv old.py DELETE_old.py` 或 `Rename-Item old.py DELETE_old.py`
- 是否真的要刪由使用者自己 review 跟手動清理
- 例外：無

### 2. 所有生成/修改的檔案必須立刻 git commit
- Claude 建立或修改的任何檔案（docs、tests、code、config…）都視為有意義
- 完成一個邏輯單元就 `git add <files> && git commit -m "<msg>"`，**不必詢問使用者**
- 不要擅自判斷「這是暫存/廢棄/無意義」而不 commit — 不要的使用者會自己 revert
- 「邏輯單元」：完成一個子任務 / 新建 .md / 一輪測試完 / chat 結束前
- chat session 最後一個動作必為 commit
- 不 push（push 仍需明確要求）
- .gitignore 已排除的路徑（`data/cache/`、`__pycache__/` 等）不用塞

違反這兩條會造成使用者資料永久遺失（已發生過：UAT.md、scan_snapshots/*.parquet）。

---

## 專案目標
追蹤日本上市股票的主力動向（外資/法人買賣超、信用残變化、股價位階），
輸出持倉警告、停損觸發、吃貨訊號，輔助進出場判斷。

## 品牌前綴
專案名稱 `CapyStock`，遵循 Capy* 命名規則。

## 技術棧
- Python 3.10+
- CLI：argparse
- 爬蟲：requests + BeautifulSoup4 + lxml
- 備援資料：yfinance
- 表格輸出：tabulate
- 儲存：JSON（追蹤清單）、CSV（歷史 log、各股票快取）

## 資料來源

### 主要：kabutan.jp（免費爬蟲）
| 資料類別 | URL 模板 | 更新頻率 |
|---------|----------|----------|
| 股價 / 成交量 | `https://kabutan.jp/stock/kabuka?code={CODE}&ashi=day&page={PAGE}` | 日 |
| 個股總覽 / 名稱 | `https://kabutan.jp/stock/?code={CODE}` | — |

注意：kabutan 的個股信用残歷史與投資部門別為 Premium 會員專屬，免費 API
無穩定公開來源。本工具改由本地 CSV 載入（見下方）。

### 備援：yfinance
- 當 kabutan 爬取失敗時，自動改用 `yfinance.Ticker("{CODE}.T")` 取得股價與成交量。
- yfinance 不提供日本信用残資料，故該欄位僅依賴 kabutan。

### EDINET（金融廳官方 API）— 5% rule 自動監控
- 用途：個股「大量保有報告書」（docTypeCode 350）與変更報告書（360），
  即 >5% 持股申報、連動外資/機構建倉或減倉訊號。
- Endpoint：`https://api.edinet-fsa.go.jp/api/v2/documents.json`
- 認證：`Subscription-Key` query param；key 存於 `data/.env`（`EDINET_API_KEY=...`）
- edinetCode → 証券コード 對照檔：自動下載 `Edinetcode.zip`（官方），快取於
  `data/cache/edinet/edinet_code_map.csv`（CP932 → UTF-8）
- 在 `check` 時自動附帶（預設回掃 3 日），也可獨立 `python -m capystock.main edinet --days 30`

### 本地 CSV 補充資料（可選）
| 資料類別 | 路徑 | 欄位 | 單位 |
|---------|------|------|------|
| 信用残（週） | `data/cache/{CODE}_margin.csv` | `week,margin_long,margin_short,ratio` | 千株 |
| 投資部門別（日） | `data/cache/{CODE}_flow.csv` | `date,foreign_net,institution_net,individual_net` | 千株 |

- 缺 `_margin.csv` → 跳過條件 2（融資暴增）
- 缺 `_flow.csv` → 跳過條件 1（法人連賣）、吃貨訊號
- 其他條件（股價離低點、停損）仍會評估。

## 單位約定
- **金額**：日圓（JPY），不做匯率換算。
- **張數**：千股（千株），即 kabutan 原始單位。成交量欄位直接為千株數。
- **百分比**：以小數表示，輸出時 ×100。

## 判斷邏輯參數（位於 `capystock/config.py`）

### 持倉出場（三選二即警告）
1. `INSTITUTIONAL_SELL_CONSECUTIVE_DAYS = 3`
   `INSTITUTIONAL_SELL_RATIO_OF_PRIOR_10D_BUY = 0.20`
2. `MARGIN_INCREASE_CONSECUTIVE_WEEKS = 3`
   `MARGIN_INCREASE_VS_8W_MEAN = 2.0`
3. `PRICE_RISE_FROM_RECENT_LOW = 0.30`（近 30 日最低）

### 停損
- `STOP_LOSS_DROP_PCT = 0.05`（相對追蹤起始價）
- `STOP_LOSS_CONSECUTIVE_DAYS = 2`

### 吃貨訊號
- `ACCUMULATION_INSTITUTIONAL_BUY_DAYS = 5`（外資或法人連續買超日數）
- 同期信用残融資餘額下降 → 成立

### 爬蟲禮貌參數
- `REQUEST_DELAY_SECONDS = 2.0`（每次 HTTP 間隔）
- `USER_AGENT = "CapyStock/1.0 (+personal portfolio tracker)"`

## 檔案結構
```
CapyStock/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── capystock/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── scraper.py
│   ├── analyzer.py
│   └── storage.py
├── data/
│   ├── watchlist.json      # 追蹤清單
│   ├── log.csv             # 警示歷史（append-only）
│   └── cache/              # 各股票快取（price/margin/flow CSV）
```

## 操作
```
python -m capystock.main add 7203 2500
python -m capystock.main remove 7203
python -m capystock.main check
python -m capystock.main log [--days 30]
```

## 未完成 / 未來擴充
- [ ] 自動寄發 email / LINE 通知
- [ ] 週末自動排程 cron
- [ ] 技術指標（RSI、MACD）輔助
- [ ] 多檔股票批次比較面板
