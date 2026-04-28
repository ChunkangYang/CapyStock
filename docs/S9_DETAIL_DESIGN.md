# S9 Detail Design — 通知通道抽象 + Email/LINE 推送（實作紀錄）

依賴：[SPRINT_09.md](SPRINT_09.md)
完成日：2026-04-25

## 實裝產出
- ✅ `api/schemas/notify.py`：Pydantic models（NotificationPayload、ChannelResult、ChannelInfo、TestRequest、SendRequest、NotificationLogEntry）
- ✅ `api/notify/base.py`：NotificationChannel ABC（send / health_check / is_configured）
- ✅ `api/notify/email_channel.py`：SMTP channel
  - 587 + STARTTLS / 465 + SSL 雙模式
  - `SMTP_DRY_RUN=1` → 寫 `data/.smtp_outbox/{ts}.eml`
  - body_html 缺省時自動以內建 markdown→HTML 轉換
- ✅ `api/notify/line_channel.py`：LINE channel
  - `LINE_MESSAGING_TOKEN` 優先（push API），fallback `LINE_NOTIFY_TOKEN`
  - 1500 字元截斷至 1000 字並結尾加 `…`
- ✅ `api/notify/digest.py`：text→HTML helper、truncate_for_line
- ✅ `api/services/notification_service.py`：
  - `list_channels()` / `send()` / `test_channel()`
  - 多通道送出後寫 `data/notification_log.csv`（thread-safe）
  - `read_log(days, channel?, severity?)` 篩選與排序
  - `build_default_service()` 工廠
- ✅ `api/routers/notify.py`：4 個 endpoints
  - `GET /api/v1/notify/channels` / `POST /api/v1/notify/test` / `POST /api/v1/notify/send` / `GET /api/v1/notify/log`
  - 多 status 碼：200/207/502
- ✅ `data/notification_rules.json`、`data/notification_log.csv` 初始化

## 自動化測試（21/21 全綠）
- `tests/unit/test_notify_email.py`（4）：dry-run、env、未配置、smtplib mock
- `tests/unit/test_notify_line.py`（6）：notify mode、truncate、messaging mode、無收件人、未配置、HTTP error
- `tests/unit/test_notification_service.py`（6）：多通道一成一敗、未知通道、list、test_channel、log filter、channel raise
- `tests/api/test_notify_router.py`（5）：channels、test ok、test fail 502、partial 207、log filter
