# Milestone 4 — 自動化、排程與通知

## 規劃決策（已確認）
- 排程：**Windows Task Scheduler（主環境）+ APScheduler（in-process 後援）** 雙軌並存，預設用 APScheduler
- 通知通道：**Email（SMTP）+ LINE Notify**，未來可擴 Telegram / Discord
- 通知策略：**每日彙總（digest）+ 即時關鍵警報（critical）** 兩種模式
- 依賴：M3 的 backend service / scan_service / simulation_service

## Sprint 範圍與大綱

| Sprint | 主題 | 詳細設計 |
|---|---|---|
| S9 | 通知通道抽象 + Email/LINE 推送 | [SPRINT_09.md](SPRINT_09.md) |
| S10 | 通知規則 + 警報 → 推送整合 | [SPRINT_10.md](SPRINT_10.md) |
| S11 | 排程器（APScheduler + 雙 worker 整合） | [SPRINT_11.md](SPRINT_11.md) |
| S12 | 通知 / 排程設定 UI + 健康監控頁 | [SPRINT_12.md](SPRINT_12.md) |
| S13 | 部署整合 + 文件 | [SPRINT_13.md](SPRINT_13.md) |

## 整體架構新增

```
CapyStock/
├── api/
│   ├── notify/                    # ★新增 通知通道抽象
│   │   ├── base.py                # NotificationChannel ABC
│   │   ├── email_channel.py / line_channel.py
│   │   └── digest.py
│   ├── services/
│   │   ├── notification_service.py   # ★新增
│   │   └── scheduler_service.py      # ★新增
│   ├── routers/
│   │   ├── notify.py / scheduler.py
│   ├── schemas/notify.py / scheduler.py
│   └── workers/
│       ├── daily_pipeline.py / healthcheck.py
├── data/
│   ├── notification_rules.json / notification_log.csv
│   ├── scheduler_runs.csv
│   └── .env                       # ★擴 SMTP_*, LINE_NOTIFY_TOKEN
├── frontend/src/routes/settings/
│   ├── +page.svelte / notifications/+page.svelte / scheduler/+page.svelte
└── docs/DEPLOY/
    ├── scheduler_winTask.xml.template
    └── scheduler_cron.example
```

### 新增環境變數（`data/.env`）
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=xxx@gmail.com
SMTP_PASS=app_password
SMTP_FROM=CapyStock <xxx@gmail.com>
LINE_NOTIFY_TOKEN=xxxx
NOTIFY_DEFAULT_RECIPIENTS=cky1983@gmail.com
```

## 跨 Sprint 共通約定

### 通知測試規則
- 任何測試**禁止**真寄 email / 真打 LINE Notify
- email：`SMTP_DRY_RUN=1` 或起 `smtpdfix`
- LINE：`responses` lib mock endpoint
- conftest fixture `disable_external_notify` autouse

### 排程測試規則
- `BackgroundScheduler` 以 `MemoryJobStore` + 注入 `clock` 加速
- 任何 service / handler 不可呼叫 `datetime.now()` — 一律 `clock.now()`
- 預設 timezone `Asia/Tokyo`

### 環境變數規範
- `data/.env` 為 single source of truth
- `api/deps.py` 定義 `Settings(BaseSettings)`，所有變數以 typed model 暴露
- 缺必要變數 → app startup 印 warning 但不 crash（degraded mode）

## 順序建議
1. **S9**：通道層先做，無依賴
2. **S10**：規則 + digest，依賴 S9
3. **S11**：排程器，整合 S2 / S7 / S10 worker
4. **S12**：UI，依賴 S9–S11 API
5. **S13**：部署 + 文件，最後做

完成 M4 後，使用者可：「設一次規則 + 排程，每天早上 8 點收到 email/LINE，週末手動跑 backtest，平日 paper 自動推進」。
