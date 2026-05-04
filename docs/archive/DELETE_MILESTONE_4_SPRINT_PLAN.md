# Milestone 4 — 自動化、排程與通知 詳細設計

> 本文件交付給 Sonnet / Haiku 作為實作藍本。每個 Sprint 含：目的、檔案產物、API/元件規格、驗收條件。
> 規劃決策（已確認）：
> - 排程：**Windows Task Scheduler（主環境）+ APScheduler（in-process 後援）** 雙軌並存，預設用 APScheduler，cron XML 範本附在 docs。
> - 通知通道：**Email（SMTP）+ LINE Notify**，未來可擴 Telegram / Discord。
> - 通知策略：**每日彙總（digest）+ 即時關鍵警報（critical）** 兩種模式。
> - 前一 Milestone（M3）的 backend service / scan_service / simulation_service 為依賴。

---

## 0. 整體架構新增

```
CapyStock/
├── api/
│   ├── notify/                    # ★新增 通知通道抽象
│   │   ├── __init__.py
│   │   ├── base.py                # NotificationChannel ABC
│   │   ├── email_channel.py       # SMTP
│   │   ├── line_channel.py        # LINE Notify
│   │   └── digest.py              # digest 組裝（HTML / 純文字）
│   ├── services/
│   │   ├── notification_service.py   # ★新增 編排：抓 alerts → 過濾 → 推送
│   │   └── scheduler_service.py      # ★新增 APScheduler 包裝
│   ├── routers/
│   │   ├── notify.py              # ★新增 通知測試 / 訂閱管理
│   │   └── scheduler.py           # ★新增 job 列表 / 執行歷史
│   ├── schemas/
│   │   ├── notify.py              # NotificationRule / NotificationLog
│   │   └── scheduler.py           # JobDef / JobRun
│   └── workers/
│       ├── daily_pipeline.py      # ★新增 每日整合 worker（scan + paper + notify）
│       └── healthcheck.py         # ★新增 健康監控（worker 心跳）
├── data/
│   ├── notification_rules.json    # ★新增 訂閱設定
│   ├── notification_log.csv       # ★新增 推送歷史（append-only）
│   ├── scheduler_runs.csv         # ★新增 排程執行歷史
│   └── .env                       # ★擴 SMTP_*, LINE_NOTIFY_TOKEN
├── frontend/src/routes/
│   └── settings/                  # ★新增
│       ├── +page.svelte           # 通知設定總覽
│       ├── notifications/+page.svelte
│       └── scheduler/+page.svelte
└── docs/
    ├── MILESTONE_4_SPRINT_PLAN.md (本文件)
    ├── DEPLOY/scheduler_winTask.xml.template   # Windows Task Scheduler 範本
    └── DEPLOY/scheduler_cron.example           # Linux cron 範本
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

---

## Sprint 9 — 通知通道抽象 + Email/LINE 推送

### 目的
建立 channel-agnostic 通知層，未來新增 Telegram / Discord 不用改 service。

### 檔案
- `api/notify/base.py`
- `api/notify/email_channel.py`
- `api/notify/line_channel.py`
- `api/notify/digest.py`
- `api/services/notification_service.py`
- `api/routers/notify.py`
- `api/schemas/notify.py`
- `data/notification_rules.json`
- `data/notification_log.csv`

### Channel 抽象

```python
# api/notify/base.py
class NotificationPayload(BaseModel):
    title: str
    body_text: str            # 純文字（LINE Notify、SMS 用）
    body_html: str | None     # HTML（Email 用；None = body_text 自動轉）
    severity: Literal["info", "warn", "critical"]
    tags: list[str]           # ["digest", "alert", "scheduler"...]
    metadata: dict            # 任意附帶資料

class ChannelResult(BaseModel):
    channel: str              # "email" / "line"
    ok: bool
    error: str | None
    sent_at: datetime
    recipient: str            # 收件人辨識（email or "line:default"）

class NotificationChannel(ABC):
    name: str
    @abstractmethod
    def send(self, payload: NotificationPayload, recipients: list[str]) -> list[ChannelResult]: ...
    @abstractmethod
    def health_check(self) -> bool: ...     # 不送訊息，只驗證 credential / endpoint reachable
```

### Email channel
- `smtplib.SMTP_SSL` (port 465) 或 `SMTP` + `starttls` (port 587)
- 發送時若 `body_html` 為 None，自動用 `markdown` lib 轉
- 測試環境：環境變數 `SMTP_DRY_RUN=1` → 不真寄，把 message 寫到 `data/.smtp_outbox/{ts}.eml`

### LINE channel
- `POST https://notify-api.line.me/api/notify`
- header `Authorization: Bearer {LINE_NOTIFY_TOKEN}`
- body: `message=...`（純文字最多 1000 字元，超過要分段；本實作先 truncate 並加 `…`）
- recipients 參數對 LINE Notify 沒意義（一個 token = 一個收信端），實作上忽略

### NotificationService

```python
class NotificationService:
    def __init__(self, channels: dict[str, NotificationChannel]): ...

    def send(self, payload: NotificationPayload, channel_names: list[str], recipients_by_channel: dict[str, list[str]]) -> list[ChannelResult]:
        """同步送多通道，全部結果寫 notification_log.csv"""

    def test_channel(self, channel_name: str, recipients: list[str]) -> ChannelResult:
        """送測試訊息：title='[CapyStock] Test'"""

    def list_channels(self) -> list[dict]:
        """{name, configured, healthy}"""
```

### Router

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/notify/channels` | 列出所有 channel 與健康狀態 |
| POST | `/api/v1/notify/test` | body `{channel, recipients?}`；送測試訊息回結果 |
| POST | `/api/v1/notify/send` | body `{title, body_text, body_html?, severity, channels, recipients_by_channel}`；通用發送（給 admin / 整合測試用） |
| GET | `/api/v1/notify/log?days=7&channel=email&severity=critical` | 推送歷史 |

### `notification_log.csv` 欄位
```
ts, channel, recipient, severity, title, ok, error, tags
```

### 驗收（自動化）

`pytest tests/unit/test_notify_email.py tests/unit/test_notify_line.py tests/unit/test_notification_service.py tests/api/test_notify_router.py -v` 全綠：

- Email：用 `aiosmtpd` 或 `smtpdfix` 在測試起 SMTP server，斷言收到 message-id / from / to / subject / body
- Email DRY_RUN：`SMTP_DRY_RUN=1` 時 `data/.smtp_outbox/` 出現 `.eml` 檔
- LINE：用 `responses` mock `notify-api.line.me`，斷言 header `Authorization: Bearer ...`、body `message=...`
- LINE truncate：1500 字元 input → 實際送出 ≤ 1000 字元並結尾為 `…`
- NotificationService.send：同時兩 channel 一成一敗 → 回傳兩個 result、log.csv 寫入兩列、HTTP 回應 207 Multi-Status
- `/notify/test` API 真的呼叫 channel.send 而非 mock 整層

### 給實作者
- `aiosmtpd` 在 Windows 上有問題 → fallback 用 `smtpdfix`（pytest plugin）
- LINE Notify 自 2025 年起官方公告將終止服務；若 token 無法申請，**改用 LINE Messaging API**（`POST https://api.line.me/v2/bot/message/push`），對外介面（`LINE channel`）保持不變。實作時偵測 `LINE_MESSAGING_TOKEN` 優先於 `LINE_NOTIFY_TOKEN`。

---

## Sprint 10 — 通知規則 + 警報 → 推送整合

### 目的
- 不是每次有 alert 就轟炸；要可訂閱 / 過濾
- 兩種模式並存：**digest（每日彙總）** vs **realtime（critical 即時）**

### 資料結構（`data/notification_rules.json`）

```json
{
  "rules": [
    {
      "id": "rule-default-digest",
      "name": "每日彙總",
      "mode": "digest",
      "trigger": { "schedule": "daily", "time": "08:00" },
      "filters": {
        "alert_types": ["exit", "stop_loss", "accumulation"],
        "min_severity": "info",
        "scope": "watchlist"
      },
      "channels": ["email"],
      "recipients_by_channel": { "email": ["cky1983@gmail.com"] },
      "enabled": true
    },
    {
      "id": "rule-stop-loss-realtime",
      "name": "停損即時警報",
      "mode": "realtime",
      "trigger": { "on_alert": true },
      "filters": {
        "alert_types": ["stop_loss"],
        "min_severity": "critical",
        "scope": "watchlist"
      },
      "channels": ["email", "line"],
      "recipients_by_channel": { "email": ["cky1983@gmail.com"] },
      "enabled": true
    }
  ]
}
```

### 檔案
- `api/services/notification_service.py`：擴 `process_alerts()`、`build_digest()`、`evaluate_rules()`
- `api/notify/digest.py`
- `api/routers/notify.py`：擴 rules CRUD endpoints

### Digest 組裝（digest.py）

```python
def build_digest(date: date, alerts_by_code: dict[str, list[Alert]], snapshot_summary: dict, scope: Literal["watchlist","favorites","all"]) -> NotificationPayload:
    """
    產出 HTML：
      ## CapyStock 每日彙總 — 2026-04-26
      ### 持倉警示（N）
        7203 トヨタ — exit_signal（C1+C3）
        ...
      ### 停損警示（N）
      ### 吃貨訊號（N）
      ### EDINET 5%申報（N）
      ### 模擬交易摘要
        - paper-foo：當前權益 1,234,567（+5.2%）
    """
```

### 整合點

```python
# api/services/notification_service.py
def process_daily_digest(today: date, dry_run: bool=False) -> list[ChannelResult]:
    """
    1. 對所有 enabled mode=digest rule，依 trigger.time 判斷是否該跑
    2. 用 scope 過濾 watchlist / favorites / all
    3. 跑 signal_service.analyze_watchlist() + scan_service.load_latest_snapshot('signals')
    4. build_digest → channels.send
    """

def process_realtime_alert(alert: Alert, code: str) -> list[ChannelResult]:
    """
    1. 對所有 enabled mode=realtime rule
    2. filters 命中即送
    3. 送之前 dedupe：notification_log.csv 中過去 24h 同 (rule_id, code, alert_type) 已送過 → skip
    """
```

### Router 擴充

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/notify/rules` | 列表 |
| POST | `/api/v1/notify/rules` | 新增 |
| PATCH | `/api/v1/notify/rules/{id}` | 修改 |
| DELETE | `/api/v1/notify/rules/{id}` | 刪除 |
| POST | `/api/v1/notify/rules/{id}/run` | 立即執行（測試用，body `{dry_run?: true}`） |
| POST | `/api/v1/notify/digest/preview` | body `{rule_id?, date?}`：回傳 NotificationPayload（不發送） |

### 驗收（自動化）

`pytest tests/unit/test_digest.py tests/unit/test_notification_rules.py tests/api/test_notify_rules_router.py -v`：

- Digest：給定 alerts dict + snapshot → 產出 HTML 含預期 H2 / row
- 規則命中：給 5 個 alert，rule filter 留 2 → channel.send 被呼叫 1 次（digest 合併）
- 即時 dedupe：同 alert 連送兩次，第二次回傳空（log 只一筆）
- Rule CRUD：POST/PATCH/DELETE 各 happy + 4xx
- preview：不真送，但回 body_html 內容正確
- 排程時間判定：rule.trigger.schedule="daily" time="08:00"，給 `now=07:59` → 不跑；`now=08:00` → 跑；`now=08:30` 但今日尚未跑過 → 跑（catch-up）

---

## Sprint 11 — 排程器（APScheduler + 雙 worker 整合）

### 目的
把以下排程化、並有 UI / API 可看：
- 每日 06:00 — `scan_worker --kind signals`
- 每日 06:30 — `scan_worker --kind dividend`
- 每日 07:00 — `paper_worker`（推進所有 paper sim）
- 每日 08:00 — digest 推送
- realtime — alert 觸發即送（在 daily_pipeline 結束時掃 alerts → process_realtime_alert）

### 檔案
- `api/services/scheduler_service.py`
- `api/routers/scheduler.py`
- `api/schemas/scheduler.py`
- `api/workers/daily_pipeline.py`
- `data/scheduler_runs.csv`
- `docs/DEPLOY/scheduler_winTask.xml.template`
- `docs/DEPLOY/scheduler_cron.example`

### SchedulerService

```python
class JobDef(BaseModel):
    id: str                      # "scan_signals", "scan_dividend", "paper_advance", "digest_send"
    name: str
    cron: str                    # "0 6 * * *"
    handler: str                 # dotted path "api.workers.scan_worker:run_signals"
    enabled: bool = True
    timeout_seconds: int = 1800
    max_instances: int = 1

class JobRun(BaseModel):
    run_id: str                  # uuid
    job_id: str
    started_at: datetime
    finished_at: datetime | None
    status: Literal["running", "success", "failed", "timeout", "skipped"]
    duration_seconds: float | None
    error: str | None
    output_summary: str | None   # 前 200 字 stdout

class SchedulerService:
    def __init__(self, jobs: list[JobDef]): ...
    def start(self) -> None: ...                 # 安裝到 APScheduler BackgroundScheduler
    def stop(self) -> None: ...
    def list_jobs(self) -> list[JobDef]: ...
    def list_runs(self, job_id: str | None=None, days: int=7) -> list[JobRun]: ...
    def trigger_now(self, job_id: str) -> JobRun: ...
    def update_job(self, job_id: str, **fields) -> JobDef: ...
```

### 預設 jobs（hard-coded 初始集合，使用者可改 cron / disable）

| id | cron | handler |
|---|---|---|
| scan_signals | `0 6 * * 1-5` | `api.workers.scan_worker:run_signals` |
| scan_dividend | `30 6 * * 1` | `api.workers.scan_worker:run_dividend`（每週一） |
| paper_advance | `0 7 * * 1-5` | `api.workers.paper_worker:run_all` |
| daily_pipeline | `0 8 * * 1-5` | `api.workers.daily_pipeline:run`（含 digest 推送 + realtime 警報掃描） |
| healthcheck_ping | `*/30 * * * *` | `api.workers.healthcheck:ping` |

### daily_pipeline.py（一次性整合腳本）

```python
def run(today: date | None=None, dry_run: bool=False) -> dict:
    """
    1. 確保今日 signals scan 已存在（沒有就現跑）
    2. analyze_watchlist → 收集 alerts
    3. process_realtime_alert(每個 critical alert)
    4. process_daily_digest(today)
    5. 回傳 summary {scan_rows, alerts_total, realtime_sent, digest_sent}
    """
```

### Router

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/scheduler/jobs` | 列表 + next_run_time |
| PATCH | `/api/v1/scheduler/jobs/{id}` | 改 cron / enabled |
| POST | `/api/v1/scheduler/jobs/{id}/run` | 立即觸發（背景） |
| GET | `/api/v1/scheduler/runs?job_id=&days=7&status=` | 執行歷史 |
| GET | `/api/v1/scheduler/runs/{run_id}` | 單筆詳情（含 output） |

### `data/scheduler_runs.csv` 欄位
```
run_id, job_id, started_at, finished_at, status, duration_seconds, error, output_summary
```

### 啟動方式
- `api/main.py` 在 `lifespan` startup hook：`SchedulerService.start()`
- shutdown hook：`SchedulerService.stop()`
- 環境變數 `CAPYSTOCK_SCHEDULER_DISABLED=1` → 跳過（測試 / 本地開發用）

### Windows Task Scheduler 範本
- `docs/DEPLOY/scheduler_winTask.xml.template`：可 import 到 Windows Task Scheduler，讓系統開機就跑 `uvicorn`（不依賴使用者登入）
- 內容：`<Triggers>` boot trigger + `<Actions>` 啟 PowerShell `cd ... && uvicorn api.main:app --port 8000`

### 驗收（自動化）

`pytest tests/unit/test_scheduler_service.py tests/unit/test_daily_pipeline.py tests/api/test_scheduler_router.py -v`：

- SchedulerService：用 `BackgroundScheduler(timezone='Asia/Tokyo')`，inject `MemoryJobStore` + 加速 clock，斷言 1 秒內 cron `* * * * *` job 至少跑一次
- trigger_now：回 JobRun status=success、duration > 0
- timeout：handler 故意 sleep > timeout_seconds → status=timeout
- 失敗：handler raise → status=failed、error 寫入 csv
- daily_pipeline：mock 各 service，斷言呼叫順序 scan → analyze → realtime → digest，summary dict 欄位完整
- Router：列表 / patch cron / trigger_now / runs filter
- 重啟持久化：scheduler_runs.csv 仍在；jobs 內存 + 改動寫入 `data/scheduler_jobs.json`（patch 後重啟仍生效）

### 給實作者
- APScheduler 用 `BackgroundScheduler`（in-process）。若日後要分離程序，遷 `apscheduler[redis]`；本 sprint 只做 in-process。
- Job handler 必須是 idempotent（同日重跑不會重複寫 snapshot — S2 已驗證）

---

## Sprint 12 — 通知 / 排程設定 UI + 健康監控頁

### 目的
讓使用者不必開 JSON / CSV 也能：
- 切換 rule 開關 / 改 cron / 改 recipient
- 查 run 歷史與失敗詳情
- 看到「最近一次 scan 何時跑、結果」

### 路由
- `/settings/notifications`
- `/settings/scheduler`
- `/settings/health`（系統狀態 dashboard）

### `/settings/notifications`

#### 區塊
1. **Channels 狀態卡**：Email / LINE 各一張（綠燈 = configured + healthy）
   - 「測試發送」按鈕 → `/notify/test` → toast 顯示 ok/error
2. **Rules 表格**：
   - 欄位：啟用 toggle / Name / Mode / Trigger / Filters 摘要 / Channels / 最近送出 / 操作（編輯 / 刪除 / 立即執行 / Preview）
   - 「+ 新規則」開 modal 表單
3. **Log table**：最近 7 日推送，可篩 channel / severity

#### 規則編輯 modal
- mode radio
- digest：cron picker（用 `cron-parser` 顯示「每日 08:00」人話）
- realtime：alert_types multi-select、min_severity radio
- scope radio (watchlist / favorites / all)
- channels multi-check + per-channel recipients 輸入
- 「Preview」按鈕 → 顯示 digest body_html（iframe srcdoc）

### `/settings/scheduler`

- Jobs 表格：Name / cron（可 inline 編輯）/ Enabled toggle / Last run / Next run / Status badge / 操作（Run Now / 看 Runs）
- 點 row 展開最近 10 次 runs（mini timeline，色塊代表 status）
- Run 詳情 modal：起訖時間 / output_summary（pre 顯示）/ error stack

### `/settings/health`

- 「Worker 心跳」：healthcheck_ping job 最近一次成功時間，超過 1 小時亮紅
- 「資料新鮮度」：`scan/snapshots` 最新日期、`paper sim cursor_date` 最舊
- 「Notification deliverability」：過去 7 日成功率（折線）
- 「Disk usage」：`data/` 目錄大小 + 各子目錄 breakdown

### API 新增
| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/health/system` | aggregate：scheduler last run / scan freshness / notify success rate / disk |

### 驗收（自動化）

`npm run test:e2e` 通過 `e2e/settings.spec.ts`：

1. 訪問 `/settings/notifications`：channels 卡片亮燈（mock `/notify/channels`）；點測試 → toast；建立 rule → 表格新增一列；toggle disable → PATCH 呼叫
2. Preview：modal 內 iframe srcdoc 含 `<h2>` 等預期內容
3. `/settings/scheduler`：jobs 表格 row count = mock；inline 改 cron → PATCH；Run Now → 1 秒內 status=running → success；展開 runs mini timeline 5 個色塊
4. `/settings/health`：四張卡 DOM 存在；scan freshness 卡顯示日期與「N 日前」相對描述；折線圖 series count = 7
5. 截圖回歸：`/settings/notifications`、`/settings/scheduler`、`/settings/health` 三張

`npm run test:unit`：
- `CronEditor.test.ts`：輸入 `0 8 * * *` → 顯示「每日 08:00」；輸入無效 → 顯示錯誤
- `RuleForm.test.ts`：mode 切換顯示對應欄位；submit emit 完整 payload

---

## Sprint 13 — 部署整合 + 文件

### 目的
把 M1–M4 所有元件打包成「一鍵啟動」服務（不為了上 cloud，為了使用者重灌時能 5 分鐘恢復）。

### 檔案
- `Dockerfile`（multi-stage：node build frontend → python runtime + adapter-static 輸出）
- `docker-compose.yml`（單 service + volume mount `data/`）
- `Makefile`：`make dev` / `make test` / `make build` / `make run`
- `docs/DEPLOY.md`：部署手冊
- `docs/USER_GUIDE.md`：使用者手冊（CLI + Web UI 並列）
- `docs/ARCHITECTURE.md`：模組關係圖（Mermaid）

### 部署模式

#### 模式 A：本機 Python（首選）
```
pip install -r requirements.txt
cd frontend && npm install && npm run build
uvicorn api.main:app --host 0.0.0.0 --port 8000
# 排程器隨 uvicorn lifespan 起
```

#### 模式 B：Docker
```
docker compose up -d
# 預設 port 8000；data/ 掛載為 volume
```

#### 模式 C：Windows 服務
- 用 `nssm` 把 `uvicorn` 註冊為服務
- 範本：`docs/DEPLOY/nssm_install.ps1`

### 驗收（半自動）

- `make test` 一次跑完 backend pytest + frontend unit + e2e（可在 CI run）
- `docker build .` 成功；`docker run -p 8000:8000 -v $(pwd)/data:/app/data capystock` 起來後 `curl /api/v1/health` 回 200
- `frontend/build` 內 `index.html` 存在且被 FastAPI mount 在 `/`
- 使用者手冊章節：安裝、`add` / `check` / web UI 走過、設定通知、設定排程、模擬交易
- 部署手冊章節：環境變數總表、port、log 位置、備份 `data/` 建議

### 自動化測試
- `tests/e2e/test_smoke_after_build.py`（pytest + httpx）：build 完 docker image，subprocess 起 container，30 秒內 healthcheck 200，清理
- `tests/integration/test_full_pipeline.py`：起 in-process FastAPI + scheduler disabled，呼叫 `daily_pipeline.run(today, dry_run=True)`，斷言 summary 各欄位 > 0、notification log 有 dry-run 記錄

---

## 跨 Sprint 共通約定（沿用 M3，補充以下）

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

---

## 順序建議
1. **S9**：通道層先做，無依賴
2. **S10**：規則 + digest，依賴 S9
3. **S11**：排程器，整合 S2 / S7 / S10 worker
4. **S12**：UI，依賴 S9–S11 API
5. **S13**：部署 + 文件，最後做

完成 M4 後，使用者可：「設一次規則 + 排程，每天早上 8 點收到 email/LINE，週末手動跑 backtest，平日 paper 自動推進」。
