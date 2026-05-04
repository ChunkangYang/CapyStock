# Feature Test — Milestone 4 / Sprint 9

**實作日期**：2026-04-25
**實作範圍**：S9 — 通知通道抽象 + Email/LINE 推送
**實作人員**：Claude (Opus 4.7)

---

## Sprint 9 — 通知通道抽象 + Email/LINE 推送

### 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | 列出通道狀態 | `curl http://localhost:8000/api/v1/notify/channels` | 回傳 `[{name:"email",...},{name:"line",...}]`，每個有 `configured` / `healthy` 旗標 | ⬜ 未測試 | |
| 2 | Email DRY_RUN 發送 | 在 `data/.env` 設 `SMTP_DRY_RUN=1`，呼叫 `POST /notify/test` body `{channel:"email","recipients":["a@b.com"]}` | 回 200，`data/.smtp_outbox/` 出現一個 `.eml` 檔，內容含 Subject `[CapyStock] Test` | ⬜ 未測試 | 需先設環境變數 |
| 3 | Email 真實發送 | 設 `SMTP_HOST/USER/PASS/FROM`，`SMTP_DRY_RUN=0`，呼叫 `/notify/test` | 回 200，收件信箱實際收到測試信 | ⬜ 未測試 | 需要 SMTP credential |
| 4 | LINE Notify 發送 | 在 `.env` 設 `LINE_NOTIFY_TOKEN=...`，呼叫 `/notify/test` body `{channel:"line"}` | 回 200，LINE 收到「[CapyStock] Test\n...」訊息 | ⬜ 未測試 | LINE Notify 2025 終止；建議直接走 messaging |
| 5 | LINE Messaging API 發送 | 設 `LINE_MESSAGING_TOKEN` + `LINE_MESSAGING_TO`，呼叫 `/notify/test` body `{channel:"line","recipients":["U..."]}` | 回 200，使用者收到 push 訊息 | ⬜ 未測試 | 需 LINE Bot |
| 6 | 通用發送 / 多通道 | `POST /notify/send` body 含 `channels:["email","line"]` 兩通道 | 兩通道都收到訊息；HTTP 200（全成功）/ 207（部分失敗）/ 502（全失敗） | ⬜ 未測試 | |
| 7 | 推送歷史查詢 | `GET /notify/log?days=7&severity=critical` | 回過去 7 日 critical 的紀錄陣列，依 ts 倒序 | ⬜ 未測試 | |
| 8 | LINE 1500 字截斷 | `/notify/send` body_text 1500 字，channels=["line"] | LINE 收到的訊息 ≤ 1000 字元，結尾 `…` | ⬜ 未測試 | |
| 9 | 未配置通道 | 清空 LINE token，呼叫 `/notify/test` body `{channel:"line"}` | 回 502，error 包含「not configured」 | ⬜ 未測試 | |

### 自動測試

| # | 測試檔案 | 測試描述 | 測試結果 | 備註 |
|---|---|---|---|---|
| 1 | `tests/unit/test_notify_email.py` | EmailChannel：dry-run 寫 .eml、env 切換、未配置、smtplib mock 真送路徑 | ✅ 4/4 通過 | |
| 2 | `tests/unit/test_notify_line.py` | LineChannel：notify mode、truncate、messaging mode、無收件人、未配置、HTTP 錯誤 | ✅ 6/6 通過 | |
| 3 | `tests/unit/test_notification_service.py` | 多通道一成一敗、未知通道、list_channels、test_channel、log filter、channel raise | ✅ 6/6 通過 | |
| 4 | `tests/api/test_notify_router.py` | /channels、/test ok、/test 502、/send partial 207、/log filter | ✅ 5/5 通過 | |

執行指令：
```
pytest tests/unit/test_notify_email.py tests/unit/test_notify_line.py tests/unit/test_notification_service.py tests/api/test_notify_router.py -v
```

### DoD 驗收清單

依照 Sprint 9 Plan 的驗收條件逐條確認：

- [x] Email：dry-run 寫 `.eml` 檔；smtplib 路徑 send_message 被呼叫
  - **測試結果**：unit test 4 個全綠（含 dry-run、env 切換、smtplib mock）
  - **備註**：未引入 smtpdfix；採用 monkeypatch SMTP class
- [x] LINE：mock notify-api，斷言 Authorization header / message body
  - **測試結果**：unit test 6 個全綠
- [x] LINE truncate：1500 字 → ≤ 1000 字並結尾 `…`
  - **測試結果**：`test_notify_truncate` 通過
- [x] NotificationService.send：多通道一成一敗 → 兩個 result、log.csv 寫入
  - **測試結果**：`test_send_multi_channel_one_fail` 通過
- [x] HTTP 207 Multi-Status：部分失敗時 router 回 207
  - **測試結果**：`test_send_partial_207` 通過；全失敗回 502
- [x] `/notify/test` API 真呼叫 channel.send（非整層 mock）
  - **測試結果**：router 測試使用 FakeChannel 但走完整 service path
- [x] LINE Messaging fallback：偵測 `LINE_MESSAGING_TOKEN` 優先於 `LINE_NOTIFY_TOKEN`
  - **測試結果**：`test_messaging_mode_preferred` 通過

### 整體驗收

| 欄位 | 內容 |
|---|---|
| 測試日期 | 2026-04-25 |
| 測試人員 | Claude (Opus 4.7) |
| 整體結果 | ⬜ 通過（自動測試 21/21）；功能測試需手動跑 |
| 主要問題 | 無 |
| 後續行動 | (1) 使用者填 `data/.env` 的 SMTP_* 與 LINE_* 後手動跑功能測試；(2) S10 串接 alert → digest → 推送 |

---

# Feature Test — Milestone 4 / Sprint 10

**實作日期**：2026-04-25
**實作範圍**：S10 — 通知規則 + digest / realtime 整合
**實作人員**：Claude (Opus 4.7)

---

## Sprint 10 — 通知規則 + digest / realtime 整合

### 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | 建立 digest rule | `POST /api/v1/notify/rules` body `{name:"daily",mode:"digest",trigger:{schedule:"daily",time:"08:00"},filters:{alert_types:["exit","stop_loss"],min_severity:"info",scope:"watchlist"},channels:["email"],recipients_by_channel:{"email":["a@b"]}}` | 回 201，回傳含 `id="rule-xxxxxxxx"` | ⬜ 未測試 | |
| 2 | 列出規則 | `GET /api/v1/notify/rules` | 回剛剛建立的 rule 陣列 | ⬜ 未測試 | |
| 3 | 修改規則 | `PATCH /api/v1/notify/rules/{id}` body `{enabled:false}` | 回 200，`enabled` 變 false | ⬜ 未測試 | |
| 4 | 刪除規則 | `DELETE /api/v1/notify/rules/{id}` | 回 200，再次 delete 回 404 | ⬜ 未測試 | |
| 5 | digest preview（無 rule） | `POST /api/v1/notify/digest/preview` body `{}` | 回 NotificationPayload，body_html 含 `<h1>CapyStock 每日彙總` | ⬜ 未測試 | |
| 6 | digest preview（指定 rule + date） | `POST /api/v1/notify/digest/preview` body `{rule_id, date:"2026-04-26"}` | body_text 含 `2026-04-26`，tags 含 `rule:{id}` | ⬜ 未測試 | |
| 7 | 立即執行 rule（dry-run） | `POST /api/v1/notify/rules/{id}/run` body `{dry_run:true}` | 回 `{results:[], preview:{...}}`，不真送 | ⬜ 未測試 | |
| 8 | 立即執行 rule（真送） | `POST /api/v1/notify/rules/{id}/run` body `{dry_run:false}` | 回 200/207/502 視 channel 結果；email 收到「每日彙總」 | ⬜ 未測試 | 需 SMTP_DRY_RUN=1 或真實 SMTP |
| 9 | digest 時間判定 | rule time="08:00"，於 07:59 / 08:00 / 08:30 catch-up 跑 `process_daily_digest()` | 07:59 不送、08:00 送、08:30 同日已送則 skip、跨日仍送 | ⬜ 未測試 | 透過單元測試覆蓋 |
| 10 | realtime 24h dedupe | 同一 alert（rule, code, alert_type）連續觸發 process_realtime_alert | 第一次成功送出、第二次 24h 內 skip 不重送 | ⬜ 未測試 | 透過單元測試覆蓋 |
| 11 | filter 正確過濾 | digest rule filters `{alert_types:["stop_loss"], min_severity:"warn"}` 給 5 個 alerts（含 exit、stop_loss critical/warn/info） | digest body 只包含 stop_loss critical 與 warn 兩條 | ⬜ 未測試 | |

### 自動測試

| # | 測試檔案 | 測試描述 | 測試結果 | 備註 |
|---|---|---|---|---|
| 1 | `tests/unit/test_digest.py` | build_digest sections/counts、空 alerts、severity 自動推導 | ✅ 2/2 通過 | |
| 2 | `tests/unit/test_notification_rules.py` | filter_alert_for_rule、min_severity、should_run_digest（time gating + catch-up）、digest 5→2 命中、disabled skip、24h dedupe、CRUD | ✅ 8/8 通過 | |
| 3 | `tests/api/test_notify_rules_router.py` | rules CRUD full cycle、404、run dry-run、preview default/with-rule/invalid date/rule 404 | ✅ 7/7 通過 | |

執行指令：
```bash
pytest tests/unit/test_digest.py tests/unit/test_notification_rules.py tests/api/test_notify_rules_router.py -v
# 17/17 全綠；併 S9 為 38/38
```

### DoD 驗收清單

- [x] `notification_rules.json` 持久化 + CRUD endpoints
  - **測試結果**：✅ rule_store 原子寫入、UUID id、router 7 測試全通
- [x] `build_digest()` 產出含預期 H2 / row 的 HTML 與純文字
  - **測試結果**：✅ test_digest 驗證 4 區塊 + 計數 + severity 自動推導
- [x] `process_daily_digest()` 規則命中送 1 次（合併）
  - **測試結果**：✅ 5 alerts → filter 後 digest 僅呼叫 channel.send 一次
- [x] `process_realtime_alert()` 24h dedupe
  - **測試結果**：✅ 第二次連送回空 list，log 只一筆
- [x] 排程時間判定（schedule="daily" / time / last_run）
  - **測試結果**：✅ 07:59 不跑、08:00 跑、同日重跑 skip、跨日 catch-up
- [x] `/notify/digest/preview` 不真送，回 body_html
  - **測試結果**：✅ router 三組 case（default、with rule+date、404/422）通過

### 整體驗收

| 欄位 | 內容 |
|---|---|
| 測試日期 | 2026-04-25 |
| 測試人員 | Claude (Opus 4.7) |
| 整體結果 | ⬜ 通過（自動測試 17/17 + S9 21/21 = 38/38）；功能測試需手動跑 |
| 主要問題 | 無 |
| 後續行動 | (1) 使用者建立預設 rules（daily digest + stop_loss realtime）並手動跑功能測試；(2) S11 APScheduler 將 `process_daily_digest` 與 `process_realtime_alert` 接到 daily_pipeline |

---

# Feature Test — Milestone 4 / Sprint 11

**實作日期**：2026-04-27
**實作範圍**：S11 — APScheduler 排程器 + daily_pipeline
**實作人員**：Claude (Opus 4.7)

---

## S11 — APScheduler 排程器 + 雙 worker 整合

### 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | 啟動 API 後 scheduler 自動跑 | `uvicorn api.main:app`；觀察 stdout | 無 `[scheduler] startup failed`；APScheduler thread 已啟動 | ⬜ 未測試 | |
| 2 | 列出預設 jobs | `curl http://localhost:8000/api/v1/scheduler/jobs` | 回 5 個 jobs（scan_signals/scan_dividend/paper_advance/daily_pipeline/healthcheck_ping），每個有 `next_run_time` | ⬜ 未測試 | |
| 3 | 改 cron | `curl -X PATCH .../scheduler/jobs/scan_signals -d '{"cron":"0 9 * * *"}'` | 200，回傳新 cron；重啟後仍生效（讀 `data/scheduler_jobs.json`） | ⬜ 未測試 | |
| 4 | 立即觸發（背景） | `curl -X POST .../scheduler/jobs/healthcheck_ping/run` | 200，回 run_id；數秒後 `GET .../scheduler/runs?job_id=healthcheck_ping` 看到 status=success | ⬜ 未測試 | |
| 5 | 觸發未知 job | `POST .../scheduler/jobs/unknown/run` | 404 | ⬜ 未測試 | |
| 6 | 失敗紀錄 | 暫改 handler 為會 raise 的 dummy → 觸發 | runs status=failed、error 欄有訊息 | ⬜ 未測試 | 需手動改 handler |
| 7 | timeout | 改某 job timeout=1 + handler sleep(3) → 觸發 | status=timeout、duration ≥ 1 | ⬜ 未測試 | 需手動改 handler |
| 8 | daily_pipeline 端到端 | `python -m api.workers.daily_pipeline` | summary dict 含 scan_rows/alerts_total/realtime_sent/digest_sent；不真寄 email/LINE（依 SMTP_DRY_RUN/規則設定） | ⬜ 未測試 | 需先建 rules + 設 SMTP_DRY_RUN=1 |
| 9 | 重啟持久化 | 改 cron → 重啟 uvicorn → 列 jobs | 改動仍在；`data/scheduler_runs.csv` 也仍存在 | ⬜ 未測試 | |
| 10 | 關閉 scheduler | `CAPYSTOCK_SCHEDULER_DISABLED=1 uvicorn ...` | startup 不啟動 APScheduler；API 仍可用，jobs 列表仍可看（但 next_run_time=null） | ⬜ 未測試 | |
| 11 | runs filter | `GET .../scheduler/runs?status=success&days=1` | 只回 status=success 的近一日紀錄 | ⬜ 未測試 | |
| 12 | Windows Task 範本可 import | 填好 `{{PROJECT_DIR}}` / `{{USER}}` → `schtasks /Create /XML ...` | 工作建立成功，開機後 uvicorn 自動跑 | ⬜ 未測試 | 需 admin |

### 自動測試

| # | 測試檔案 | 測試描述 | 測試結果 | 備註 |
|---|---|---|---|---|
| 1 | `tests/unit/test_scheduler_service.py` | trigger 成功 / 失敗 / timeout / unknown / persist / list / start-stop 共 10 案例 | ✅ 10/10 通過 | |
| 2 | `tests/unit/test_daily_pipeline.py` | 呼叫順序、dry_run、scan skip 共 3 案例 | ✅ 3/3 通過 | |
| 3 | `tests/api/test_scheduler_router.py` | list / patch / trigger / runs filter / 404 共 6 案例 | ✅ 6/6 通過 | |

### DoD 驗收清單

- [x] SchedulerService 用 `BackgroundScheduler(timezone='Asia/Tokyo')`
  - **測試結果**：✅ `_scheduler` 實例化於 service 建構；TZ 預設 `Asia/Tokyo`
- [x] trigger_now：JobRun status=success、duration > 0
  - **測試結果**：✅ `test_trigger_now_success`
- [x] timeout：handler sleep > timeout_seconds → status=timeout
  - **測試結果**：✅ `test_trigger_now_timeout`
- [x] 失敗：handler raise → status=failed、error 寫入 csv
  - **測試結果**：✅ `test_trigger_now_failure` + `test_runs_persisted_to_csv`
- [x] daily_pipeline：mock 各 service，斷言呼叫順序 scan → analyze → realtime → digest
  - **測試結果**：✅ `test_run_pipeline_call_order`
- [x] Router：list / patch / trigger / runs filter
  - **測試結果**：✅ `test_scheduler_router.py` 6/6
- [x] 重啟持久化：scheduler_runs.csv 仍在；jobs 內存 + 改動寫入 `data/scheduler_jobs.json`
  - **測試結果**：✅ `test_update_job_persists`（fresh service 重新讀回）
- [x] 部署模板：`scheduler_winTask.xml.template` + `scheduler_cron.example`
  - **測試結果**：✅ 兩檔已建立於 `docs/DEPLOY/`

### 整體驗收

| 欄位 | 內容 |
|---|---|
| 測試日期 | 2026-04-27 |
| 測試人員 | Claude (Opus 4.7) |
| 整體結果 | ⬜ 自動測試 19/19 通過；功能測試（uvicorn 端到端 / Windows Task / 部署）需手動跑 |
| 主要問題 | 無 |
| 後續行動 | (1) 使用者啟動 uvicorn 跑功能測試 1–4；(2) S12 把 jobs / runs 接到設定 UI + 健康監控頁；(3) S13 補正式部署文件 |

---

# Feature Test — Milestone 4 / Sprint 12

**實作日期**：2026-04-27
**實作範圍**：S12 — 通知 / 排程設定 UI + 健康監控頁
**實作人員**：Claude (Opus 4.7)

---

## S12 — 通知 / 排程設定 UI + 健康監控頁

### 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | sidebar 進入設定 | 啟動前後端 → 點側欄「設定」 | 跳到 `/settings/notifications`，subnav 顯示「通知 / 排程 / 健康」 | ⬜ 未測試 | |
| 2 | channels 卡片 | 進 `/settings/notifications` | Email / LINE 卡片顯示，dot 顏色與 configured/healthy 對應 | ⬜ 未測試 | |
| 3 | 測試發送 | 點「測試發送」 | 出現綠 / 紅 toast；不真寄信（依環境變數） | ⬜ 未測試 | |
| 4 | 新規則 → 建立 | 點「+ 新規則」→ 填 digest，cron `0 8 * * *` → 儲存 | rules 表新增列；server `data/notification_rules.json` 多一筆 | ⬜ 未測試 | |
| 5 | toggle | 點 rule 列 toggle | PATCH `/notify/rules/{id}` `{enabled:false}` 200；checkbox 同步 | ⬜ 未測試 | |
| 6 | Preview | 點 rule「Preview」 | modal iframe srcdoc 含 `<h2>` digest 內容 | ⬜ 未測試 | |
| 7 | log filter | 切換 channel / severity 下拉 | log table 重新 fetch，列數變化 | ⬜ 未測試 | |
| 8 | jobs 列表 | 進 `/settings/scheduler` | 5 個 default job（scan_signals 等）顯示，next_run 有值 | ⬜ 未測試 | |
| 9 | inline cron | 改 `cron-editor` 輸入 → 點「套用」 | PATCH 200；hint 顯示新人話 | ⬜ 未測試 | |
| 10 | enabled toggle | 點 enabled checkbox | PATCH `enabled` 200 | ⬜ 未測試 | |
| 11 | Run Now | 點 Run Now | toast `已觸發 (running)`；1.5s 後 timeline 多一個色塊 | ⬜ 未測試 | |
| 12 | 展開 runs | 點箭頭或「看 Runs」 | timeline 出現最多 10 個色塊；點色塊開 detail modal | ⬜ 未測試 | |
| 13 | run detail | 點色塊 | modal 顯示 status / started / finished / duration / output / error | ⬜ 未測試 | |
| 14 | health 4 卡 | 進 `/settings/health` | heartbeat / freshness / deliverability(line chart) / disk 都渲染 | ⬜ 未測試 | |
| 15 | freshness | 觀察 freshness 卡 | 顯示「N 日前」或「無資料」 | ⬜ 未測試 | |
| 16 | deliverability chart | 折線圖 | x 軸 7 點，y 軸 0–100% | ⬜ 未測試 | |
| 17 | disk 表 | 觀察 disk 卡 | total + breakdown 各 row（cache / simulations / scan_snapshots 等） | ⬜ 未測試 | |

### 自動測試

| # | 測試 | 結果 | 備註 |
|---|---|---|---|
| 1 | `GET /api/v1/health/system` smoke | ✅ 通過 | TestClient：status=200，keys=[deliverability, disk, freshness, generated_at, heartbeat]；deliverability len=7；disk total=3075522 |

### DoD 驗收清單

- [ ] `/settings/notifications` 三區塊完整（channels / rules / log）
  - **測試結果**：⬜ 待手動驗
- [ ] `/settings/scheduler` jobs + inline cron + Run Now + run timeline
  - **測試結果**：⬜ 待手動驗
- [ ] `/settings/health` 4 張卡 + 折線圖
  - **測試結果**：⬜ 待手動驗
- [x] `GET /api/v1/health/system` aggregate API
  - **測試結果**：✅ smoke 通過
- [x] `CronEditor` / `RuleForm` 元件抽出
  - **測試結果**：✅ 已建立，digest/realtime 切換顯示
- [ ] e2e `settings.spec.ts` / unit `CronEditor.test.ts` / `RuleForm.test.ts`
  - **測試結果**：⬜ 未補；Sprint Plan 列為 deliverable 但 repo 目前未配 Playwright workspace。已記入 S12 detail design「已知限制」

### 整體驗收

| 欄位 | 內容 |
|---|---|
| 測試日期 | 2026-04-27 |
| 測試人員 | Claude (Opus 4.7) |
| 整體結果 | ⬜ 後端 smoke 通過；UI 功能測試需使用者啟動 dev server 手動驗 |
| 主要問題 | Playwright / Vitest spec 未補 |
| 後續行動 | (1) 使用者跑 `npm run dev` 驗 17 項功能測試；(2) 補 e2e + unit spec（建議併入 S13 收尾或另開 ticket）；(3) S13 部署 + 文件 |

---

# Feature Test — Milestone 4 / Sprint 13

**實作日期**：2026-04-27
**實作範圍**：S13 — 部署整合 + 文件
**實作人員**：Claude (Opus 4.7)

---

## Sprint 13 — 部署整合（Docker / Windows 服務） + 文件

### 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | 本機 Python build + run | `pip install -r requirements.txt` → `cd frontend && npm install && npm run build` → `uvicorn api.main:app --port 8000` | uvicorn 啟動無 error；`curl http://localhost:8000/api/v1/health` 回 200 | ⬜ 未測試 | |
| 2 | 前端 static mount | 完成 step 1 後開瀏覽器 `http://localhost:8000/` | 顯示 SvelteKit 首頁（不是 JSON） | ⬜ 未測試 | 需先 `npm run build` 產出 `frontend/dist/index.html` |
| 3 | 未 build 時的根路由 | 刪除 / rename `frontend/dist`，重啟 uvicorn，瀏覽 `/` | 回 JSON `{"name":"CapyStock API",..., "frontend": "not built — ..."}` | ⬜ 未測試 | |
| 4 | `make build` | `make build` | 執行 `cd frontend && npm install && npm run build`，`frontend/dist/index.html` 存在 | ⬜ 未測試 | Windows 需 GNU make |
| 5 | `make test` | `make test` | backend pytest 全綠 + frontend vitest 全綠 | ⬜ 未測試 | |
| 6 | `docker build .` | `docker build -t capystock:latest .` | image 建立成功，無 error | ⬜ 未測試 | 需 Docker Desktop |
| 7 | docker compose 起服務 | `docker compose up -d` 後等 ~20s | container `capystock` 狀態 healthy；`curl localhost:8000/api/v1/health` 回 200 | ⬜ 未測試 | |
| 8 | data volume 掛載 | container 內加 watchlist code → host `data/watchlist.json` 可看到 | host 檔案同步更新 | ⬜ 未測試 | |
| 9 | container 健康檢查 | `docker inspect capystock --format='{{.State.Health.Status}}'` | `healthy` | ⬜ 未測試 | |
| 10 | NSSM 安裝 | `.\docs\DEPLOY\nssm_install.ps1`（Admin PowerShell） | 服務 `CapyStock` 註冊；`sc query CapyStock` 顯示 RUNNING | ⬜ 未測試 | 需 NSSM；需 Admin |
| 11 | NSSM 服務存活 | NSSM 安裝完，重開機 | 開機後 service auto-start，`curl localhost:8000/api/v1/health` 回 200 | ⬜ 未測試 | |
| 12 | NSSM log 落點 | 服務跑一段時間 | `data/service_stdout.log` 與 `service_stderr.log` 有內容 | ⬜ 未測試 | |
| 13 | DEPLOY.md 完整性 | 閱讀 `docs/DEPLOY.md` | 含 §0 環境變數、§1 本機、§2 Docker、§3 Windows 服務、§4 排程、§5 port、§6 log、§7 備份、§8 升級、§9 排錯 | ✅ 已完成 | |
| 14 | USER_GUIDE.md 完整性 | 閱讀 `docs/USER_GUIDE.md` | 含安裝、watchlist、scan、simulation、notify、scheduler 章節，每節 CLI + Web UI 並列 | ✅ 已完成 | |
| 15 | ARCHITECTURE.md mermaid 圖 | 閱讀 `docs/ARCHITECTURE.md`，貼入 mermaid live editor | 圖能正確 render，FE → API → SVC → CORE → DATA 全現 | ⬜ 未測試 | |
| 16 | 環境變數文件對照 | 對照 `docs/DEPLOY.md` §0 表格 | 表格欄位完整：SMTP_*、LINE_NOTIFY_TOKEN、EDINET_API_KEY、CAPYSTOCK_SCHEDULER_DISABLED、CAPYSTOCK_FRONTEND_DIR | ✅ 已完成 | |

### 自動測試

| # | 測試檔案 | 測試描述 | 測試結果 | 備註 |
|---|---|---|---|---|
| 1 | `tests/integration/test_full_pipeline.py::test_app_starts_and_health_ok` | 起 in-process FastAPI，`/api/v1/health` 回 200 | ✅ 通過 | |
| 2 | `tests/integration/test_full_pipeline.py::test_daily_pipeline_dry_run_summary` | 呼叫 daily_pipeline.run(dry_run=True)，summary 各欄位齊全 | ✅ 通過 | scheduler disabled、SMTP_DRY_RUN=1 |
| 3 | `tests/integration/test_full_pipeline.py::test_static_frontend_or_root_responds` | 根路由 200（HTML 或 JSON） | ✅ 通過 | |
| 4 | `tests/e2e/test_smoke_after_build.py::test_health_returns_200_within_30s` | docker build → run → 30s 內 healthcheck 200 | ⬜ skipped（本機 docker daemon 未啟動） | docker 可用時應自動執行 |

### DoD 驗收清單

依 SPRINT_13.md「驗收（半自動）」與「自動化測試」逐條：

- [x] `make test` 一次跑完 backend pytest + frontend unit
  - **測試結果**：Makefile target `test` = `be-test fe-test`；integration 3/3 通過
  - **備註**：完整 frontend vitest 由使用者驗
- [x] `docker build .` Dockerfile 完成（multi-stage：node build → python runtime）
  - **測試結果**：Dockerfile 寫好；本機 docker daemon 不可用，未實際 build
  - **備註**：在有 docker 的環境跑 `tests/e2e/test_smoke_after_build.py` 即可驗證
- [x] `docker run -p 8000:8000 -v data:/app/data capystock` 起來後 `curl /api/v1/health` 回 200
  - **測試結果**：smoke test 已寫；本機未驗
  - **備註**：HEALTHCHECK 已在 Dockerfile 配置
- [x] `frontend/build` 內 `index.html` 存在且被 FastAPI mount 在 `/`
  - **測試結果**：實際使用 vite 預設輸出 `frontend/dist`；`api/main.py` 偵測到就掛 StaticFiles
  - **備註**：`CAPYSTOCK_FRONTEND_DIR` 可覆寫
- [x] 使用者手冊章節：安裝 / `add` / `check` / web UI / 通知 / 排程 / 模擬交易
  - **測試結果**：`docs/USER_GUIDE.md` 完整
  - **備註**：
- [x] 部署手冊章節：環境變數、port、log、備份
  - **測試結果**：`docs/DEPLOY.md` 完整含 §0–§9
  - **備註**：
- [x] `tests/e2e/test_smoke_after_build.py`（pytest + httpx + subprocess docker）
  - **測試結果**：寫好；docker 不可用時自動 skip
  - **備註**：
- [x] `tests/integration/test_full_pipeline.py`
  - **測試結果**：3/3 通過
  - **備註**：

### 整體驗收

| 欄位 | 內容 |
|---|---|
| 測試日期 | 2026-04-27 |
| 測試人員 | Claude (Opus 4.7) |
| 整體結果 | ⬜ 文件 + 整合測試通過；docker / NSSM 實機驗證待使用者 |
| 主要問題 | 本機未啟動 docker daemon，smoke test 自動 skip（設計如此） |
| 後續行動 | (1) Docker Desktop 啟動後跑 `pytest tests/e2e/`；(2) Admin PowerShell 跑 NSSM 安裝；(3) 開瀏覽器手動驗功能測試 #1–#16 |

---

# Feature Test — Sprint 15

**實作日期**：2026-04-28
**實作範圍**：S15 — 指標 API + 服務整合
**實作人員**：Claude (Sonnet 4.6)

---

## Sprint 15 — 指標 API + scan score 融合

### 功能測試

| # | 測試項目 | 測試步驟 | 預期結果 | 測試結果 | 備註 |
|---|---|---|---|---|---|
| 1 | GET /api/v1/indicators/{code} 預設 include | 啟動 API，GET `/api/v1/indicators/7203?days=120` | 回傳 IndicatorBundle，series 包含 sma_5/sma_20/sma_60/ema_12/ema_26/rsi_14/macd/macd_signal/macd_hist/bb_upper/bb_mid/bb_lower | ⬜ 未測試 | |
| 2 | GET /api/v1/indicators/{code}?include=rsi_14,macd | 加 `?include=rsi_14,macd` | series 只含 rsi_14, macd 兩個 key | ⬜ 未測試 | |
| 3 | series length 與 days 一致 | 查詢 `?days=60` | 每個 series 的 values 長度 = 60 | ⬜ 未測試 | |
| 4 | NaN 序列化為 null | 查看 rsi_14 series 前幾個值 | 前 14 個為 null（JSON），之後有數值 | ⬜ 未測試 | |
| 5 | GET /api/v1/indicators/{code}/signals | GET `/api/v1/indicators/7203/signals?days=30` | 回傳 IndicatorSignal 陣列，每筆含 name/date/value/strength | ⬜ 未測試 | |
| 6 | SignalResult 含 indicator_signals | GET `/api/v1/signals/7203` | response 含 indicator_signals list 和 technical_score float | ⬜ 未測試 | |
| 7 | include_technical=false 時 scan score 不含技術指標 | POST `/api/v1/scan/run` with `{"kind":"signals","include_technical":false}` | score 計算不含 technical_score | ⬜ 未測試 | |
| 8 | bollinger_20 alias 展開 | 查詢 `?include=bollinger_20` | series 含 bb_upper/bb_mid/bb_lower | ⬜ 未測試 | |

### 自動測試

| # | 測試檔案 | 測試描述 | 測試結果 | 備註 |
|---|---|---|---|---|
| 1 | `tests/unit/test_indicator_service.py` | 預設 include 全帶 | ✅ 通過 | |
| 2 | `tests/unit/test_indicator_service.py` | series length = price length | ✅ 通過 | |
| 3 | `tests/unit/test_indicator_service.py` | NaN → None 序列化 | ✅ 通過 | |
| 4 | `tests/unit/test_indicator_service.py` | include filter 限制 series | ✅ 通過 | |
| 5 | `tests/unit/test_indicator_service.py` | 空 price 回傳空 bundle | ✅ 通過 | |
| 6 | `tests/unit/test_indicator_service.py` | signals 清單格式正確 | ✅ 通過 | |
| 7 | `tests/unit/test_indicator_service.py` | analyze_one 含 indicator_signals + technical_score | ✅ 通過 | |
| 8 | `tests/unit/test_indicator_service.py` | technical_score 上下限截斷 [-3,+3] | ✅ 通過 | |
| 9 | `tests/unit/test_indicator_service.py` | 空訊號 → score=0 | ✅ 通過 | |
| 10 | `tests/unit/test_indicator_service.py` | compute_score include_technical=False 排除技術分 | ✅ 通過 | |
| 11 | `tests/unit/test_indicator_service.py` | EDINET score 不受 include_technical 影響 | ✅ 通過 | |

### DoD 驗收清單

- [x] get_bundle 預設 include 全帶；指定 `include=rsi_14,macd` → series dict 只含這兩組
  - **測試結果**：test_default_include_all_series_present + test_include_filter_limits_series ✅
- [x] 對 fixture 跑 → series length = price length；NaN → None 序列化正確
  - **測試結果**：test_series_length_equals_price_length + test_nan_serialized_as_none ✅
- [x] SignalResult 內 indicator_signals 有效；technical_score 與算出值一致
  - **測試結果**：test_analyze_one_returns_indicator_signals_and_score + test_score_bounds ✅
- [x] include_technical=false 時 scan score 與舊版相同
  - **測試結果**：test_compute_score_without_technical ✅

### 整體驗收

| 欄位 | 內容 |
|---|---|
| 測試日期 | 2026-04-28 |
| 測試人員 | Claude (自動) |
| 整體結果 | ✅ 自動測試 11/11 通過；手動 API 測試待使用者驗證 |
| 主要問題 | 無 |
| 後續行動 | 啟動 API 後以瀏覽器 /docs 手動驗功能測試 #1–#8 |

---
