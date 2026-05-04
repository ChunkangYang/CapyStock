# CapyStock — 使用者手冊

CapyStock 是日股籌碼分析工具。本手冊涵蓋：

1. 安裝
2. 追蹤清單管理（CLI + Web UI）
3. 掃描與信號（CLI + Web UI）
4. 模擬交易
5. 通知設定
6. 排程設定

---

## 1. 安裝

```bash
git clone <repo>
cd CapyStock
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn api.main:app --port 8000
```

開 `http://localhost:8000`。詳細部署選項請見 [`DEPLOY.md`](DEPLOY.md)。

---

## 2. 追蹤清單

### CLI

```bash
python -m capystock.main add 7203 2500     # 加入 7203 (Toyota)，追蹤起始價 2500
python -m capystock.main remove 7203
python -m capystock.main list
```

### Web UI

開 `/`，左側 sidebar → **Watchlist**。可新增、移除、查看每檔最新信號。

---

## 3. 掃描與信號

### CLI

```bash
python -m capystock.main check                # 全 watchlist 掃一次
python -m capystock.main check --code 7203    # 單檔
python -m capystock.main edinet --days 7      # 5%-rule 申報回掃
python -m capystock.main fundamental 7203     # 8 指標基本面評分
python -m capystock.main log --days 30        # 歷史警示
```

### Web UI

| 頁面 | 功能 |
|---|---|
| `/` | 進出場信號儀表板（投機面） |
| `/dividend` | 高股息篩選（金雞） |
| `/scan` | 全市場掃描結果（每日 snapshot） |
| `/favorites` | 我的最愛 |
| `/stock/{code}` | 個股詳細：價格、信用残、EDINET 申報、基本面 |

---

## 4. 模擬交易（Paper / Backtest）

### Web UI

`/simulation` → 新增 simulation：

- **Paper trading**：每日推進，依信號自動下單
- **Backtest**：指定區間，一次性回測

可設定：
- 初始資金
- 交易策略（signal-based）
- 風險上限（單筆 / 總曝險）

執行後可看 equity curve、勝率、夏普比、最大回撤。

### 排程推進

paper 模式會由 daily_pipeline 自動推進到「今日」。手動推進：

```bash
curl -X POST http://localhost:8000/api/v1/simulation/{id}/advance
```

---

## 5. 通知設定

### Web UI

`/settings/notifications`：

| 欄位 | 說明 |
|---|---|
| 通道（Email / LINE） | 開關各通道 |
| Digest 時段 | 每日彙總時間（預設 08:00 JST） |
| Realtime 觸發 | 哪些 severity 即時推送（預設 critical） |
| 測試通知 | 一鍵發送測試（dry-run 可選） |

設定存於 `data/notification_rules.json`。secret（SMTP / LINE token）放 `data/.env`。

### CLI dry-run 測試

```bash
SMTP_DRY_RUN=1 python -m api.workers.daily_pipeline
```

不會真寄信，但會寫 `data/notification_log.csv`。

---

## 6. 排程設定

### Web UI

`/settings/scheduler` — 看到目前所有 job：

| Job | 預設 cron | 用途 |
|---|---|---|
| `daily_pipeline` | 08:00 JST 平日 | 跑掃描 → 收集 alert → 推送 |
| `healthcheck_ping` | 每 30 分 | worker heartbeat |
| `paper_advance` | 09:30 JST 平日 | 推進 paper simulation |

可手動觸發、暫停、調整 cron。

### 健康監控

`/health` — 看：

- worker heartbeat（最近一次成功時間）
- 資料新鮮度（signals 最新日 / paper cursor 最舊）
- 通知成功率（過去 7 日）
- disk usage（`data/` 各目錄）

---

## 7. 常見任務

| 想做什麼 | 怎麼做 |
|---|---|
| 設一次規則，每天早上收 digest | `/settings/notifications` 開 email + 設定 08:00 → 完成 |
| 週末手動跑全市場掃描 | CLI: `python -m capystock.main check`；UI: `/scan` 點刷新 |
| 追蹤 7203、停損 5% | UI 新增 watchlist + 設停損；或 CLI `add 7203 2500` |
| 看哪天通知失敗 | `/health` deliverability 圖表，或 `data/notification_log.csv` |

---

## 8. 進階

- 環境變數總表：見 [`DEPLOY.md`](DEPLOY.md) §0
- 架構圖：[`ARCHITECTURE.md`](ARCHITECTURE.md)
- Bug 回報：寫進 `docs/BUG.md`
