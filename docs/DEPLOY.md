# CapyStock — 部署手冊

涵蓋三種部署模式：本機 Python（首選）、Docker、Windows 服務。

---

## 0. 共通環境變數

放於 `data/.env`（single source of truth；FastAPI 啟動時讀）：

```
# ── 通知通道 ────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=xxx@gmail.com
SMTP_PASS=app_password
SMTP_FROM=CapyStock <xxx@gmail.com>
LINE_NOTIFY_TOKEN=xxxx
NOTIFY_DEFAULT_RECIPIENTS=cky1983@gmail.com

# ── 資料源 ──────────────────────────────────
EDINET_API_KEY=...

# ── 開發旗標 ────────────────────────────────
SMTP_DRY_RUN=0
CAPYSTOCK_SCHEDULER_DISABLED=0
CAPYSTOCK_FRONTEND_DIR=          # 留空 = 自動偵測 frontend/dist
```

**規則**：缺必要變數時 app 會以 degraded mode 啟動（warning，但不 crash）。

---

## 1. 模式 A：本機 Python（首選）

```bash
# 1. backend
pip install -r requirements.txt

# 2. frontend build
cd frontend && npm install && npm run build && cd ..

# 3. 起服務
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

開瀏覽器：`http://localhost:8000`（前端）／`http://localhost:8000/docs`（API doc）。

或一鍵：`make run`

---

## 2. 模式 B：Docker

```bash
# build
docker build -t capystock:latest .

# 或 docker compose（推薦，自動掛 data/ volume）
docker compose up -d

# 健康檢查
curl http://localhost:8000/api/v1/health
```

- `data/` 會以 volume 掛入 container，所有 watchlist / scan snapshot / 通知 log 都保存在 host
- 若要關閉 container 內的排程器（例如 host 已用 Task Scheduler 排程）：在 compose 設 `CAPYSTOCK_SCHEDULER_DISABLED=1`

---

## 3. 模式 C：Windows 服務（NSSM）

```powershell
# 系統管理員 PowerShell
cd C:\path\to\CapyStock

# 先 build frontend
cd frontend; npm install; npm run build; cd ..

# 安裝 nssm（如未安裝）
choco install nssm

# 註冊服務
.\docs\DEPLOY\nssm_install.ps1

# 確認
sc query CapyStock
curl http://localhost:8000/api/v1/health
```

移除：
```powershell
nssm stop CapyStock
nssm remove CapyStock confirm
```

服務 log：`data/service_stdout.log`、`data/service_stderr.log`

---

## 4. 排程設定

詳見 `docs/SPRINT_11.md`。重點：

- in-process APScheduler（預設啟用）：API 啟動時自動跑 daily_pipeline / healthcheck
- Windows Task Scheduler 範本：`docs/DEPLOY/scheduler_winTask.xml.template`
- Cron 範本：`docs/DEPLOY/scheduler_cron.example`

---

## 5. Port / 防火牆

| Port | 用途 |
|---|---|
| 8000 | FastAPI（前後端統一入口） |
| 5173 | （僅 dev）Vite dev server |

production 只需開 8000。

---

## 6. Log 位置

| 類型 | 路徑 |
|---|---|
| Notification log | `data/notification_log.csv` |
| Scheduler runs | `data/scheduler_runs.csv` |
| Scan snapshots | `data/scan_snapshots/{kind}_{date}.parquet` |
| Service stdout/stderr (Windows) | `data/service_stdout.log` / `service_stderr.log` |
| Docker | `docker logs capystock` |

---

## 7. 備份 `data/`

`data/` 是唯一狀態。建議：

```bash
# 每日備份（rclone / robocopy / cp）
robocopy data\ backup\capystock-$(Get-Date -F yyyyMMdd) /E
```

`data/.env` 含 secret，**不要** commit、不要外傳。

---

## 8. 升級

```bash
git pull
pip install -r requirements.txt          # 若 requirements.txt 改了
cd frontend && npm install && npm run build && cd ..

# 模式 A
# 重啟 uvicorn

# 模式 B
docker compose down && docker compose up -d --build

# 模式 C
nssm restart CapyStock
```

---

## 9. 疑難排解

| 症狀 | 排查 |
|---|---|
| `/` 404 | frontend 未 build：執行 `cd frontend && npm run build` |
| `/api/v1/health` 不回 | uvicorn 沒起、port 被佔 |
| 通知沒寄出 | 看 `data/notification_log.csv`；檢查 `SMTP_DRY_RUN` 是否為 1 |
| Scheduler 沒跑 | 看 `/api/v1/health/system`，檢查 `CAPYSTOCK_SCHEDULER_DISABLED` |
| Docker healthcheck 失敗 | `docker logs capystock`，多半是 `data/.env` 沒掛或變數錯 |
