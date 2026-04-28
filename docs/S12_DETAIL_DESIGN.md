# S12 — Detail Design：通知 / 排程設定 UI + 健康監控頁

依賴：[SPRINT_12.md](SPRINT_12.md)

完成日：2026-04-27

## 新增後端

### `api/schemas/health.py`
- `WorkerHeartbeat` / `DataFreshness` / `DeliverabilityPoint` / `DiskBreakdown` / `DiskUsage` / `SystemHealth`

### `api/routers/health.py` — `GET /api/v1/health/system`
聚合四個面向：

1. **heartbeat**：呼叫 `scheduler_service.list_runs(job_id="healthcheck_ping", days=2)`，
   取最新一筆 `success`，狀態判定：
   - 距今 ≤ 3600s → `ok`
   - 否則 `stale`
   - 沒紀錄 → `unknown`

2. **freshness**：
   - 掃描 `data/scan_snapshots/` 內 `^(signals|dividend)_(YYYY-MM-DD)\.parquet$` 取最大日期
   - paper sim cursor 最舊：`simulation_service.list_all()` 過濾 paper + 非 draft

3. **deliverability**：`notification_service.read_log(days=7)` 依日彙總，
   產生 7 個點（含當日，遞增）每點含 total / ok / success_rate

4. **disk**：`DATA_DIR` 直屬子項目 size（rglob 累計），合計 total_bytes

註冊於 `api/main.py`：`app.include_router(health.router, prefix="/api/v1", tags=["health"])`

## 新增前端

### `frontend/src/routes/settings/+layout.svelte`
- subnav：通知 / 排程 / 健康，使用 `$page.url.pathname` 標 active

### `frontend/src/routes/settings/+page.svelte`
- 預設 redirect `/settings/notifications`

### `frontend/src/routes/settings/notifications/+page.svelte`
- Channels 卡：`GET /notify/channels`，綠燈 = configured && healthy；「測試發送」呼叫 `POST /notify/test` → toast
- Rules 表：CRUD，toggle = `PATCH /notify/rules/{id}` `{enabled}`；立即執行 = `POST /notify/rules/{id}/run`；Preview = `POST /notify/digest/preview {rule_id}` → modal iframe srcdoc
- Log 表：`GET /notify/log?days=7&channel=...&severity=...`
- Modal：使用 `RuleForm` 元件

### `frontend/src/routes/settings/scheduler/+page.svelte`
- jobs 表：`GET /scheduler/jobs`
- inline cron 編輯（`CronEditor`），按「套用」呼叫 `PATCH /scheduler/jobs/{id} {cron}`
- enabled checkbox → `PATCH {enabled}`
- Run Now → `POST /scheduler/jobs/{id}/run`
- 點 row 展開最近 10 runs（`GET /scheduler/runs?job_id=...&days=7`）→ mini timeline 色塊
- 點色塊開 run 詳情 modal

### `frontend/src/routes/settings/health/+page.svelte`
- 4 張卡：heartbeat、freshness、deliverability（echarts line）、disk
- `GET /health/system`

### `frontend/src/lib/components/CronEditor.svelte`
純前端 cron 解讀，支援：
- `0 8 * * *` → 「每日 08:00」
- `0 8 * * 1-5` → 「平日 08:00」
- `*/30 * * * *` → 「每 30 分鐘」
- 5 欄以外 → 紅框 + 「無效」

### `frontend/src/lib/components/RuleForm.svelte`
- mode radio（digest / realtime）切換顯示
  - digest → 顯示 `CronEditor`
  - realtime → 顯示 `alert_types` checkbox + `min_severity` radio
- scope radio (watchlist / favorites / all)
- channels checkbox + 每個 channel 的 recipients 輸入框（comma separated）
- submit 事件 emit 完整 payload（含 trigger.time 由 cron 反推 HH:MM）

### Sidebar
`+layout.svelte` 加「設定」連結到 `/settings/notifications`

## 資料相依
- `data/scheduler_runs.csv`（S11）
- `data/scan_snapshots/`（S2）
- `data/notification_log.csv`（S9）
- `data/simulations/`（S7）

## 驗收

### 後端 smoke test（已通過）
```
CAPYSTOCK_SCHEDULER_DISABLED=1 python -c "TestClient(app).get('/api/v1/health/system')"
→ 200, keys=[deliverability, disk, freshness, generated_at, heartbeat]
deliverability_len=7
```

### 前端手動驗收（需 dev server）
1. `/settings/notifications` channel 卡片渲染、test 按鈕回 toast
2. 建立 rule → 表格新增；toggle → PATCH 成功
3. Preview → modal iframe 含 srcdoc
4. `/settings/scheduler` jobs row count 與後端一致；inline 改 cron 顯示「套用」按鈕
5. Run Now → toast；展開列出 timeline 色塊
6. `/settings/health` 4 張卡，折線圖 7 點

## 已知限制 / HUMAN_TODO
- e2e Playwright spec、unit Vitest spec 未建立（M4 Sprint Plan 約定但實際 repo 尚未配 playwright workspace；補完或調整 plan 後另開 ticket）
- CronEditor 的人話表只覆蓋常見 patterns，複雜 cron 直接顯示 raw
