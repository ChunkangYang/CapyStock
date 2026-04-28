# CapyStock — 架構文件

## 模組關係（Mermaid）

```mermaid
flowchart TB
  subgraph FE[Frontend - SvelteKit / Vite]
    UI_Dash["/ 信號儀表板"]
    UI_Div["/dividend 高股息"]
    UI_Scan["/scan 全市場掃描"]
    UI_Sim["/simulation"]
    UI_Set["/settings (notify / scheduler)"]
    UI_Hlt["/health 健康監控"]
  end

  subgraph API[FastAPI - api/]
    R_Meta[meta]
    R_WL[watchlist]
    R_Sig[signals]
    R_Div[dividend]
    R_Scan[scan]
    R_Fav[favorites]
    R_Sim[simulation]
    R_Notify[notify]
    R_Sched[scheduler]
    R_Hlt[health]
  end

  subgraph SVC[Services]
    SVC_Sig[signal_service]
    SVC_Scan[scan_service]
    SVC_Sim[simulation_service]
    SVC_Notify[notification_service]
    SVC_Sched[scheduler_service]
  end

  subgraph WORK[Workers - api/workers/]
    W_Daily[daily_pipeline]
    W_HC[healthcheck]
  end

  subgraph CHAN[Notify Channels - api/notify/]
    CH_Email[email_channel]
    CH_LINE[line_channel]
    CH_Digest[digest builder]
  end

  subgraph CORE[Core - capystock/]
    C_Scrape[scraper kabutan / yfinance]
    C_Anal[analyzer 進出場 / 停損 / 吃貨]
    C_Fund[fundamental IR Bank]
    C_Edinet[edinet 5%-rule]
    C_Store[storage watchlist / log]
  end

  subgraph DATA[data/]
    D_WL[watchlist.json]
    D_Log[log.csv]
    D_NotifyLog[notification_log.csv]
    D_Rules[notification_rules.json]
    D_Snap[scan_snapshots/*.parquet]
    D_Sim[simulations/*.json]
    D_Cache[cache/ price + margin + flow]
    D_Env[.env]
  end

  FE -->|HTTP /api/v1/*| API
  API --> SVC
  SVC --> CORE
  SVC --> DATA
  W_Daily --> SVC_Scan
  W_Daily --> SVC_Sig
  W_Daily --> SVC_Notify
  W_HC --> SVC_Sched
  SVC_Sched --> W_Daily
  SVC_Sched --> W_HC
  SVC_Notify --> CHAN
  CHAN --> D_NotifyLog
  C_Scrape -->|kabutan / yfinance| EXT[(External Data)]
  C_Edinet -->|EDINET API| EXT
```

## 啟動流程

1. `uvicorn api.main:app` 啟動 → `lifespan` hook
2. 預設啟動 `scheduler_service.start()`（除非 `CAPYSTOCK_SCHEDULER_DISABLED=1`）
3. 排程器註冊 jobs：`daily_pipeline`、`healthcheck_ping`、`paper_advance`
4. FastAPI mount：
   - `/api/v1/*` → 各 router
   - `/` → `frontend/dist`（StaticFiles, html=True）

## daily_pipeline 流程

```
today = date.today()
1. 若 signals snapshot 不存在 → run_signals_scan
2. analyze_watchlist → {code: [alerts]}
3. 對每個 critical alert → process_realtime_alert（去重 24h）
4. process_daily_digest（依 rule 中 last_run 控制 idempotent）
```

## 部署形態

| 模式 | 進程 | 排程 |
|---|---|---|
| Local Python | `uvicorn` 單一進程 | in-process APScheduler |
| Docker | container | in-process APScheduler |
| Windows Service (NSSM) | service 包 uvicorn | in-process APScheduler 或外部 Task Scheduler 呼叫 `python -m api.workers.daily_pipeline` |

## 資料流向總覽

| 來源 | 走哪 | 落地 |
|---|---|---|
| kabutan / yfinance | scraper | `data/cache/{CODE}_*.csv` |
| EDINET | edinet 模組 | `data/cache/edinet/` |
| 全市場掃描 | scan_service | `data/scan_snapshots/{kind}_{date}.parquet` |
| 模擬交易 | simulation_service | `data/simulations/{uuid}.json` |
| 通知 | notification_service | `data/notification_log.csv` |
| 排程 run | scheduler_service | `data/scheduler_runs.csv` |

## 設定檔

| 檔案 | 內容 | 是否 commit |
|---|---|---|
| `data/.env` | secret（SMTP/LINE/EDINET key） | ❌ |
| `data/watchlist.json` | 追蹤股票 | ❌ |
| `data/notification_rules.json` | 通知規則 | ❌ |
| `capystock/config.py` | 演算法參數（停損％等） | ✅ |
| `Dockerfile` / `docker-compose.yml` / `Makefile` | 部署 | ✅ |
