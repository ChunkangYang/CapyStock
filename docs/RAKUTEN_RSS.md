# 樂天 RSS 資料匯出指引

## 目的

從樂天マーケットスピード II RSS 取得**個股日頻信用残**（取代現有的週頻 JPX 估算），讓「融資暴增」條件能提早 1-2 週判斷。

## 為何不用 REST API？

樂天證券沒有公開 REST API。RSS 是樂天自研的 RTD（Real-Time Data）函數，**只能在 Excel 儲存格裡呼叫**。本腳本透過 `pywin32` 自動化 Excel 抓取，再寫回 CSV。

## 前置條件（缺一不可）

| 條件 | 確認方式 |
|---|---|
| Windows 10/11 | ✅ 你目前環境 |
| Microsoft Office Excel | 開 Excel 確認版本（**不接受** Excel Online / WPS / LibreOffice） |
| マーケットスピード II 安裝並登入 | [下載](https://marketspeed.jp/ms2/onlinehelp/) |
| RSS 利用權限開通 | 需符合任一：① 信用口座開設 ② 過去 3 個月有股票/投信交易 ③ 預存金 ≥ ¥300,000 |
| Python 套件 | `pip install pywin32 pandas`（已自動安裝） |

## 確認 RSS 已通

1. 啟動マーケットスピード II 並登入
2. 開啟一個新 Excel 檔，輸入：
   ```
   =RssMarket("7203.T","現在値")
   ```
3. 應出現豐田汽車即時股價

如果回傳：
- `#NAME?` → Excel 沒載入 RSS 插件（COM アドイン → 勾「楽天 RSS」）
- `#N/A` → マケスピ II 沒開或沒登入
- `0` → RSS 權限未開通，去樂天 web 申請

## 執行

```bash
# 抓 watchlist 全部
python scripts/rakuten_rss_fetch.py --watchlist

# 指定股票
python scripts/rakuten_rss_fetch.py --codes 7203,6758,9984

# 全市場（>3000 檔，慢，建議排程跑）
python scripts/rakuten_rss_fetch.py --all --delay 0.3
```

**執行中請勿關閉マーケットスピード II 與 Excel**（Excel 在背景開，跑完自動關）。

## 輸出

```
data/cache/{code}_margin_daily.csv  # 個股日頻信用残
data/cache/_rakuten_rss_report.json # 匯出摘要與失敗清單
```

CSV 欄位：
| 欄位 | 說明 | 單位 |
|---|---|---|
| date | 日期 | YYYY-MM-DD |
| margin_long | 信用買殘 | 千株 |
| margin_short | 信用売殘 | 千株 |
| ratio | 信用倍率 | - |

## 已知限制

1. **RSS 推送時間**：每檔需 1-3 秒讓 RTD 穩定，3000 檔約 15-30 分鐘
2. **マケスピ II 必須前景執行**：最小化可、關閉不行
3. **資料新鮮度**：信用残東証本身是 T+2 公布（週四公布週二的數據），RSS 拉到的也是這個 lag，但比 JPX 週頻好
4. **個股法人/外資 flow 無法取得**：樂天 RSS 沒有這個欄位，這是 TSE 機構付費資料

## 排程建議

平日 18:00（東証收盤 + 兩小時，等信用残更新）跑一次 `--watchlist`。週四另外跑 `--all` 全市場更新。

未來可整合進 GitHub Action（但 Action 跑在 Linux 上，無法用 pywin32）→ 需本機排程（Windows 工作排程器）。
