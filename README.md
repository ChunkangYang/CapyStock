# CapyStock

日股籌碼分析工具 — 追蹤主力動向、產生進出場警示。

## 安裝

```bash
pip install -r requirements.txt
```

## 使用

```bash
# 加入追蹤（股票代號 + 追蹤起始價）
python -m capystock.main add 7203 2500

# 顯示追蹤清單
python -m capystock.main list

# 移除追蹤
python -m capystock.main remove 7203

# 執行分析（全部）
python -m capystock.main check

# 只分析指定代號
python -m capystock.main check --code 7203

# 查看過去 30 天警示歷史
python -m capystock.main log --days 30

# 單獨查 EDINET 5% rule 申報（watchlist 範圍）
python -m capystock.main edinet --days 7

# 掃全市場所有 5% rule 申報
python -m capystock.main edinet --days 3 --all

# check 時停用 EDINET
python -m capystock.main check --no-edinet
```

## EDINET 設定

金融廳免費 API。申請 key：https://disclosure2.edinet-fsa.go.jp/weee0020.aspx

於 `data/.env` 寫入：
```
EDINET_API_KEY=<your_key>
```

第一次執行會自動下載 `Edinetcode.zip` 對照表並快取至 `data/cache/edinet/`。
之後 `check` 會自動顯示 watchlist 內股票最近 3 日的 5% rule 申報（外資持股、
自己株買付、機構增減持等）。

## 選填資料（信用残 / 投資部門別）

日本公開免費來源不穩定提供個股信用残歷史與每日法人買賣超，
如有自備資料可放在：

### `data/cache/{code}_margin.csv` — 週度信用残
```csv
week,margin_long,margin_short,ratio
2026-04-11,18200,4100,4.44
2026-04-18,19100,3900,4.90
2026-04-25,22500,3500,6.43
```

### `data/cache/{code}_flow.csv` — 每日投資部門別買賣超
```csv
date,foreign_net,institution_net,individual_net
2026-04-20,+3200,+1500,-4800
2026-04-21,-1200,-800,+2100
```

單位：千股（正值為買超、負值為賣超）。缺檔時 analyzer 會跳過對應
條件但仍評估股價位階與停損。

## 判斷邏輯與參數

詳見 [`CLAUDE.md`](./CLAUDE.md) 與 [`capystock/config.py`](./capystock/config.py)。
