# Cloud Fetch 部署文件（GitHub Actions 正式版）

## 狀態
- ✅ PoC 驗證通過：Azure IP 沒被擋（yahoo_jp / minkabu / jpx 都能訪問）
- ✅ 已升級為正式版：`cloud-fetch.yml`
- ✅ 已加入「從雲端同步」按鈕：`/data` 頁面右上 `☁ 從雲端同步`

---

## 排程說明

預設排程：**每週一到五，JST 16:00（東京收盤後 1 小時）**
- 對應 cron：`0 7 * * 1-5`（UTC）
- 預設 mode：`watchlist`（只抓 `data/watchlist.json` 內的股票，避免燒額度）

修改排程：編輯 `.github/workflows/cloud-fetch.yml` 的 `cron:` 那行。Cron 語法：
```
分 時 日 月 週
0  7 *  *  1-5   = 每週一到五 UTC 07:00 = JST 16:00
0  */6 * * *     = 每 6 小時跑一次
```

修改後 commit + push 即生效。

### 手動觸發
GitHub repo → Actions → **Cloud Fetch** → Run workflow，可指定：
- `mode`：`watchlist`（預設）/ `all`（全市場 3747 檔）/ `codes`（自訂代碼）
- `codes`：當 mode=codes 時填，例如 `7203,6758`
- `kinds`：`margin` / `flow` / `margin,flow`
- `limit`：除錯用，限制檔數

### 暫停/關閉排程
Actions → Cloud Fetch → 右上 `…` → **Disable workflow**

---

## 在系統內使用（一鍵同步）

1. **重啟 API 伺服器** 讓新 endpoint 生效
2. 進 `/data` 頁面
3. 上方藍色 banner 顯示「☁ 雲端最新批次」狀態
4. 點 **☁ 從雲端同步** 按鈕：
   - 後端執行 `git fetch` + `git checkout origin/<branch> -- data/cloud-cache/`
   - 把 `data/cloud-cache/*.csv` 複製到 `data/cache/`（覆蓋本地舊資料）
   - overview 表格的 age 欄會即時刷新

**API endpoint**（給其他系統呼叫）：
- `GET /api/v1/data/cloud-sync/status` — 查最新雲端批次資訊
- `POST /api/v1/data/cloud-sync` body=`{"pull": true}` — 觸發同步

---

# Cloud Fetch 部署文件（GitHub Actions PoC）

## 目的
把「批量抓取」搬到 GitHub Actions 雲端執行，定時抓信用残 / 投資部門別 / 股價，
commit 回 repo，本地系統 `git pull` 即可拿到最新資料，**本地電腦不需常開**。

## 架構
```
GitHub Actions runner (Ubuntu, Azure IP)
   └─ python scripts/cloud_fetch.py
        ├─ YahooJpMarginSource   → data/cloud-cache/{code}_margin.csv
        ├─ MinkabuMarginSource   ↗
        └─ JpxFlowSource         → data/cloud-cache/{code}_flow.csv
   └─ git commit & push 回原分支
本地：
   git pull  → 取得 data/cloud-cache/
```

> 注意：雲端輸出路徑刻意用 **`data/cloud-cache/`**，與本地 `data/cache/`（被 .gitignore 排除）
> 分開。本地若要使用，請改 config 或自行同步檔案到 `data/cache/`。

---

## 前置條件
- 此 repo 已推到 GitHub（**目前本地未設定 remote**，需先建立）
- repo 可設為 **public**（無限 Actions 分鐘）或 **private**（每月 2000 分鐘免費）
- 不需要任何雲端服務費用、不需要 API key（PoC 範圍）

---

## 部署步驟

### 1. 把 repo 推上 GitHub
```bash
# 在 https://github.com/new 建立空 repo，名稱例如 CapyStock
git remote add origin https://github.com/<你的帳號>/CapyStock.git
git push -u origin feature/s25-portfolio        # 或先 merge 到 main 再 push
```

### 2. 確認 workflow 已偵測到
- 進入 GitHub repo → **Actions** 分頁
- 應看到 workflow：**Cloud Fetch (PoC)**
- 若沒看到，確認 `.github/workflows/cloud-fetch.yml` 已被 push 上去

### 3. 開啟 workflow 寫入權限
- repo → **Settings** → **Actions** → **General**
- 滾到底 **Workflow permissions**
- 選 **Read and write permissions** → Save
- （這步是讓 Actions 能 commit 回 repo）

### 4. 手動觸發第一次驗證
- Actions → Cloud Fetch (PoC) → **Run workflow**
- 參數預設即可（5 檔 × margin + flow）
- 約 1–3 分鐘完成

### 5. 檢查結果
**成功狀況**（綠燈）：
- 看到一筆 commit：`chore(cloud-fetch): update ...`
- `data/cloud-cache/` 出現 CSV 與 `_fetch_report.json`
- 本地執行 `git pull` 即可拿到

**失敗狀況**（紅燈）：
- 點 run 查看 log
- 也可下載 Artifact `fetch-report-<id>` 看 JSON 內每筆失敗原因
- 常見失敗：
  - `403 / 429` → Azure IP 被擋（**PoC 主要驗證點**）
  - `Connection timeout` → 對方限速
  - `JPX: 找不到週報 Excel 下載連結` → JPX 改版（rare）

### 6. 排程啟用
workflow 已內建 cron：每週一到五 UTC 07:00（JST 16:00，東京收盤後 1h）。
- 不需任何設定，push 上 GitHub 即自動排程
- 想暫停：Actions → Cloud Fetch (PoC) → 右上 `…` → **Disable workflow**

---

## PoC 驗證重點
這次 PoC 主要回答兩個問題：

| 問題 | 看哪裡 |
|------|--------|
| Q1: Yahoo JP / minkabu / JPX 在 Azure IP 上是否被擋？ | run log 的 OK/FAIL 比例，特別看 `source` 欄 |
| Q2: 全量抓取 3747 檔的耗時推估 | 5 檔耗時 × 750 ≈ 全量耗時，看是否 < 30 分（單 job 上限）|

**判讀**：
- **5 檔全綠** → 可進階：擴大到 universe.csv 全市場（用 `--all` 或 schedule 加參數）
- **margin 全紅、flow 綠** → Yahoo/minkabu 擋 Azure IP，需找替代源或改用 self-hosted runner
- **全紅** → 退回本地排程方案

---

## 之後要做（PoC 成功後）

1. **本地端整合**：寫一支 `scripts/sync_cloud_cache.py`，`git pull` 後把
   `data/cloud-cache/*.csv` 複製到 `data/cache/` 給系統使用（或改 `config.CACHE_DIR` 雙路徑讀取）
2. **全市場排程**：把 cron 改為 `python scripts/cloud_fetch.py --all`
3. **失敗通知**：workflow 加 step，失敗時發 Telegram / email
4. **EDINET 5% rule**：加進 workflow（已有 API key 機制）
5. **股價也加進來**：目前 PoC 只做 margin + flow，price 之後一起搬

---

## 成本確認
- public repo：**完全免費，無限分鐘**
- private repo：每月 2000 分鐘免費。每日 1 次 × ~3 分鐘 × 22 天 ≈ **66 分鐘 / 月**，遠低於額度
- 儲存：每檔 CSV 約 10KB，3747 檔 × 2 種 ≈ 75MB，遠低於 1GB 建議上限

**符合「完全免費」需求。**

---

## 已知限制
- GitHub Actions 不是常駐服務，是 cron 排程。最小間隔 5 分鐘，實際排隊延遲常達 10–30 分鐘
  → 適合「日線收盤後一次」，不適合即時 tick
- 單一 job 最長 6 小時（PoC workflow 設 30 分鐘超時）
- repo 若 inactive 60 天，scheduled workflow 會被自動停用（每月手動 run 一次即可避免）
