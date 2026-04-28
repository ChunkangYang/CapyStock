# S10 Detail Design — 通知規則 + digest / realtime 整合（實作紀錄）

依賴：[SPRINT_10.md](SPRINT_10.md)
完成日：2026-04-25

## 實裝產出
- ✅ `api/schemas/notify.py` 擴充：NotificationRule、RuleTrigger、RuleFilters、RuleCreate/UpdateRequest、RuleRunRequest、DigestPreviewRequest
- ✅ `api/services/rule_store.py`：notification_rules.json 持久化（CRUD、原子寫入、UUID id）
- ✅ `api/notify/digest.py` 擴充 `build_digest()`：
  - 4 區塊（持倉警示 / 停損警示 / 吃貨訊號 / 其他）
  - 自動算 severity（critical > warn > info）
  - body_text + body_html 同步產出，支援 snapshot_summary 模擬交易摘要
- ✅ `api/services/notification_service.py` 擴充：
  - `filter_alert_for_rule()` — alert_types / min_severity / codes 過濾
  - `should_run_digest()` — daily 排程時間 + catch-up 判定
  - `_scope_codes()` — watchlist / favorites / all 範圍解析
  - `build_digest_for_rule()` — 套用 rule 過濾後產生 payload，附 `rule:{id}` tag
  - `process_daily_digest(today, now, dry_run, alerts_by_code)` — 評估全部 enabled digest rules
  - `process_realtime_alert(alert, code, dry_run)` — 24h dedupe（依 rule/code/type tag 在 log 中查找）
- ✅ `api/routers/notify.py` 擴充 6 個 endpoints：
  - `GET /api/v1/notify/rules`
  - `POST /api/v1/notify/rules`
  - `PATCH /api/v1/notify/rules/{id}`
  - `DELETE /api/v1/notify/rules/{id}`
  - `POST /api/v1/notify/rules/{id}/run`（dry_run 回傳 preview payload）
  - `POST /api/v1/notify/digest/preview`（rule_id? + date? → payload）

## 自動化測試（17/17 全綠，與 S9 合計 38/38）
- `tests/unit/test_digest.py`（2）：sections/counts、空 alerts
- `tests/unit/test_notification_rules.py`（8）：filter、min_severity、time gating、catch-up、5→2 命中、disabled skip、24h dedupe、CRUD
- `tests/api/test_notify_rules_router.py`（7）：CRUD full cycle、404、run dry-run、preview default/with-rule/invalid date/rule 404
